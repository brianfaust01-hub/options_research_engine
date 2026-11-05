"""Canonical normal scan entry point, with separately versioned risk controls."""
import weekly_scan
from production_risk_controls import arbitrate_with_oil_guard


def main():
    # Replace this caller's reference only. Do not modify the allocator module
    # imported independently by the frozen config comparison or SPY processes.
    original = weekly_scan.arbitrate_portfolio
    def guarded(*args, **kwargs):
        return arbitrate_with_oil_guard(original, *args, **kwargs)
    weekly_scan.arbitrate_portfolio = guarded
    try:
        weekly_scan.main()
    finally:
        weekly_scan.arbitrate_portfolio = original


if __name__ == '__main__':
    main()
