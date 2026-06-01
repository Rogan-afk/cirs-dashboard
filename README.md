# CIRS | Cargo Integrity & Recovery Dashboard

The Cargo Integrity & Recovery Services (CIRS) dashboard is an analytical risk mitigation platform designed to identify high-exposure transit lanes and systemic carrier failures. By applying statistical process control to logistics data, the system isolates dwell time anomalies and high-value freight vulnerabilities before losses occur. This tool enables supply chain operators to transition from reactive claims management to proactive freight recovery.

**Live Demo:** [https://cirs-dashboard.onrender.com](https://cirs-dashboard.onrender.com)

## Features
* **Anomaly Detection Engine:** Applies Z-score and IQR methodologies to flag dwell time deviations and value-based risk.
* **Weighted Risk Scoring:** Assigns a 0–100 composite risk score and tier (CRITICAL to LOW) to prioritize investigations.
* **Carrier Scorecarding:** Evaluates vendor compliance by tracking historical unreceived rates against network benchmarks.
* **Corridor Exposure:** Maps specific transit lanes exhibiting statistically significant theft or loss probabilities.
* **Case Management:** Provides an interactive lookup interface for granular, shipment-level operational ledgers.

**Tech Stack:** Python, SQLite, Pandas, NumPy, SciPy, Plotly, Streamlit, Render

## Architecture Map
```text
CIRS-Dashboard/
├── app.py                  # Streamlit frontend & UI routing
├── anomaly_detection.py    # Statistical scoring & risk tiering engine
├── generate_data.py        # Synthetic supply chain state generation
├── queries.py              # Analytical SQL queries for BI extraction
└── cargo_tracking.db       # Local SQLite data vault
```

## How It Works
Data Generation: Simulates a live logistics network of 50,000 shipments across 12 carriers, injecting realistic in-transit loss scenarios and systemic delays.

Detection Engine: Processes the database, flagging records using standard deviations and IQR control limits to generate weighted threat profiles.

Dashboard Execution: Surfaces intelligence through a 5-page interactive UI, allowing operators to filter, isolate, and export critical cases.

## Run Locally
```bash
pip install -r requirements.txt
python generate_data.py
python anomaly_detection.py
streamlit run app.py
```
