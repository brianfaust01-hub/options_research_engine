"""
Project Stonks
Trade Journal
"""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import VERSION, CONFIG_VERSION


JOURNAL_PATH = Path("data/trade_journal.csv")


def log_trade_recommendation(trade):

    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    trade_dict = asdict(trade)

    trade_dict["RecommendationDate"] = datetime.now()
    trade_dict["ProjectVersion"] = VERSION
    trade_dict["ConfigVersion"] = CONFIG_VERSION

    df = pd.DataFrame([trade_dict])

    if JOURNAL_PATH.exists():
        existing = pd.read_csv(JOURNAL_PATH)

        df = pd.concat(
            [existing, df],
            ignore_index=True,
        )

    df.to_csv(
        JOURNAL_PATH,
        index=False,
    )