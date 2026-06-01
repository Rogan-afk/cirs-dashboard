import sqlite3
import pandas as pd
import numpy as np
from scipy.stats import zscore
import os

def main():
    db_path = 'cargo_tracking.db'

    # Check if DB exists to prevent confusing pandas SQL errors if missing
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found in the current directory.")
        return

    # 1. Load all rows from shipments into a pandas DataFrame
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM shipments"
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("The shipments table is empty. Exiting.")
        conn.close()
        return

    # 2. Compute three binary flag columns

    # ==========================================
    # FLAG A -- z_score_flag & dwell_zscore
    # ==========================================
    def calculate_safe_zscore(x):
        # If carrier has only 1 shipment, std is 0 and z-score is undefined
        if len(x) <= 1:
            return np.zeros(len(x))
        # Handle cases where all values are identical (std=0) causing NaNs
        z = zscore(x, ddof=0)
        return np.nan_to_num(z, nan=0.0)

    # Compute z-score per carrier group
    df['dwell_zscore'] = df.groupby('carrier_id')['dwell_time_hours'].transform(calculate_safe_zscore)

    # Flag if abs(z-score) > 2.0
    df['z_score_flag'] = np.where(df['dwell_zscore'].abs() > 2.0, 1, 0)

    # ==========================================
    # FLAG B -- iqr_flag
    # ==========================================
    # Compute global Q1, Q3, and IQR for freight_value_usd
    Q1 = df['freight_value_usd'].quantile(0.25)
    Q3 = df['freight_value_usd'].quantile(0.75)
    IQR = Q3 - Q1

    # Flag if value > Q3 + 1.5*IQR AND status is IN_TRANSIT or UNRECEIVED
    df['iqr_flag'] = np.where(
        (df['freight_value_usd'] > (Q3 + 1.5 * IQR)) &
        (df['status'].isin(['UNRECEIVED', 'IN_TRANSIT'])),
        1, 0
    )

    # ==========================================
    # FLAG C -- carrier_risk_flag & carrier_unreceived_rate
    # ==========================================
    # Compute unreceived_rate per carrier_id
    carrier_stats = df.groupby('carrier_id').agg(
        total_shipments=('shipment_id', 'count'),
        unreceived_count=('status', lambda x: (x == 'UNRECEIVED').sum())
    ).reset_index()

    carrier_stats['carrier_unreceived_rate'] = (
        carrier_stats['unreceived_count'] / carrier_stats['total_shipments']
    )

    # Compute mean and std across all carriers
    mean_rate = carrier_stats['carrier_unreceived_rate'].mean()
    std_rate = carrier_stats['carrier_unreceived_rate'].std(ddof=1)
    if pd.isna(std_rate):
        std_rate = 0.0

    threshold_rate = mean_rate + 1.5 * std_rate

    # Identify risky carriers
    carrier_stats['carrier_risk_flag'] = np.where(
        carrier_stats['carrier_unreceived_rate'] > threshold_rate, 1, 0
    )

    # Join rates and flags back to the main dataframe
    df = df.merge(
        carrier_stats[['carrier_id', 'carrier_unreceived_rate', 'carrier_risk_flag']],
        on='carrier_id',
        how='left'
    )

    # 3. Compute risk_score (Noise Suppression Update)
    # We tie heavy points to flags to prevent normal variances from stacking to 40+ points.
    
    # Dwell: 40 pts if flagged, else capped at 15
    dwell_component = np.where(
        df['z_score_flag'] == 1,
        40,
        np.minimum(df['dwell_zscore'].abs() * 7.5, 15)
    )

    # Value: 30 pts if flagged, else capped at 10
    value_component = np.where(
        df['iqr_flag'] == 1,
        30,
        np.minimum((df['freight_value_usd'] / 60000.0) * 10, 10)
    )

    # Carrier: 30 pts if flagged, else capped at 10 (normalized by max rate)
    max_unreceived_rate = df['carrier_unreceived_rate'].max()
    if max_unreceived_rate > 0:
        base_carrier = (df['carrier_unreceived_rate'] / max_unreceived_rate) * 10
    else:
        base_carrier = 0.0

    carrier_component = np.where(
        df['carrier_risk_flag'] == 1,
        30,
        base_carrier
    )

    # Sum components, clip between 0 and 100, and round to 2 decimal places
    df['risk_score'] = np.clip(
        dwell_component + value_component + carrier_component, 0, 100
    ).round(2)

    # 4. Assign risk_tier based on risk_score
    conditions = [
        df['risk_score'] >= 60,
        df['risk_score'] >= 40,
        df['risk_score'] >= 20
    ]
    choices = ['CRITICAL', 'HIGH', 'MEDIUM']
    df['risk_tier'] = np.select(conditions, choices, default='LOW')

    # 5. Create flagged_shipments table in cargo_tracking.db
    df.to_sql('flagged_shipments', conn, if_exists='replace', index=False)
    conn.close()

    # 6. Summary Output
    tier_counts = df['risk_tier'].value_counts()

    print("=== Anomaly Detection Summary ===")
    print(f"CRITICAL: {tier_counts.get('CRITICAL', 0)} shipments")
    print(f"HIGH:     {tier_counts.get('HIGH', 0)} shipments")
    print(f"MEDIUM:   {tier_counts.get('MEDIUM', 0)} shipments")
    print(f"LOW:      {tier_counts.get('LOW', 0)} shipments")
    print("--- Precision Check ---")

    def calculate_precision(tier_name):
        tier_df = df[df['risk_tier'] == tier_name]
        if len(tier_df) == 0:
            return 0.0
        return (tier_df['is_anomaly'].sum() / len(tier_df)) * 100

    crit_precision = calculate_precision('CRITICAL')
    high_precision = calculate_precision('HIGH')

    print(f"Of CRITICAL-flagged shipments, {crit_precision:.1f}% have is_anomaly=1 (ground truth)")
    print(f"Of HIGH-flagged shipments, {high_precision:.1f}% have is_anomaly=1")

if __name__ == "__main__":
    main()