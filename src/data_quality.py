"""Hindsight observation provenance and data-quality classification.

This module does not repair historical evidence. It gives new and legacy
observations an honest, deterministic quality assessment so downstream
analysis can decide how each record may be used.
"""

from __future__ import annotations

import math
from typing import Any


OBSERVATION_SCHEMA_GENERATION = "4.0"

REQUIRED_HINDSIGHT_FIELDS = (
    "ResearchScore",
    "OpportunityScore",
    "BullishScore",
    "BearishScore",
    "DirectionalConviction",
)

FIELD_ALIASES = {
    "ResearchScore": (
        "ResearchScore",
        "research_score",
        "StrategyScore",
    ),
    "OpportunityScore": (
        "OpportunityScore",
        "opportunity_score",
    ),
    "BullishScore": (
        "BullishScore",
        "bullish_score",
    ),
    "BearishScore": (
        "BearishScore",
        "bearish_score",
    ),
    "DirectionalConviction": (
        "DirectionalConviction",
        "directional_conviction",
    ),
}


def is_missing(value: Any) -> bool:
    """Return True for absent values without depending on pandas."""

    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, float):
        return math.isnan(value)

    return False


def canonicalize_hindsight_fields(observation: dict) -> dict:
    """Return a copy with required hindsight fields under canonical names."""

    canonical = dict(observation)

    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            value = canonical.get(alias)

            if not is_missing(value):
                canonical[field] = value
                break

        else:
            canonical.setdefault(field, None)

    return canonical


def assess_observation(observation: dict) -> dict:
    """Classify an observation without changing or rejecting its evidence."""

    assessed = canonicalize_hindsight_fields(observation)
    missing_fields = [
        field
        for field in REQUIRED_HINDSIGHT_FIELDS
        if is_missing(assessed.get(field))
    ]

    assessed["ObservationSchemaGeneration"] = (
        OBSERVATION_SCHEMA_GENERATION
    )
    assessed.setdefault(
        "RecommendationTruthSource",
        "PROJECT_STONKS_SYSTEM",
    )
    assessed.setdefault(
        "ExecutionTruthSource",
        "PROJECT_STONKS_MODEL",
    )
    assessed.setdefault(
        "BrokerReconciliationStatus",
        "NOT_RECONCILED",
    )
    assessed["DataQualityStatus"] = (
        "COMPLETE" if not missing_fields else "PARTIAL"
    )
    assessed["DataQualityIssues"] = [
        f"MISSING_{field}"
        for field in missing_fields
    ]

    return assessed
