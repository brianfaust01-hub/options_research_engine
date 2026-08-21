"""In-memory timing and request-attribution metrics for one scan run."""

from __future__ import annotations

from collections import Counter
from threading import Lock


_lock = Lock()
_counts: Counter = Counter()
_durations: Counter = Counter()


def reset_pipeline_metrics() -> None:
    with _lock:
        _counts.clear()
        _durations.clear()


def record_count(name: str, amount: int = 1) -> None:
    with _lock:
        _counts[name] += amount


def record_duration(name: str, seconds: float) -> None:
    with _lock:
        _durations[name] += seconds


def get_pipeline_metrics() -> dict:
    with _lock:
        return {
            "counts": dict(_counts),
            "durations_seconds": {
                key: round(value, 3)
                for key, value in _durations.items()
            },
        }
