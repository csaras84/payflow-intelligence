"""Seed PayPal Sandbox with real sent B2B invoices + local seeded disputes.

Run from backend/: python -m app.seed.seed_sandbox
"""
import json
import uuid
from pathlib import Path
import httpx
from app.tools.paypal_client import PayPalSandboxClient

DEMO_INVOICES = [
    ("Artisan Cafe Group", "ap@artisancafe.example.com", "520.00", "Wholesale Espresso Beans", 12, 0.88),
    ("Metro Co-Work Pantry", "finance@metrocowork.example.com", "340.00", "Monthly Roastery Supply", 6, 0.94),
    ("Harbor Bistro LLC", "accounts@harborbistro.example.com", "450.00", "Single-Origin Cold Brew Kegs", 15, 0.80),
]

SEEDED_DISPUTES = [
    {
        "dispute_id": "PP-D-90418",
        "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "dispute_amount": {"currency_code": "USD", "value": "650.00"},
        "disputed_transactions": [{"seller_transaction_id": "CAP-88210"}],
        "seeded": True,
    },
    {
        "dispute_id": "PP-D-90422",
        "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED",
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "dispute_amount": {"currency_code": "USD", "value": "400.00"},
        "disputed_transactions": [{"seller_transaction_id": "CAP-88219"}],
        "seeded": True,
    },
    {
        "dispute_id": "PP-D-90429",
        "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "dispute_amount": {"currency_code": "USD", "value": "180.00"},
        "disputed_transactions": [{"seller_transaction_id": "CAP-88244"}],
        "seeded": True,
    },
]


def main() -> None:
    client = PayPalSandboxClient()
    headers = client._headers()

    seed_dir = Path(__file__).resolve().parent
    disputes_file = seed_dir / "seeded_disputes.json"
    invoice_meta_file = seed_dir / "seeded_invoice_meta.json"

    # 1. Write seeded disputes state file (resets statuses to WAITING_FOR_SELLER_RESPONSE)
    disputes_file.write_text(json.dumps(SEEDED_DISPUTES, indent=2), encoding="utf-8")
    print(f"[Disputes] Seeded {len(SEEDED_DISPUTES)} disputes in {disputes_file.name}")

    # 2. Create & send real B2B invoices in PayPal Sandbox
    invoice_meta = {}
    with httpx.Client(timeout=25.0) as http:
        for idx, (name, email, amount, item_name, days_overdue, reliability) in enumerate(
            DEMO_INVOICES, start=1
        ):
            inv_num = f"INV-2026-{uuid.uuid4().hex[:4].upper()}"
            draft_payload = {
                "detail": {
                    "invoice_number": inv_num,
                    "currency_code": "USD",
                    "note": "Net-15 wholesale coffee supply invoice.",
                },
                "primary_recipients": [
                    {
                        "billing_info": {
                            "name": {"full_name": name},
                            "email_address": email,
                        }
                    }
                ],
                "items": [
                    {
                        "name": item_name,
                        "quantity": "1",
                        "unit_amount": {"currency_code": "USD", "value": amount},
                    }
                ],
            }
            resp = http.post(
                f"{client.base_url}/v2/invoicing/invoices",
                json=draft_payload,
                headers=headers,
            )
            client._raise_for_paypal_error(resp, "Create Draft Invoice")
            data = resp.json()
            inv_id = data.get("id") or data.get("href", "").split("/")[-1]

            send_resp = http.post(
                f"{client.base_url}/v2/invoicing/invoices/{inv_id}/send",
                json={"send_to_invoicer": False, "send_to_recipient": True},
                headers=headers,
            )
            client._raise_for_paypal_error(send_resp, f"Send Invoice {inv_id}")

            invoice_meta[inv_id] = {
                "days_overdue": days_overdue,
                "historical_reliability": reliability,
            }
            print(
                f"[{idx}/3] Created & Sent Live Sandbox Invoice {inv_id} ({inv_num}) "
                f"- ${amount} USD for {name} (reliability={reliability})"
            )

    invoice_meta_file.write_text(json.dumps(invoice_meta, indent=2), encoding="utf-8")
    print(f"[Invoices] Saved overdue/reliability metadata to {invoice_meta_file.name}")


if __name__ == "__main__":
    main()