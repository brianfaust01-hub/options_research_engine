"""Canonical normal scan entry point, with separately versioned risk controls."""
import weekly_scan
from production_risk_controls import arbitrate_with_oil_guard
from opening_hour import arbitrate_with_opening_hour


def main():
    # Replace this caller's reference only. Do not modify the allocator module
    # imported independently by the frozen config comparison or SPY processes.
    original = weekly_scan.arbitrate_portfolio
    def guarded(*args, **kwargs):
        def with_oil(*inner_args, **inner_kwargs):
            return arbitrate_with_oil_guard(original, *inner_args, **inner_kwargs)
        return arbitrate_with_opening_hour(with_oil, *args, **kwargs)
    weekly_scan.arbitrate_portfolio = guarded
    try:
        weekly_scan.main()
    finally:
        weekly_scan.arbitrate_portfolio = original


if __name__ == '__main__':
    main()
