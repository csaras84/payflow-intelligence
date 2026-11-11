"""Seed PayPal Sandbox with real sent B2B invoices for the demo.

Run from backend/: python -m app.seed.seed_sandbox
"""
import uuid
import httpx
from app.tools.paypal_client import PayPalSandboxClient

DEMO_INVOICES = [
    ("Artisan Cafe Group", "ap@artisancafe.example.com", "520.00", "Wholesale Espresso Beans"),
    ("Metro Co-Work Pantry", "finance@metrocowork.example.com", "340.00", "Monthly Roastery Supply"),
    ("Harbor Bistro LLC", "accounts@harborbistro.example.com", "450.00", "Single-Origin Cold Brew Kegs"),
]


def main() -> None:
    client = PayPalSandboxClient()
    headers = client._headers()

    with httpx.Client(timeout=20.0) as http:
        for idx, (name, email, amount, item_name) in enumerate(DEMO_INVOICES, start=1):
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
            if resp.status_code in (200, 201):
                data = resp.json()
                inv_id = data.get("id") or data.get("href", "").split("/")[-1]
                # Send the draft invoice so its status becomes SENT/UNPAID
                http.post(
                    f"{client.base_url}/v2/invoicing/invoices/{inv_id}/send",
                    json={"send_to_invoicer": False, "send_to_recipient": True},
                    headers=headers,
                )
                print(f"[{idx}/3] Created & Sent Sandbox Invoice {inv_id} ({inv_num}) - ${amount} USD for {name}")
            else:
                print(f"[{idx}/3] Failed ({resp.status_code}): {resp.text}")


if __name__ == "__main__":
    main()