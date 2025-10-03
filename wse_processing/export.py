"""Utilities for exporting processed datasets."""
from __future__ import annotations

from io import BytesIO
from typing import Dict

import pandas as pd


def export_to_excel(sheets: Dict[str, pd.DataFrame]) -> BytesIO:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31])
    buffer.seek(0)
    return buffer
