# WSE QAQC Toolkit

This repository contains a Streamlit application for turning raw HOBO logger
exports into barometrically compensated water surface elevation (WSE) time
series. The tool is designed around a drag-and-drop workflow: upload your
in-water pressure logger export alongside the matching barometric logger
export, optionally add an existing combined dataset, and download the merged
and quality-controlled dataset complete with daily and weekly statistics.

## Key features

- Accepts HOBO `.hobo`, CSV, TXT, and Excel exports for both water and
  barometric loggers.
- Automatically merges the two data streams using a configurable tolerance and
  computes gauge pressure, water depth, and WSE relative to a user-specified
  datum.
- Highlights potential logger shifts based on sudden depth changes and optional
  temperature exceedances.
- Produces daily and weekly mean summaries for WSE and temperature.
- Provides interactive charts and a one-click Excel export containing the raw
  merged timeseries, QA/QC flags, and summary tables.

## Getting started

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Launch the Streamlit app:

   ```bash
   streamlit run app/app.py
   ```

3. Follow the steps in the interface to upload your logger exports, configure
   processing parameters, review QA/QC results, and download the consolidated
   Excel report.

## Configuration options

The sidebar exposes parameters to tailor the processing pipeline:

- **Reference datum elevation** – the known elevation at which water depth is
  zero. This sets the baseline for WSE calculations.
- **Fluid density** – defaults to 1000 kg/m³ (freshwater) but can be adjusted
  for site-specific conditions.
- **Pressure units** – select whether the logger values are stored in kPa or
  psi so that gauge pressure is converted correctly into depth.
- **Merge tolerance** – maximum allowable time separation when pairing water
  and barometric observations.
- **Timezone** – optional Olson timezone identifier to localise timestamps.
- **QA/QC thresholds** – customise the depth change threshold used to flag
  potential logger shifts and enable an optional temperature exceedance alert.

## Project structure

```
app/                Streamlit user interface
wse_processing/     Core data loading, calculation, QA/QC, and export helpers
requirements.txt    Python dependencies
```

Feel free to adapt the processing rules in `wse_processing/` to match site
specific QA/QC criteria or additional summary products.
