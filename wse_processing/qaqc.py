"""Quality control helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .calculations import ColumnNames


@dataclass
class QAQCConfig:
    shift_threshold: float = 0.15  # metres
    temperature_threshold: Optional[float] = None  # degrees above which to flag


def flag_shifts(df: pd.DataFrame, config: QAQCConfig) -> pd.DataFrame:
    """Return rows flagged for step changes in water depth."""
    if ColumnNames.WATER_DEPTH not in df:
        raise KeyError("water depth column missing from dataframe")

    depth = df[ColumnNames.WATER_DEPTH]
    delta = depth.diff().abs()
    flags = delta > config.shift_threshold
    flagged = df.loc[flags].copy()
    flagged["depth_change"] = delta[flags]
    return flagged


def flag_temperature_outliers(df: pd.DataFrame, config: QAQCConfig) -> pd.DataFrame:
    """Flag suspiciously high temperatures if a threshold is provided."""
    if not config.temperature_threshold or ColumnNames.WATER_TEMPERATURE not in df:
        return pd.DataFrame(columns=df.columns)

    mask = df[ColumnNames.WATER_TEMPERATURE] > config.temperature_threshold
    flagged = df.loc[mask].copy()
    flagged["temperature_excess"] = (
        df.loc[mask, ColumnNames.WATER_TEMPERATURE] - config.temperature_threshold
    )
    return flagged
