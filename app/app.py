from __future__ import annotations

import io
from pathlib import Path
from typing import Optional
import sys

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from wse_processing.calculations import ColumnNames, ProcessingConfig, compute_wse, summarise_timeseries
from wse_processing.export import export_to_excel
from wse_processing.io import ParsedDataset, load_dataset
from wse_processing.qaqc import QAQCConfig, flag_shifts, flag_temperature_outliers

st.set_page_config(page_title="WSE QAQC Toolkit", layout="wide")


def _upload_file(label: str) -> Optional[ParsedDataset]:
    uploaded = st.file_uploader(label, type=["hobo", "csv", "txt", "xlsx", "xls"], accept_multiple_files=False)
    if not uploaded:
        return None
    data = io.BytesIO(uploaded.getvalue())
    dataset = load_dataset(uploaded.name, data, Path(uploaded.name).suffix)
    st.success(f"Loaded {dataset.name} with {len(dataset.data)} rows")
    return dataset


def _column_selector(dataset: ParsedDataset, label: str, default: Optional[str]) -> Optional[str]:
    if not dataset:
        return None
    options = list(dataset.data.columns)
    if not options:
        return None
    return st.selectbox(label, options, index=options.index(default) if default in options else 0)


def main() -> None:
    st.title("SRWC")
    st.subheader("Water Surface Elevation QAQC")
    st.write(
        "Upload HOBO exports or CSV/Excel files for both your in-water and in-air sensors. "
        "The app will merge them, compute barometrically compensated water surface elevations, "
        "perform QA/QC checks, and summarise temperatures and WSE as daily and weekly averages."
    )

    with st.sidebar:
        st.header("Processing Settings")
        reference_datum = st.number_input(
            "Reference datum elevation",
            value=100.0,
            help="Elevation of water surface when depth is zero.",
        )
        fluid_density = st.number_input(
            "Fluid density (kg/m³)",
            value=1000.0,
            help="Use 1000 for freshwater, adjust if needed.",
        )
        pressure_units = st.selectbox("Pressure units", ["kPa", "psi"], index=0)
        merge_tol = st.text_input(
            "Merge tolerance",
            value="15min",
            help="Maximum time difference when matching water and air readings.",
        )
        timezone = st.text_input(
            "Timezone (optional)",
            value="",
            help="TZ identifier e.g. America/Los_Angeles",
        ) or None

        st.header("QA/QC Settings")
        shift_threshold = st.number_input(
            "Depth shift threshold (m)",
            value=0.15,
            min_value=0.0,
            step=0.01,
        )
        temp_threshold = st.number_input(
            "Temperature alert threshold (°C)",
            value=35.0,
            min_value=0.0,
            step=0.5,
        )
        enable_temp_flag = st.checkbox("Enable temperature QA/QC", value=False)

    st.subheader("1. Upload water logger export")
    water_dataset = _upload_file("Water logger file")

    st.subheader("2. Upload barometric logger export")
    baro_dataset = _upload_file("Barometric logger file")

    st.subheader("3. (Optional) Upload existing combined dataset")
    history_file = st.file_uploader(
        "Historical dataset (Excel/CSV)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=False,
    )
    history_df: Optional[pd.DataFrame] = None
    if history_file is not None:
        if history_file.name.endswith(".csv"):
            history_df = pd.read_csv(history_file)
        else:
            history_df = pd.read_excel(history_file)
        st.info(f"Loaded historical dataset with {len(history_df)} rows")

    if not (water_dataset and baro_dataset):
        st.stop()

    st.subheader("4. Map columns")
    col1, col2 = st.columns(2)
    with col1:
        water_time = _column_selector(water_dataset, "Water timestamp column", water_dataset.timestamp_column)
        water_pressure = _column_selector(water_dataset, "Water pressure column", water_dataset.pressure_column)
        water_temp = _column_selector(water_dataset, "Water temperature column", water_dataset.temperature_column)
    with col2:
        baro_time = _column_selector(baro_dataset, "Barometric timestamp column", baro_dataset.timestamp_column)
        baro_pressure = _column_selector(baro_dataset, "Barometric pressure column", baro_dataset.pressure_column)
        baro_temp = _column_selector(baro_dataset, "Barometric temperature column", baro_dataset.temperature_column)

    if not (water_time and water_pressure and baro_time and baro_pressure):
        st.error("Please ensure timestamps and pressure columns are selected for both datasets.")
        st.stop()

    config = ProcessingConfig(
        reference_datum=reference_datum,
        fluid_density=fluid_density,
        pressure_units=pressure_units,
        timezone=timezone,
        merge_tolerance=merge_tol,
    )

    qaqc_config = QAQCConfig(
        shift_threshold=shift_threshold,
        temperature_threshold=temp_threshold if enable_temp_flag else None,
    )

    with st.spinner("Computing water surface elevation…"):
        merged = compute_wse(
            water_dataset.data,
            baro_dataset.data,
            config,
            water_pressure_col=water_pressure,
            baro_pressure_col=baro_pressure,
            water_temp_col=water_temp,
            baro_temp_col=baro_temp,
            timestamp_col_water=water_time,
            timestamp_col_baro=baro_time,
        )

    if history_df is not None and not history_df.empty:
        merged = pd.concat([history_df, merged], ignore_index=True)
        merged = merged.drop_duplicates(subset=[ColumnNames.TIMESTAMP]).sort_values(ColumnNames.TIMESTAMP)
        st.success("Merged with historical dataset.")

    st.subheader("5. QA/QC summary")
    flagged_shifts = flag_shifts(merged, qaqc_config)
    if not flagged_shifts.empty:
        st.warning("Potential depth shifts detected")
        st.dataframe(flagged_shifts[[ColumnNames.TIMESTAMP, ColumnNames.WATER_DEPTH, "depth_change"]].head(200))
    else:
        st.success("No depth shifts detected above threshold")

    if enable_temp_flag:
        flagged_temp = flag_temperature_outliers(merged, qaqc_config)
        if not flagged_temp.empty:
            st.warning("Temperature exceedances found")
            st.dataframe(flagged_temp[[ColumnNames.TIMESTAMP, ColumnNames.WATER_TEMPERATURE, "temperature_excess"]].head(200))
        else:
            st.success("No temperature exceedances found")

    st.subheader("6. Visualisation")
    chart_cols = st.multiselect(
        "Select series to plot",
        [ColumnNames.WSE, ColumnNames.WATER_DEPTH, ColumnNames.WATER_TEMPERATURE, ColumnNames.AIR_TEMPERATURE],
        default=[ColumnNames.WSE, ColumnNames.WATER_TEMPERATURE],
    )
    if chart_cols:
        st.line_chart(merged.set_index(ColumnNames.TIMESTAMP)[chart_cols])

    st.subheader("7. Daily & weekly summaries")
    daily, weekly = summarise_timeseries(merged)
    st.write("Daily averages")
    st.dataframe(daily.head(50))
    st.write("Weekly averages")
    st.dataframe(weekly.head(50))

    st.subheader("8. Download results")
    output_buffer = export_to_excel(
        {
            "combined_timeseries": merged,
            "daily_summary": daily,
            "weekly_summary": weekly,
            "qaqc_depth_flags": flagged_shifts,
            "qaqc_temperature_flags": flag_temperature_outliers(merged, qaqc_config)
            if enable_temp_flag
            else pd.DataFrame(),
        }
    )
    st.download_button(
        "Download Excel report",
        data=output_buffer,
        file_name="wse_qaqc_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
