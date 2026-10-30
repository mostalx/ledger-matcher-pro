"""
Creates fake orders / invoices / payments CSV files for testing the matcher.

Everything here is made up. Most orders go through the normal path
(order -> invoice -> payment), then I deliberately break a few of them
so the matcher has something to find. Run it with a fixed seed so the
sample data is the same every time.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
AS_OF = date(2026, 4, 15)      # the "today" of the sample data
NUM_ORDERS = 120

CUSTOMERS = [
    "Nile Trading", "Baltic Foods", "Anatolia Retail", "Vistula Logistics",
    "Cairo Fresh Market", "Lodz Office Supplies", "Aegean Imports",
    "Warsaw Tech Parts", "Bosphorus Cafe Group", "Carpathia Wholesale",
]


def money(low, high):
    return round(random.uniform(low, high), 2)


def main(out_folder="data"):
    random.seed(SEED)
    out = Path(out_folder)
    out.mkdir(exist_ok=True)

    # 1. normal orders, oldest first (so the "early" ones are safely overdue by AS_OF)
    start = date(2026, 1, 5)
    orders = []
    for i in range(NUM_ORDERS):
        orders.append({
            "order_id": f"ORD-{1001 + i}",
            "customer": random.choice(CUSTOMERS),
            "order_date": start + timedelta(days=int(i * 0.6) + random.randint(0, 2)),
            "amount": money(150, 6000),
        })

    # 2. pick which orders get which problem (no overlaps)
    early = list(range(0, 80))           # these have had plenty of time to be paid
    random.shuffle(early)
    unbilled = set(early[:6])
    amount_wrong = set(early[6:11])
    duplicated = set(early[11:15])
    never_paid = set(early[15:23])
    short_paid = set(early[23:28])
    over_paid = set(early[28:31])

    invoices, payments = [], []
    inv_no, pay_no = 5001, 9001

    for idx, o in enumerate(orders):
        if idx in unbilled:
            continue  # nobody sent an invoice, the classic "forgot to bill"

        inv_date = o["order_date"] + timedelta(days=random.randint(1, 5))
        inv_amount = o["amount"]
        if idx in amount_wrong:
            # someone typed the price wrong, off by a few percent
            inv_amount = round(o["amount"] * random.choice([0.93, 1.05, 1.08]), 2)

        inv_id = f"INV-{inv_no}"
        inv_no += 1
        invoices.append({"invoice_id": inv_id, "order_id": o["order_id"],
                         "invoice_date": inv_date, "amount": inv_amount})

        if idx in duplicated:
            invoices.append({"invoice_id": f"INV-{inv_no}", "order_id": o["order_id"],
                             "invoice_date": inv_date + timedelta(days=2),
                             "amount": inv_amount})
            inv_no += 1

        if idx in never_paid:
            continue

        pay_date = inv_date + timedelta(days=random.randint(8, 35))
        if pay_date > AS_OF:
            continue  # customer still has time, not a problem

        pay_amount = inv_amount
        if idx in short_paid:
            pay_amount = round(inv_amount - money(20, 400), 2)   # bank fee or deduction
        if idx in over_paid:
            pay_amount = round(inv_amount + money(50, 300), 2)

        payments.append({"payment_id": f"PAY-{pay_no}", "invoice_id": inv_id,
                         "payment_date": pay_date, "amount": pay_amount})
        pay_no += 1

    # 3. a few invoices for orders that do not exist
    for _ in range(3):
        invoices.append({"invoice_id": f"INV-{inv_no}",
                         "order_id": f"ORD-{random.randint(9001, 9099)}",
                         "invoice_date": date(2026, 2, random.randint(1, 20)),
                         "amount": money(300, 2500)})
        inv_no += 1

    # 4. a couple of payments pointing at an invoice number nobody has
    for _ in range(2):
        payments.append({"payment_id": f"PAY-{pay_no}",
                         "invoice_id": f"INV-{random.randint(8000, 8099)}",
                         "payment_date": date(2026, 3, random.randint(1, 25)),
                         "amount": money(200, 3000)})
        pay_no += 1

    write_csv(out / "orders.csv", orders, ["order_id", "customer", "order_date", "amount"])
    write_csv(out / "invoices.csv", invoices, ["invoice_id", "order_id", "invoice_date", "amount"])
    write_csv(out / "payments.csv", payments, ["payment_id", "invoice_id", "payment_date", "amount"])
    print(f"Wrote {len(orders)} orders, {len(invoices)} invoices, {len(payments)} payments to {out}/")


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
