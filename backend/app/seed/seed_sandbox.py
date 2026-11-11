"""Create a handful of sandbox orders so the dashboard has data.

Run from backend/:  python -m app.seed.seed_sandbox
"""
import random

from app.tools.paypal_client import PayPalClient

SAMPLES = [
    ("Wholesale order", "USD"),
    ("Subscription renewal", "USD"),
    ("EU marketplace sale", "EUR"),
    ("Consulting invoice", "USD"),
    ("UK retail sale", "GBP"),
]


def main(n: int = 10) -> None:
    client = PayPalClient()
    for i in range(n):
        desc, cur = random.choice(SAMPLES)
        amount = round(random.uniform(25, 2500), 2)
        order = client.create_order(amount, cur, desc)
        print(f"[{i + 1}/{n}] {order.get('id')}  {cur} {amount:>9.2f}  {desc}")


if __name__ == "__main__":
    main()
