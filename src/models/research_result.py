"""
Project Stonks
Research Result Model

Defines the standard output format for all research modules.
"""

from dataclasses import dataclass


@dataclass
class ResearchResult:
    module: str
    signal: str
    confidence: int
    trend: int
    momentum: int
    risk: int
    liquidity: int
    reasons: list[str]