import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from matcher import run_all_checks  # noqa: E402

AS_OF = "2026-04-15"


def make(orders, invoices, payments):
    o = pd.DataFrame(orders, columns=["order_id", "customer", "order_date", "amount"])
    i = pd.DataFrame(invoices, columns=["invoice_id", "order_id", "invoice_date", "amount"])
    p = pd.DataFrame(payments, columns=["payment_id", "invoice_id", "payment_date", "amount"])
    o["order_date"] = pd.to_datetime(o["order_date"])
    i["invoice_date"] = pd.to_datetime(i["invoice_date"])
    p["payment_date"] = pd.to_datetime(p["payment_date"])
    return o, i, p


def types(issues):
    return sorted(issues["issue_type"].tolist())


def test_clean_flow_has_no_issues():
    o, i, p = make(
        [("ORD-1", "A", "2026-01-10", 100.0)],
        [("INV-1", "ORD-1", "2026-01-12", 100.0)],
        [("PAY-1", "INV-1", "2026-02-01", 100.0)])
    assert run_all_checks(o, i, p, AS_OF).empty


def test_unbilled_order():
    o, i, p = make([("ORD-1", "A", "2026-01-10", 100.0)], [], [])
    assert types(run_all_checks(o, i, p, AS_OF)) == ["Unbilled order"]


def test_amount_mismatch():
    o, i, p = make(
        [("ORD-1", "A", "2026-01-10", 100.0)],
        [("INV-1", "ORD-1", "2026-01-12", 110.0)],
        [("PAY-1", "INV-1", "2026-02-01", 110.0)])
    result = run_all_checks(o, i, p, AS_OF)
    assert types(result) == ["Invoice amount mismatch"]
    assert result.loc[0, "difference"] == 10.0


def test_duplicate_invoice_is_reported_once():
    o, i, p = make(
        [("ORD-1", "A", "2026-01-10", 100.0)],
        [("INV-1", "ORD-1", "2026-01-12", 100.0),
         ("INV-2", "ORD-1", "2026-01-14", 100.0)],
        [("PAY-1", "INV-1", "2026-02-01", 100.0)])
    result = run_all_checks(o, i, p, AS_OF)
    assert types(result) == ["Duplicate invoice"]
    assert result.loc[0, "invoice_id"] == "INV-2"


def test_overdue_only_after_payment_terms():
    o, i, p = make(
        [("ORD-1", "A", "2026-04-01", 100.0), ("ORD-2", "B", "2026-01-01", 100.0)],
        [("INV-1", "ORD-1", "2026-04-02", 100.0), ("INV-2", "ORD-2", "2026-01-02", 100.0)],
        [])
    result = run_all_checks(o, i, p, AS_OF)
    assert types(result) == ["Overdue invoice"]
    assert result.loc[0, "invoice_id"] == "INV-2"


def test_short_and_over_payment():
    o, i, p = make(
        [("ORD-1", "A", "2026-01-10", 100.0), ("ORD-2", "B", "2026-01-10", 200.0)],
        [("INV-1", "ORD-1", "2026-01-12", 100.0), ("INV-2", "ORD-2", "2026-01-12", 200.0)],
        [("PAY-1", "INV-1", "2026-02-01", 90.0), ("PAY-2", "INV-2", "2026-02-01", 250.0)])
    assert types(run_all_checks(o, i, p, AS_OF)) == ["Overpayment", "Short payment"]


def test_orphans():
    o, i, p = make(
        [("ORD-1", "A", "2026-01-10", 100.0)],
        [("INV-1", "ORD-1", "2026-01-12", 100.0), ("INV-9", "ORD-404", "2026-01-12", 50.0)],
        [("PAY-1", "INV-1", "2026-02-01", 100.0), ("PAY-2", "INV-777", "2026-02-01", 30.0)])
    assert types(run_all_checks(o, i, p, AS_OF)) == ["Invoice without order", "Payment without invoice"]


def test_two_partial_payments_add_up():
    o, i, p = make(
        [("ORD-1", "A", "2026-01-10", 100.0)],
        [("INV-1", "ORD-1", "2026-01-12", 100.0)],
        [("PAY-1", "INV-1", "2026-02-01", 60.0), ("PAY-2", "INV-1", "2026-02-10", 40.0)])
    assert run_all_checks(o, i, p, AS_OF).empty
