import sqlite3
import pandas as pd

# =============================================================================
# Query 1 — Carrier Risk Scorecard
# Detects: Aggregated carrier performance focusing on unreceived shipment rates 
# and average loss values.
# Why it matters: Identifying carriers with systemic failures or disproportionately
# high loss rates is the first step in auditing vendor compliance and mitigating 
# theft or systemic operational failures.
# =============================================================================
q1 = """
SELECT 
    carrier_id, 
    carrier_name, 
    COUNT(*) AS total_shipments,
    SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) AS unreceived_count,
    ROUND((SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 2) AS unreceived_rate_pct,
    ROUND(AVG(dwell_time_hours), 1) AS avg_dwell_time_hours,
    ROUND(AVG(CASE WHEN status = 'UNRECEIVED' THEN freight_value_usd ELSE NULL END), 2) AS avg_freight_value_unreceived
FROM shipments
GROUP BY 
    carrier_id, 
    carrier_name
ORDER BY 
    unreceived_rate_pct DESC;
"""

# =============================================================================
# Query 2 — High-Risk Lane Analysis
# Detects: Specific transit routes (lanes) that experience high rates of missing 
# cargo (>12%) or abnormally long wait times (>50 hours).
# Why it matters: Cargo is most vulnerable when it is stationary or traveling 
# through unsecured regions. Pinpointing high-risk lanes allows logistics teams 
# to reroute freight, mandate team drivers, or require secured parking.
# =============================================================================
q2 = """
SELECT 
    lane_id,
    COUNT(*) AS shipment_count,
    SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) AS unreceived_count,
    ROUND((SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 2) AS unreceived_rate_pct,
    ROUND(AVG(dwell_time_hours), 1) AS avg_dwell_time_hours,
    CASE 
        WHEN ROUND((SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 2) > 12 
          OR ROUND(AVG(dwell_time_hours), 1) > 50 THEN 'HIGH-RISK'
        ELSE 'NORMAL' 
    END AS risk_flag
FROM shipments
GROUP BY 
    lane_id
HAVING 
    COUNT(*) >= 10
ORDER BY 
    unreceived_rate_pct DESC;
"""

# =============================================================================
# Query 3 — Dwell Time Outlier Shipments
# Detects: Individual shipments where the dwell time is more than two standard 
# deviations above the carrier's historical average.
# Why it matters: Statistically abnormal dwell times are a leading indicator 
# of hijacked, abandoned, or heavily delayed cargo. Investigating these anomalies 
# can prevent spoilage or recover stolen goods.
# =============================================================================
q3 = """
WITH CarrierStats AS (
    SELECT 
        carrier_id,
        AVG(dwell_time_hours) AS avg_dwell,
        SQRT(AVG(dwell_time_hours * dwell_time_hours) - AVG(dwell_time_hours) * AVG(dwell_time_hours)) AS std_dwell
    FROM shipments
    GROUP BY carrier_id
)
SELECT 
    s.shipment_id,
    s.carrier_name,
    s.lane_id,
    s.dwell_time_hours,
    s.freight_value_usd,
    s.status,
    s.scheduled_arrival
FROM shipments s
JOIN CarrierStats cs ON s.carrier_id = cs.carrier_id
WHERE s.dwell_time_hours > (cs.avg_dwell + 2 * cs.std_dwell)
ORDER BY 
    s.dwell_time_hours DESC
LIMIT 100;
"""

# =============================================================================
# Query 4 — High-Value At-Risk Shipments
# Detects: Shipments currently in transit or missing with a declared freight 
# value exceeding $30,000 USD.
# Why it matters: Provides an actionable queue for security and operations 
# teams. High-value shipments naturally attract more risk and require priority 
# tracking and immediate intervention if delayed.
# =============================================================================
q4 = """
SELECT 
    shipment_id,
    carrier_name,
    lane_id,
    status,
    scheduled_arrival,
    actual_arrival,
    freight_value_usd,
    dwell_time_hours,
    stop_count
FROM shipments
WHERE status IN ('IN_TRANSIT', 'UNRECEIVED')
  AND freight_value_usd > 30000
ORDER BY 
    freight_value_usd DESC;
"""

# =============================================================================
# Query 5 — Monthly Loss Trend
# Detects: Macro-level trends indicating whether cargo loss (unreceived rate) 
# is increasing or decreasing month-over-month.
# Why it matters: Identifies seasonal vulnerabilities (e.g., holiday spikes in 
# cargo theft) and tracks the long-term effectiveness of newly implemented 
# security protocols or carrier audits.
# =============================================================================
q5 = """
SELECT 
    strftime('%Y-%m', scheduled_departure) AS year_month,
    COUNT(*) AS total_shipments,
    SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) AS unreceived_count,
    ROUND((SUM(CASE WHEN status = 'UNRECEIVED' THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 2) AS unreceived_rate_pct
FROM shipments
WHERE scheduled_departure IS NOT NULL
GROUP BY 
    year_month
ORDER BY 
    year_month ASC;
"""

# =============================================================================
# Testing Block
# =============================================================================
if __name__ == "__main__":
    db_path = "cargo_tracking.db"
    
    try:
        # Establish connection to SQLite database
        conn = sqlite3.connect(db_path)
        print(f"Successfully connected to {db_path}\n" + "="*50)
        
        queries = {
            "Query 1: Carrier Risk Scorecard": q1,
            "Query 2: High-Risk Lane Analysis": q2,
            "Query 3: Dwell Time Outlier Shipments": q3,
            "Query 4: High-Value At-Risk Shipments": q4,
            "Query 5: Monthly Loss Trend": q5
        }
        
        # Iterate, execute, and print the top 5 rows
        for query_name, sql in queries.items():
            print(f"\nExecuting {query_name}...")
            try:
                df = pd.read_sql_query(sql, conn)
                if df.empty:
                    print("Result: 0 rows returned (or table is empty).")
                else:
                    print(df.head(5).to_string(index=False))
            except Exception as e:
                print(f"Error executing {query_name}: {e}")
                
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\nDatabase connection closed.")