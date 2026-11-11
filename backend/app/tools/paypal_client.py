import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

# Load .env from current working directory or repo root
load_dotenv()
root_env = Path(__file__).resolve().parents[3] / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env, override=False)

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"
SEEDED_DISPUTES_FILE = SEED_DIR / "seeded_disputes.json"
SEEDED_INVOICE_META_FILE = SEED_DIR / "seeded_invoice_meta.json"


class PayPalSandboxClient:
    def __init__(self) -> None:
        self.client_id = (
            os.getenv("PAYPAL_CLIENT_ID", "").strip().strip('"').strip("'")
        )
        self.client_secret = (
            os.getenv("PAYPAL_CLIENT_SECRET", "").strip().strip('"').strip("'")
        )
        self.base_url = "https://api-m.sandbox.paypal.com"
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

        self.toolkit = None
        if self.client_id and self.client_secret:
            try:
                from paypal_agent_toolkit.langchain.toolkit import PayPalToolkit

                self.toolkit = PayPalToolkit(
                    client_id=self.client_id,
                    secret=self.client_secret,
                    environment="sandbox",
                )
            except Exception:
                self.toolkit = None

    def _raise_for_paypal_error(self, resp: httpx.Response, context: str) -> None:
        if resp.status_code >= 400:
            raise RuntimeError(
                f"PayPal Sandbox API Error during {context} "
                f"[HTTP {resp.status_code} {resp.request.method} {resp.request.url}]: {resp.text}"
            )

    def _get_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Missing PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET in .env"
            )

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
            )
            self._raise_for_paypal_error(resp, "OAuth2 token exchange")
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + int(data.get("expires_in", 3200)) - 60
            return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # --- Helpers for Seeded Disputes State File ---

    def _load_seeded_disputes(self) -> List[Dict[str, Any]]:
        if not SEEDED_DISPUTES_FILE.exists():
            return []
        return json.loads(SEEDED_DISPUTES_FILE.read_text(encoding="utf-8"))

    def _is_seeded_dispute(self, dispute_id: str, capture_id: str = "") -> bool:
        for d in self._load_seeded_disputes():
            if d.get("dispute_id") == dispute_id:
                return True
            txs = d.get("disputed_transactions", [{}])
            if capture_id and txs and txs[0].get("seller_transaction_id") == capture_id:
                return True
        return False

    def _update_seeded_dispute_status(self, dispute_id: str, new_status: str, note: str) -> None:
        disputes = self._load_seeded_disputes()
        for d in disputes:
            if d.get("dispute_id") == dispute_id:
                d["status"] = new_status
                d["last_action_note"] = note
        SEEDED_DISPUTES_FILE.write_text(json.dumps(disputes, indent=2), encoding="utf-8")

    # --- READ-ONLY OPERATIONS (Used above Merchant Approval gate) ---

    def get_available_balance_usd(self) -> float:
        override_bal = os.getenv("DEMO_STARTING_BALANCE_USD")
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{self.base_url}/v1/reporting/balances",
                params={"currency_code": "USD"},
                headers=self._headers(),
            )
            self._raise_for_paypal_error(resp, "GET /v1/reporting/balances")
            if override_bal is not None:
                return float(override_bal)
            balances = resp.json().get("balances", [])
            for b in balances:
                if b.get("currency") == "USD":
                    val = b.get("available_balance", {}).get("value")
                    if val is not None:
                        return float(val)
            return 0.0

    def list_open_disputes(self) -> List[Dict[str, Any]]:
        # Always authenticate and query live PayPal Sandbox first
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{self.base_url}/v1/customer/disputes",
                headers=self._headers(),
            )
            self._raise_for_paypal_error(resp, "GET /v1/customer/disputes")
            items = resp.json().get("items", [])
            if items:
                detailed: List[Dict[str, Any]] = []
                for item in items[:5]:
                    d_id = item.get("dispute_id")
                    detail_resp = client.get(
                        f"{self.base_url}/v1/customer/disputes/{d_id}",
                        headers=self._headers(),
                    )
                    self._raise_for_paypal_error(
                        detail_resp, f"GET /v1/customer/disputes/{d_id}"
                    )
                    detailed.append(detail_resp.json())
                return detailed

        # If live Sandbox returned 200 OK with 0 open disputes, load seeded_disputes.json
        seeded = self._load_seeded_disputes()
        if not seeded:
            raise RuntimeError(
                "PayPal Sandbox returned 0 open disputes and seeded_disputes.json is missing. "
                "Run `python -m app.seed.seed_sandbox` first."
            )
        return seeded

    def list_overdue_invoices(self) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{self.base_url}/v2/invoicing/invoices",
                params={"page_size": 10, "total_required": "true"},
                headers=self._headers(),
            )
            self._raise_for_paypal_error(resp, "GET /v2/invoicing/invoices")
            items = resp.json().get("items", [])
            unpaid = [
                inv
                for inv in items
                if inv.get("status")
                in ("SENT", "UNPAID", "PARTIALLY_PAID", "PAYMENT_PENDING")
            ][:3]

            meta_map: Dict[str, Any] = {}
            if SEEDED_INVOICE_META_FILE.exists():
                meta_map = json.loads(
                    SEEDED_INVOICE_META_FILE.read_text(encoding="utf-8")
                )

            defaults = [(12, 0.88), (6, 0.94), (15, 0.80)]
            for idx, inv in enumerate(unpaid):
                inv_id = inv.get("id", "")
                if inv_id in meta_map:
                    inv["days_overdue"] = meta_map[inv_id]["days_overdue"]
                    inv["historical_reliability"] = meta_map[inv_id]["historical_reliability"]
                else:
                    d_over, rel = defaults[idx % len(defaults)]
                    inv["days_overdue"] = d_over
                    inv["historical_reliability"] = rel

            return unpaid

    # --- WRITE OPERATIONS (Strictly gated behind Merchant Approval) ---

    def add_shipment_tracking(
        self, capture_id: str, tracking_number: str, carrier: str = "DHL"
    ) -> Dict[str, Any]:
        # Validate token is active before proceeding
        _ = self._get_token()
        if self._is_seeded_dispute("", capture_id=capture_id):
            return {
                "status": "TRACKING_ADDED",
                "capture_id": capture_id,
                "live": False,
            }

        payload = {
            "trackers": [
                {
                    "transaction_id": capture_id,
                    "tracking_number": tracking_number,
                    "status": "DELIVERED",
                    "carrier": carrier,
                }
            ]
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/shipping/trackers-batch",
                json=payload,
                headers=self._headers(),
            )
            self._raise_for_paypal_error(resp, "POST /v1/shipping/trackers-batch")
            return {"status": "TRACKING_ADDED", "capture_id": capture_id, "live": True}

    def provide_dispute_evidence(
        self,
        dispute_id: str,
        carrier_name: str,
        tracking_number: str,
        notes: str,
    ) -> Dict[str, Any]:
        _ = self._get_token()
        if self._is_seeded_dispute(dispute_id):
            self._update_seeded_dispute_status(dispute_id, "UNDER_REVIEW", notes)
            return {"dispute_id": dispute_id, "status": "UNDER_REVIEW", "live": False}

        payload = {
            "evidences": [
                {
                    "evidence_type": "PROOF_OF_FULFILLMENT",
                    "evidence_info": {
                        "tracking_info": [
                            {
                                "carrier_name": carrier_name,
                                "tracking_number": tracking_number,
                            }
                        ]
                    },
                    "notes": notes[:2000],
                }
            ]
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/customer/disputes/{dispute_id}/provide-evidence",
                json=payload,
                headers=self._headers(),
            )
            self._raise_for_paypal_error(
                resp, f"POST /v1/customer/disputes/{dispute_id}/provide-evidence"
            )
            return {"dispute_id": dispute_id, "status": "UNDER_REVIEW", "live": True}

    def make_dispute_offer(
        self, dispute_id: str, offer_amount_usd: float, note: str
    ) -> Dict[str, Any]:
        _ = self._get_token()
        if self._is_seeded_dispute(dispute_id):
            self._update_seeded_dispute_status(dispute_id, "OFFER_SENT", note)
            return {"dispute_id": dispute_id, "status": "OFFER_SENT", "live": False}

        payload = {
            "note": note[:2000],
            "offer_amount": {
                "currency_code": "USD",
                "value": f"{offer_amount_usd:.2f}",
            },
            "offer_type": "REFUND",
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/customer/disputes/{dispute_id}/make-offer",
                json=payload,
                headers=self._headers(),
            )
            self._raise_for_paypal_error(
                resp, f"POST /v1/customer/disputes/{dispute_id}/make-offer"
            )
            return {"dispute_id": dispute_id, "status": "OFFER_SENT", "live": True}

    def send_invoice_reminder(
        self, invoice_id: str, subject: str, note: str
    ) -> Dict[str, Any]:
        payload = {
            "subject": subject,
            "note": note,
            "send_to_invoicer": True,
            "send_to_recipient": True,
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}/v2/invoicing/invoices/{invoice_id}/remind",
                json=payload,
                headers=self._headers(),
            )
            self._raise_for_paypal_error(
                resp, f"POST /v2/invoicing/invoices/{invoice_id}/remind"
            )
            return {"invoice_id": invoice_id, "status": "REMINDER_SENT", "live": True}

    def create_supplier_payout(
        self, recipient_email: str, amount_usd: float, po_reference: str
    ) -> Dict[str, Any]:
        sender_batch_id = f"PAYFLOW-{po_reference}-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": f"Settlement for Purchase Order {po_reference}",
                "email_message": f"Automated working-capital payout for {po_reference}.",
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {"value": f"{amount_usd:.2f}", "currency": "USD"},
                    "note": f"Supplier settlement for {po_reference}",
                    "sender_item_id": po_reference,
                    "receiver": recipient_email,
                }
            ],
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/payments/payouts",
                json=payload,
                headers=self._headers(),
            )
            self._raise_for_paypal_error(resp, "POST /v1/payments/payouts")
            data = resp.json()
            batch_id = data.get("batch_header", {}).get(
                "payout_batch_id", sender_batch_id
            )
            batch_status = data.get("batch_header", {}).get(
                "batch_status", "PENDING"
            )
            return {
                "payout_batch_id": batch_id,
                "status": batch_status,
                "live": True,
            }

    def verify_dispute_status(self, dispute_id: str) -> str:
        _ = self._get_token()
        if self._is_seeded_dispute(dispute_id):
            for d in self._load_seeded_disputes():
                if d.get("dispute_id") == dispute_id:
                    return d.get("status", "UNDER_REVIEW")

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{self.base_url}/v1/customer/disputes/{dispute_id}",
                headers=self._headers(),
            )
            self._raise_for_paypal_error(
                resp, f"GET /v1/customer/disputes/{dispute_id}"
            )
            return resp.json().get("status", "UNDER_REVIEW")

    def verify_payout_status(self, payout_batch_id: str) -> str:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{self.base_url}/v1/payments/payouts/{payout_batch_id}",
                headers=self._headers(),
            )
            self._raise_for_paypal_error(
                resp, f"GET /v1/payments/payouts/{payout_batch_id}"
            )
            return (
                resp.json()
                .get("batch_header", {})
                .get("batch_status", "PROCESSING")
            )