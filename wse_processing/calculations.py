"""Core calculations for water surface elevation processing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


GRAVITY = 9.80665  # m/s^2
PSI_TO_PASCAL = 6894.757293168
KPA_TO_PASCAL = 1000.0


@dataclass
class ProcessingConfig:
    reference_datum: float
    fluid_density: float = 1000.0  # kg/m^3
    pressure_units: str = "kPa"  # "kPa" or "psi"
    timezone: Optional[str] = None
    merge_tolerance: str = "15min"


class ColumnNames:
    TIMESTAMP = "timestamp"
    WATER_PRESSURE = "water_pressure"
    BARO_PRESSURE = "barometric_pressure"
    GAUGE_PRESSURE = "gauge_pressure"
    WATER_TEMPERATURE = "water_temperature"
    AIR_TEMPERATURE = "air_temperature"
    WATER_DEPTH = "water_depth_m"
    WSE = "water_surface_elevation"


PRESSURE_UNITS = {"kpa", "psi"}


def _to_pascal(series: pd.Series, units: str) -> pd.Series:
    units = units.lower()
    if units == "kpa":
        return series * KPA_TO_PASCAL
    if units == "psi":
        return series * PSI_TO_PASCAL
    raise ValueError(f"Unsupported pressure unit: {units}")


def gauge_to_depth(gauge_pressure: pd.Series, *, density: float, units: str) -> pd.Series:
    """Convert gauge pressure to depth in metres."""
    pascal = _to_pascal(gauge_pressure, units)
    depth_m = pascal / (density * GRAVITY)
    return depth_m


def compute_wse(
    water: pd.DataFrame,
    barometric: pd.DataFrame,
    config: ProcessingConfig,
    *,
    water_pressure_col: str,
    baro_pressure_col: str,
    water_temp_col: Optional[str] = None,
    baro_temp_col: Optional[str] = None,
    timestamp_col_water: str = "Date Time",
    timestamp_col_baro: str = "Date Time",
) -> pd.DataFrame:
    """Merge water and barometric datasets and compute WSE."""
    df_water = water.copy()
    df_baro = barometric.copy()

    for df, timestamp_col in ((df_water, timestamp_col_water), (df_baro, timestamp_col_baro)):
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
        if config.timezone:
            df[timestamp_col] = df[timestamp_col].dt.tz_localize(config.timezone, nonexistent="shift_forward", ambiguous="NaT", errors="coerce")
        df.sort_values(timestamp_col, inplace=True)

    merged = pd.merge_asof(
        df_water,
        df_baro[[timestamp_col_baro, baro_pressure_col] + ([baro_temp_col] if baro_temp_col else [])],
        left_on=timestamp_col_water,
        right_on=timestamp_col_baro,
        direction="nearest",
        tolerance=pd.to_timedelta(config.merge_tolerance),
    )

    merged.rename(columns={
        timestamp_col_water: ColumnNames.TIMESTAMP,
        water_pressure_col: ColumnNames.WATER_PRESSURE,
        baro_pressure_col: ColumnNames.BARO_PRESSURE,
    }, inplace=True)

    if water_temp_col:
        merged.rename(columns={water_temp_col: ColumnNames.WATER_TEMPERATURE}, inplace=True)
    if baro_temp_col:
        merged.rename(columns={baro_temp_col: ColumnNames.AIR_TEMPERATURE}, inplace=True)

    merged = merged.dropna(subset=[ColumnNames.TIMESTAMP, ColumnNames.WATER_PRESSURE, ColumnNames.BARO_PRESSURE])

    merged[ColumnNames.GAUGE_PRESSURE] = merged[ColumnNames.WATER_PRESSURE] - merged[ColumnNames.BARO_PRESSURE]
    merged[ColumnNames.WATER_DEPTH] = gauge_to_depth(
        merged[ColumnNames.GAUGE_PRESSURE], density=config.fluid_density, units=config.pressure_units
    )
    merged[ColumnNames.WSE] = config.reference_datum + merged[ColumnNames.WATER_DEPTH]

    return merged


def summarise_timeseries(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return daily and weekly aggregates for WSE and temperatures."""
    index = pd.DatetimeIndex(df[ColumnNames.TIMESTAMP])
    resampled = df.set_index(index)

    daily = resampled.resample("1D").mean(numeric_only=True)
    weekly = resampled.resample("1W").mean(numeric_only=True)

    return daily, weekly
