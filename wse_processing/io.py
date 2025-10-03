"""Data ingestion helpers for WSE processing app."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Iterable, Optional

import pandas as pd


@dataclass
class ParsedDataset:
    """Container holding a parsed time-series dataset."""

    name: str
    data: pd.DataFrame
    timestamp_column: str
    pressure_column: Optional[str]
    temperature_column: Optional[str]


def _decode_bytes(data: BytesIO) -> str:
    """Decode bytes into text using a couple of sensible fallbacks."""
    raw = data.getvalue()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort – ignore errors but keep bytes that can be decoded
    return raw.decode("utf-8", errors="ignore")


def _find_header_line(lines: Iterable[str]) -> int:
    """Return the index of the header row in a HOBO export.

    The HOBO export format typically contains metadata lines followed by a row
    where the header values (e.g. ``Date Time``) start.
    """
    for idx, line in enumerate(lines):
        normalized = line.lower()
        if "date" in normalized and "time" in normalized:
            return idx
    return 0


def read_hobo_file(data: BytesIO) -> pd.DataFrame:
    """Parse a HOBO ``.hobo`` file into a DataFrame.

    The function attempts to auto-detect the header line and delimiter. It is
    resilient to metadata blocks at the top of the file and to either comma or
    tab separated data sections.
    """
    text = _decode_bytes(data)
    lines = text.splitlines()
    header_idx = _find_header_line(lines)
    content = "\n".join(lines[header_idx:])

    for sep in (None, ",", "\t", ";"):
        try:
            df = pd.read_csv(StringIO(content), sep=sep, engine="python")
        except Exception:  # pragma: no cover - pandas raises many variants
            continue
        if not df.empty:
            return df
    raise ValueError("Unable to parse HOBO file – please export as CSV/Excel.")


def read_delimited(data: BytesIO, **kwargs) -> pd.DataFrame:
    return pd.read_csv(BytesIO(data.getvalue()), **kwargs)


def read_excel(data: BytesIO, **kwargs) -> pd.DataFrame:
    return pd.read_excel(BytesIO(data.getvalue()), **kwargs)


def load_dataset(name: str, data: BytesIO, suffix: str) -> ParsedDataset:
    """Load an uploaded file into a ParsedDataset."""
    suffix = suffix.lower()
    if suffix == ".hobo":
        df = read_hobo_file(data)
    elif suffix in {".csv", ".txt"}:
        df = read_delimited(data)
    elif suffix in {".xls", ".xlsx"}:
        df = read_excel(data)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    df.columns = [col.strip() for col in df.columns]

    timestamp_col = _find_column(df.columns, ["date time", "datetime", "timestamp", "time"])
    pressure_col = _find_column(df.columns, ["pressure", "abs pressure", "water pressure", "kpa", "psi"])
    temp_col = _find_column(df.columns, ["temp", "temperature"])

    return ParsedDataset(
        name=name,
        data=df,
        timestamp_column=timestamp_col,
        pressure_column=pressure_col,
        temperature_column=temp_col,
    )


def _find_column(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    lowered = {col.lower(): col for col in columns}
    for candidate in candidates:
        for key, original in lowered.items():
            if candidate in key:
                return original
    return None
