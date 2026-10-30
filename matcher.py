"""
The reconciliation logic.

Three tables go in (orders, invoices, payments) and one table of problems
comes out. Every check returns a list of "issue" rows with the same columns,
so they can be stacked together at the end.

The flow I'm checking is:  order -> invoice -> payment
"""
import pandas as pd

AMOUNT_TOLERANCE = 0.01     # differences smaller than 1 cent are rounding noise
PAYMENT_TERMS_DAYS = 30     # an invoice is overdue after this many days

ISSUE_COLUMNS = ["issue_type", "order_id", "invoice_id", "payment_id",
                 "expected", "actual", "difference", "note"]


def load_data(folder):
    orders = pd.read_csv(f"{folder}/orders.csv", parse_dates=["order_date"])
    invoices = pd.read_csv(f"{folder}/invoices.csv", parse_dates=["invoice_date"])
    payments = pd.read_csv(f"{folder}/payments.csv", parse_dates=["payment_date"])
    return orders, invoices, payments


def _issue(issue_type, order_id=None, invoice_id=None, payment_id=None,
           expected=None, actual=None, note=""):
    difference = None
    if expected is not None and actual is not None:
        difference = round(actual - expected, 2)
    return {
        "issue_type": issue_type,
        "order_id": order_id,
        "invoice_id": invoice_id,
        "payment_id": payment_id,
        "expected": expected,
        "actual": actual,
        "difference": difference,
        "note": note,
    }


def first_invoice_per_order(invoices):
    """If an order has several invoices, the earliest one is the 'real' one.
    The rest are handled by the duplicate check, so other checks ignore them
    (otherwise one mistake would be reported three times)."""
    ordered = invoices.sort_values(["invoice_date", "invoice_id"])
    return ordered.drop_duplicates(subset="order_id", keep="first")


# ---------- order -> invoice ----------

def find_unbilled_orders(orders, invoices):
    billed = set(invoices["order_id"])
    issues = []
    for row in orders.itertuples():
        if row.order_id not in billed:
            issues.append(_issue(
                "Unbilled order", order_id=row.order_id,
                expected=row.amount, actual=0.0,
                note=f"{row.customer} was never invoiced"))
    return issues


def find_orphan_invoices(orders, invoices):
    known = set(orders["order_id"])
    issues = []
    for row in invoices.itertuples():
        if row.order_id not in known:
            issues.append(_issue(
                "Invoice without order", order_id=row.order_id,
                invoice_id=row.invoice_id, expected=0.0, actual=row.amount,
                note="No matching order found"))
    return issues


def find_duplicate_invoices(invoices):
    ordered = invoices.sort_values(["invoice_date", "invoice_id"])
    extras = ordered[ordered.duplicated(subset="order_id", keep="first")]
    issues = []
    for row in extras.itertuples():
        issues.append(_issue(
            "Duplicate invoice", order_id=row.order_id,
            invoice_id=row.invoice_id, expected=0.0, actual=row.amount,
            note="Order already has an earlier invoice"))
    return issues


def find_amount_mismatches(orders, valid_invoices):
    merged = valid_invoices.merge(orders, on="order_id", suffixes=("_inv", "_ord"))
    issues = []
    for row in merged.itertuples():
        if abs(row.amount_inv - row.amount_ord) > AMOUNT_TOLERANCE:
            issues.append(_issue(
                "Invoice amount mismatch", order_id=row.order_id,
                invoice_id=row.invoice_id,
                expected=row.amount_ord, actual=row.amount_inv,
                note="Invoice total differs from order total"))
    return issues


# ---------- invoice -> payment ----------

def find_unknown_payments(invoices, payments):
    known = set(invoices["invoice_id"])
    issues = []
    for row in payments.itertuples():
        if row.invoice_id not in known:
            issues.append(_issue(
                "Payment without invoice", invoice_id=row.invoice_id,
                payment_id=row.payment_id, expected=0.0, actual=row.amount,
                note="Money received but the invoice number does not exist"))
    return issues


def find_payment_problems(valid_invoices, payments, as_of):
    paid_so_far = payments.groupby("invoice_id")["amount"].sum()
    as_of = pd.Timestamp(as_of)
    issues = []
    for row in valid_invoices.itertuples():
        paid = round(float(paid_so_far.get(row.invoice_id, 0.0)), 2)
        age_in_days = (as_of - row.invoice_date).days

        if paid == 0:
            # an unpaid invoice is only a problem once the payment terms have passed
            if age_in_days > PAYMENT_TERMS_DAYS:
                issues.append(_issue(
                    "Overdue invoice", order_id=row.order_id,
                    invoice_id=row.invoice_id, expected=row.amount, actual=0.0,
                    note=f"No payment after {age_in_days} days"))
        elif paid < row.amount - AMOUNT_TOLERANCE:
            issues.append(_issue(
                "Short payment", order_id=row.order_id,
                invoice_id=row.invoice_id, expected=row.amount, actual=paid,
                note="Customer paid less than invoiced"))
        elif paid > row.amount + AMOUNT_TOLERANCE:
            issues.append(_issue(
                "Overpayment", order_id=row.order_id,
                invoice_id=row.invoice_id, expected=row.amount, actual=paid,
                note="Customer paid more than invoiced, refund or credit needed"))
    return issues


# ---------- put it all together ----------

def run_all_checks(orders, invoices, payments, as_of):
    # only invoices that belong to a real order go through the amount/payment checks
    linked = invoices[invoices["order_id"].isin(orders["order_id"])]
    valid_invoices = first_invoice_per_order(linked)

    issues = []
    issues += find_unbilled_orders(orders, invoices)
    issues += find_orphan_invoices(orders, invoices)
    issues += find_duplicate_invoices(invoices)
    issues += find_amount_mismatches(orders, valid_invoices)
    issues += find_unknown_payments(invoices, payments)
    issues += find_payment_problems(valid_invoices, payments, as_of)

    result = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    return result.sort_values(["issue_type", "order_id", "invoice_id"],
                              na_position="last").reset_index(drop=True)


def summarize(issues):
    """How many problems of each type, and roughly how much money is involved."""
    if issues.empty:
        return pd.DataFrame(columns=["issue_type", "count", "money_at_stake"])
    table = (issues.assign(money=issues["difference"].abs())
                   .groupby("issue_type")
                   .agg(count=("issue_type", "size"), money_at_stake=("money", "sum"))
                   .reset_index()
                   .sort_values("money_at_stake", ascending=False))
    table["money_at_stake"] = table["money_at_stake"].round(2)
    return table.reset_index(drop=True)
