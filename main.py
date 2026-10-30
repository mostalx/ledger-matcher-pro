"""
Run the reconciliation from the command line.

    python main.py                          # uses data/ and writes report.xlsx
    python main.py --data data --out my_report.xlsx --as-of 2026-04-15
"""
import argparse
import os
from datetime import date

from matcher import load_data, run_all_checks, summarize
from report import write_report


def main():
    parser = argparse.ArgumentParser(description="Match orders, invoices and payments.")
    parser.add_argument("--data", default="data", help="folder with the three CSV files")
    parser.add_argument("--out", default="report.xlsx", help="Excel file to write")
    parser.add_argument("--as-of", default=str(date.today()),
                        help="date used to decide what is overdue (YYYY-MM-DD)")
    args = parser.parse_args()

    orders, invoices, payments = load_data(args.data)
    print(f"Loaded {len(orders)} orders, {len(invoices)} invoices, {len(payments)} payments")

    issues = run_all_checks(orders, invoices, payments, args.as_of)
    summary = summarize(issues)

    if issues.empty:
        print("Everything matches. Nothing to report.")
    else:
        print(f"\nFound {len(issues)} issues:\n")
        print(summary.to_string(index=False))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_report(issues, summary, args.out)
    print(f"\nReport saved to {args.out}")


if __name__ == "__main__":
    main()
