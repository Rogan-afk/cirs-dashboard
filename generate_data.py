import sqlite3
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def main():
    db_file = 'cargo_tracking.db'
    total_records = 50000
    
    state_codes = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ]
    
    carrier_mapping = {
        "CARR-01": "FastFreight LLC",
        "CARR-02": "MidWest Cargo Co",
        "CARR-03": "TransAmerica Logistics",
        "CARR-04": "PrimeShip Inc",
        "CARR-05": "Global Express",
        "CARR-06": "Rapid Transit Lines",
        "CARR-07": "National Cargo Works",
        "CARR-08": "Vanguard Shipping",
        "CARR-09": "Apex Freight",
        "CARR-10": "Pioneer Transport",
        "CARR-11": "Horizon Logistics",
        "CARR-12": "Summit Carriers"
    }

    records = []
    
    for i in range(1, total_records + 1):
        shipment_id = f"SHIP-{i:05d}"
        carrier_id = f"CARR-{random.randint(1, 12):02d}"
        carrier_name = carrier_mapping[carrier_id]
        
        origin_state, destination_state = random.sample(state_codes, 2)
        lane_id = f"{origin_state}-{destination_state}"
        
        # Random dates across last 24 months
        days_ago = random.randint(0, 730)
        minutes_offset = random.randint(0, 1440)
        scheduled_departure = datetime.now() - timedelta(days=days_ago, minutes=minutes_offset)
        
        # 0 to 24 hours after scheduled_departure
        actual_departure = scheduled_departure + timedelta(hours=random.uniform(0, 24))
        
        # 3 to 12 days after actual_departure
        scheduled_arrival = actual_departure + timedelta(days=random.uniform(3, 12))
        
        status = random.choices(['DELIVERED', 'IN_TRANSIT', 'UNRECEIVED'], weights=[75, 15, 10])[0]
        
        if status == 'DELIVERED':
            actual_arrival = scheduled_arrival + timedelta(hours=random.uniform(0, 36))
            actual_arrival_str = actual_arrival.strftime('%Y-%m-%d %H:%M:%S')
        else:
            actual_arrival_str = None
            
        # dwell_time_hours: mean=14, std=4, minimum=4
        dwell_time_hours = max(4.0, random.gauss(14, 4))
        
        # freight_value_usd: 500 - 60000 log-normal
        freight_value_usd = float(np.clip(np.random.lognormal(mean=8.5, sigma=1.0), 500, 60000))
        
        # weight_lbs: 100 - 45000
        weight_lbs = random.uniform(100.0, 45000.0)
        
        # stop_count: 0 - 5
        stop_count = random.randint(0, 5)
        
        is_anomaly = 0
        
        # Build base record
        r = {
            'shipment_id': shipment_id,
            'carrier_id': carrier_id,
            'carrier_name': carrier_name,
            'origin_state': origin_state,
            'destination_state': destination_state,
            'lane_id': lane_id,
            'scheduled_departure': scheduled_departure.strftime('%Y-%m-%d %H:%M:%S'),
            'actual_departure': actual_departure.strftime('%Y-%m-%d %H:%M:%S'),
            'scheduled_arrival': scheduled_arrival.strftime('%Y-%m-%d %H:%M:%S'),
            'actual_arrival': actual_arrival_str,
            'status': status,
            'dwell_time_hours': dwell_time_hours,
            'freight_value_usd': freight_value_usd,
            'weight_lbs': weight_lbs,
            'stop_count': stop_count,
            'is_anomaly': is_anomaly
        }
        
        records.append(r)

    # Inject anomalies
    for r in records:
        # 1. CARR-03 and CARR-07 UNRECEIVED boost (~30%)
        if r['carrier_id'] in ['CARR-03', 'CARR-07'] and r['status'] != 'UNRECEIVED':
            # Converting ~22.2% of non-unreceived to achieve 30% overall from base 10%
            if random.random() < 0.222:
                r['status'] = 'UNRECEIVED'
                r['actual_arrival'] = None
                r['is_anomaly'] = 1

        # 2. Lane "TX-CA" and lane "IL-FL" dwell time manipulation
        if r['lane_id'] in ['TX-CA', 'IL-FL']:
            r['dwell_time_hours'] = max(50.0, random.gauss(85, 18))
            r['is_anomaly'] = 1

        # 3. High freight value rule
        if r['freight_value_usd'] > 40000 and r['carrier_id'] in ['CARR-03', 'CARR-07']:
            r['status'] = 'UNRECEIVED'
            r['actual_arrival'] = None
            r['is_anomaly'] = 1

        # 4. UNRECEIVED with high dwell time rule
        if r['status'] == 'UNRECEIVED' and r['dwell_time_hours'] > 60:
            r['is_anomaly'] = 1

    # Convert to DataFrame
    df = pd.DataFrame(records)

    # SQLite database insertion
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS shipments')
    
    create_table_sql = '''
    CREATE TABLE shipments (
        shipment_id TEXT PRIMARY KEY,
        carrier_id TEXT,
        carrier_name TEXT,
        origin_state TEXT,
        destination_state TEXT,
        lane_id TEXT,
        scheduled_departure TEXT,
        actual_departure TEXT,
        scheduled_arrival TEXT,
        actual_arrival TEXT,
        status TEXT,
        dwell_time_hours REAL,
        freight_value_usd REAL,
        weight_lbs REAL,
        stop_count INTEGER,
        is_anomaly INTEGER
    )
    '''
    cursor.execute(create_table_sql)
    conn.commit()
    
    # Insert data
    df.to_sql('shipments', conn, if_exists='append', index=False)
    
    # Reporting
    count_total = pd.read_sql("SELECT COUNT(*) as count FROM shipments", conn).iloc[0]['count']
    count_unreceived = pd.read_sql("SELECT COUNT(*) as count FROM shipments WHERE status = 'UNRECEIVED'", conn).iloc[0]['count']
    count_anomaly = pd.read_sql("SELECT COUNT(*) as count FROM shipments WHERE is_anomaly = 1", conn).iloc[0]['count']
    top_carriers = pd.read_sql("SELECT carrier_name, COUNT(*) as count FROM shipments GROUP BY carrier_name ORDER BY count DESC LIMIT 5", conn)
    
    print(f"Total records inserted: {count_total}")
    print(f"UNRECEIVED count: {count_unreceived}")
    print(f"Anomaly count (is_anomaly=1): {count_anomaly}")
    print("Top 5 carriers by shipment count:")
    for _, row in top_carriers.iterrows():
        print(f"  - {row['carrier_name']}: {row['count']} shipments")
        
    conn.close()

if __name__ == '__main__':
    main()