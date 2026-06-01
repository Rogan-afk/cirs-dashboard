import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import datetime

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Navigation Portal", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Global styling adjustments for a cleaner corporate canvas
# Global styling adjustments (Theme-Responsive)
st.markdown("""
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        /* Use Streamlit's native CSS variables for automatic Light/Dark mode support */
        h1, h2, h3 { font-weight: 600 !important; color: var(--text-color) !important; }
        .stMetric { 
            background-color: var(--secondary-background-color); 
            padding: 1rem; 
            border-radius: 0.5rem; 
            border: 1px solid var(--border-color); 
        }
    </style>
""", unsafe_allow_html=True)

# --- 2 & 3. HEADER AND BRANDING ---
st.title("Dashboard for Cargo Integrity")
st.caption("Risk Mitigation, Anomaly Detection & Incident Investigation")
st.markdown("---")

# --- 4. SIDEBAR NAVIGATION ---
st.sidebar.markdown("### Risk Management")
page = st.sidebar.radio(
    "Navigation",
    options=[
        "Executive Summary",
        "Investigation Queue",
        "Carrier Scorecard",
        "Lane Analysis",
        "Case Detail"
    ]
)

# --- 5. DATA LOADING ---
@st.cache_data
def load_data():
    conn = sqlite3.connect("cargo_tracking.db")
    
    shipments_df = pd.read_sql("SELECT * FROM shipments", conn)
    flagged_df = pd.read_sql("SELECT * FROM flagged_shipments", conn)
    
    conn.close()
    
    # Secure datetime parsing
    date_cols = ['scheduled_departure', 'actual_departure', 'scheduled_arrival', 'actual_arrival']
    for col in date_cols:
        if col in shipments_df.columns:
            shipments_df[col] = pd.to_datetime(shipments_df[col], errors='coerce')
        if col in flagged_df.columns:
            flagged_df[col] = pd.to_datetime(flagged_df[col], errors='coerce')
            
    # Standardized time intervals
    if 'scheduled_departure' in shipments_df.columns:
        shipments_df['year_month'] = shipments_df['scheduled_departure'].dt.strftime('%Y-%m')
    if 'scheduled_departure' in flagged_df.columns:
        flagged_df['year_month'] = flagged_df['scheduled_departure'].dt.strftime('%Y-%m')
        
    return shipments_df, flagged_df

try:
    shipments, flagged = load_data()
except Exception as e:
    st.error(f"Database Initialization Error. Confirm 'cargo_tracking.db' exists in the active directory. Technical details: {e}")
    st.stop()


# --- PAGE 1: EXECUTIVE SUMMARY ---
if page == "Executive Summary":
    st.subheader("Network Risk Overview")
    
    # Row 1: Metrics with premium container boxing
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    
    total_shipments = len(flagged)
    unreceived_count = len(flagged[flagged['status'] == 'UNRECEIVED'])
    critical_flags = len(flagged[flagged['risk_tier'] == 'CRITICAL'])
    
    unreceived_df = flagged[flagged['status'] == 'UNRECEIVED']
    freight_at_risk = unreceived_df['freight_value_usd'].sum()
    freight_at_risk_str = f"${freight_at_risk / 1_000_000:.1f}M"
    
    with m_col1:
        st.metric("Total Shipments Monitored", f"{total_shipments:,}")
    with m_col2:
        st.metric("Unreceived Incidents", f"{unreceived_count:,}")
    with m_col3:
        st.metric("Critical Risk Flags", f"{critical_flags:,}")
    with m_col4:
        st.metric("Total Freight At Risk", freight_at_risk_str)
        
    st.markdown("<br>", unsafe_allow_html=True)
        
    # Row 2: Charts encapsulated in structural cards
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        with st.container(border=True):
            st.markdown("##### Performance Outliers: Top 10 Carriers")
            carrier_stats = flagged.groupby('carrier_name').agg(
                total_count=('shipment_id', 'count'),
                unreceived_count=('status', lambda x: (x == 'UNRECEIVED').sum())
            ).reset_index()
            
            carrier_stats['unreceived_rate_pct'] = (carrier_stats['unreceived_count'] / carrier_stats['total_count']) * 100
            top_carriers = carrier_stats.sort_values(by='unreceived_rate_pct', ascending=False).head(10)
            
            # Using clean enterprise hex codes instead of standard primary strings
            # Change from #991B1B and #334155 to brighter, theme-agnostic colors
            top_carriers['color_hex'] = top_carriers['unreceived_rate_pct'].apply(lambda x: '#EF4444' if x > 15 else '#64748B')
            
            fig1 = px.bar(
                top_carriers, 
                x='carrier_name', 
                y='unreceived_rate_pct',
                labels={'carrier_name': 'Carrier Name', 'unreceived_rate_pct': 'Unreceived Rate (%)'}
            )
            fig1.update_traces(marker_color=top_carriers['color_hex'])
            fig1.add_hline(y=15, line_dash="dash", line_color="#EF4444", annotation_text="Critical Threshold (15%)")
            fig1.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig1, use_container_width=True)

    with chart_col2:
        with st.container(border=True):
            st.markdown("##### Longitudinal Analysis: Unreceived Volume Trend")
            monthly_df = flagged.groupby('year_month').agg(
                unreceived_count=('status', lambda x: (x == 'UNRECEIVED').sum())
            ).reset_index().dropna()
            
            monthly_df = monthly_df.sort_values('year_month')
            
            fig2 = px.bar(
                monthly_df, 
                x='year_month', 
                y='unreceived_count', 
                labels={'year_month': 'Reporting Month', 'unreceived_count': 'Incidents'},
                color_discrete_sequence=['#475569']
            )
            fig2.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig2, use_container_width=True)


# --- PAGE 2: INVESTIGATION QUEUE ---
elif page == "Investigation Queue":
    st.subheader("Active Investigation Queue")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Queue Filters")
    
    risk_tiers = flagged['risk_tier'].dropna().unique().tolist()
    default_tiers = [t for t in ['CRITICAL', 'HIGH'] if t in risk_tiers]
    
    selected_tiers = st.sidebar.multiselect("Risk Classification", options=risk_tiers, default=default_tiers)
    
    all_carriers = sorted(flagged['carrier_name'].dropna().unique())
    selected_carriers = st.sidebar.multiselect("Carrier Entity", options=all_carriers, default=all_carriers)
    
    valid_dates = flagged['scheduled_arrival'].dropna()
    min_date = valid_dates.min().date() if not valid_dates.empty else datetime.date.today()
    max_date = valid_dates.max().date() if not valid_dates.empty else datetime.date.today()
    
    date_range = st.sidebar.date_input("Scheduled Window (From / To)", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    
    filtered_df = flagged.copy()
    if selected_tiers:
        filtered_df = filtered_df[filtered_df['risk_tier'].isin(selected_tiers)]
    if selected_carriers:
        filtered_df = filtered_df[filtered_df['carrier_name'].isin(selected_carriers)]
        
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['scheduled_arrival'].dt.date >= start_date) & 
            (filtered_df['scheduled_arrival'].dt.date <= end_date)
        ]

    st.info(f"Analysis parameters yielded {len(filtered_df):,} records requiring evaluation.")
    
    display_cols = [
        'shipment_id', 'carrier_name', 'lane_id', 'status', 'risk_tier', 
        'risk_score', 'freight_value_usd', 'dwell_time_hours', 'scheduled_arrival'
    ]
    display_cols = [c for c in display_cols if c in filtered_df.columns]
    
    view_df = filtered_df[display_cols].copy()
    if 'risk_score' in view_df.columns:
        view_df['risk_score'] = view_df['risk_score'].round(1)
    if 'freight_value_usd' in view_df.columns:
        view_df['freight_value_usd'] = view_df['freight_value_usd'].fillna(0).astype(int)
    if 'scheduled_arrival' in view_df.columns:
        view_df['scheduled_arrival'] = view_df['scheduled_arrival'].dt.strftime('%Y-%m-%d %H:%M')
        
    st.dataframe(view_df, use_container_width=True, hide_index=True)
    
    csv_data = view_df.to_csv(index=False)
    st.download_button(
        label="Export Operational Queue (CSV)",
        data=csv_data,
        file_name="cr_investigation_queue.csv",
        mime="text/csv"
    )


# --- PAGE 3: CARRIER SCORECARD ---
elif page == "Carrier Scorecard":
    st.subheader("Commercial Carrier Scorecard")
    
    scorecard_df = flagged.groupby('carrier_name').agg(
        total_shipments=('shipment_id', 'count'),
        unreceived_count=('status', lambda x: (x == 'UNRECEIVED').sum()),
        avg_risk_score=('risk_score', 'mean'),
        critical_count=('risk_tier', lambda x: (x == 'CRITICAL').sum())
    ).reset_index()
    
    scorecard_df['unreceived_rate_pct'] = ((scorecard_df['unreceived_count'] / scorecard_df['total_shipments']) * 100).round(2)
    scorecard_df['avg_risk_score'] = scorecard_df['avg_risk_score'].round(1)
    scorecard_df = scorecard_df.sort_values('unreceived_rate_pct', ascending=False)
    
    if not scorecard_df.empty:
        highest_risk_carrier = scorecard_df.iloc[0]['carrier_name']
        net_avg_unreceived = (scorecard_df['unreceived_count'].sum() / scorecard_df['total_shipments'].sum() * 100)
        above_threshold_count = len(scorecard_df[scorecard_df['unreceived_rate_pct'] > 15])
    else:
        highest_risk_carrier, net_avg_unreceived, above_threshold_count = "N/A", 0.0, 0

    c_col1, c_col2, c_col3 = st.columns(3)
    with c_col1:
        st.metric("Primary Exposure Carrier", str(highest_risk_carrier))
    with c_col2:
        st.metric("Network Mean Unreceived Rate", f"{net_avg_unreceived:.2f}%")
    with c_col3:
        st.metric("Carriers Exceeding Threshold", f"{above_threshold_count:,}")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_table, col_chart = st.columns([1.2, 1])
    
    with col_table:
        with st.container(border=True):
            st.markdown("##### Performance Ledger")
            display_order = ['carrier_name', 'total_shipments', 'unreceived_count', 'unreceived_rate_pct', 'avg_risk_score', 'critical_count']
            st.dataframe(scorecard_df[display_order], use_container_width=True, hide_index=True, height=480)
        
    with col_chart:
        with st.container(border=True):
            st.markdown("##### Comparative Risk Indexing")
            fig3 = px.bar(
                scorecard_df.head(15).sort_values('unreceived_rate_pct', ascending=True),
                x='unreceived_rate_pct',
                y='carrier_name',
                orientation='h',
                color='unreceived_rate_pct',
                color_continuous_scale='RdYlGn_r',
                labels={'unreceived_rate_pct': 'Unreceived Rate %', 'carrier_name': 'Carrier'}
            )
            fig3.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig3, use_container_width=True)


# --- PAGE 4: LANE ANALYSIS (FIXED FOR EMPTY STATES) ---
elif page == "Lane Analysis":
    st.subheader("Transit Lane Integrity Profiling")
    
    lane_df = flagged.groupby('lane_id').agg(
        shipment_count=('shipment_id', 'count'),
        unreceived_count=('status', lambda x: (x == 'UNRECEIVED').sum()),
        avg_dwell_time_hours=('dwell_time_hours', 'mean'),
        avg_risk_score=('risk_score', 'mean')
    ).reset_index()
    
    # FIX: Add an interactive volume slider in the main container to ensure the page is never hard-locked empty
    st.markdown("##### Volumetric Filtering Parameters")
    max_shipments_in_data = int(lane_df['shipment_count'].max()) if not lane_df.empty else 10
    min_volume_threshold = st.slider(
        "Exclude micro-lanes. Show corridors with minimum sample size of:", 
        min_value=1, 
        max_value=max_shipments_in_data if max_shipments_in_data > 1 else 10, 
        value=min(10, max_shipments_in_data)
    )
    
    lane_df = lane_df[lane_df['shipment_count'] >= min_volume_threshold].copy()
    
    if lane_df.empty:
        st.warning("No transit corridors match the current volume filter constraints. Adjust the slider downward.")
    else:
        lane_df['unreceived_rate_pct'] = ((lane_df['unreceived_count'] / lane_df['shipment_count']) * 100).round(2)
        lane_df['avg_dwell_time_hours'] = lane_df['avg_dwell_time_hours'].round(1)
        lane_df['avg_risk_score'] = lane_df['avg_risk_score'].round(1)
        
        lane_df['risk_flag'] = lane_df.apply(
            lambda row: 'HIGH-RISK' if (row['unreceived_rate_pct'] > 12 or row['avg_dwell_time_hours'] > 50) else 'NORMAL', 
            axis=1
        )
        
        lane_df = lane_df.sort_values('unreceived_rate_pct', ascending=False)
        top_15_lanes = lane_df.head(15)
        
        with st.container(border=True):
            st.markdown("##### High-Exposure Transit Lanes")
            st.dataframe(top_15_lanes, use_container_width=True, hide_index=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        col_chart1, col_chart2 = st.columns(2)
        
        color_map = {'HIGH-RISK': '#EF4444', 'NORMAL': '#64748B'}
        
        with col_chart1:
            with st.container(border=True):
                st.markdown("##### Losses by Identified Corridors")
                fig4 = px.bar(
                    top_15_lanes,
                    x='lane_id',
                    y='unreceived_rate_pct',
                    color='risk_flag',
                    color_discrete_map=color_map,
                    labels={'lane_id': 'Corridor ID', 'unreceived_rate_pct': 'Unreceived Rate %', 'risk_flag': 'Status Flag'}
                )
                fig4.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig4, use_container_width=True)
                
        with col_chart2:
            with st.container(border=True):
                st.markdown("##### Risk Matrix Correlation (Dwell vs Loss)")
                fig5 = px.scatter(
                    lane_df,
                    x='avg_dwell_time_hours',
                    y='unreceived_rate_pct',
                    size='shipment_count',
                    color='risk_flag',
                    color_discrete_map=color_map,
                    hover_name='lane_id',
                    labels={
                        'avg_dwell_time_hours': 'Mean Dwell Interval (Hours)', 
                        'unreceived_rate_pct': 'Unreceived Rate %',
                        'risk_flag': 'Risk Assessment',
                        'shipment_count': 'Data Density'
                    }
                )
                fig5.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig5, use_container_width=True)


# --- PAGE 5: CASE DETAIL ---
elif page == "Case Detail":
    st.subheader("Case Detail Lookup")
    
    with st.container(border=True):
        col_inp, col_btn = st.columns([3, 1])
        with col_inp:
            shipment_id_input = st.text_input("Consignment Identifier Verification", placeholder="e.g. SHIP-00042", label_visibility="collapsed")
        with col_btn:
            investigate_clicked = st.button("Execute Deep Investigation", use_container_width=True)
            
    if investigate_clicked:
        clean_id = shipment_id_input.strip().upper()
        match = flagged[flagged['shipment_id'] == clean_id]
        
        if match.empty:
            st.error("System Query Failed: Shipment tracking reference code not isolated in current data vault.")
        else:
            row = match.iloc[0]
            
            # Sub-row Metrics
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.metric("Consignment Status", str(row.get('status', 'UNKNOWN')))
            with m_col2:
                st.metric("Assigned Threat Vector", str(row.get('risk_tier', 'N/A')))
            with m_col3:
                risk_score = row.get('risk_score', 0.0)
                st.metric("Absolute Threat Weight", f"{risk_score:.1f} / 100")
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Logistics Ledger Table
            with st.container(border=True):
                st.markdown("##### Logistics Operational Ledger")
                details_data = [
                    {"Field": "Carrier Account Name", "Value": str(row.get('carrier_name', ''))},
                    {"Field": "Assigned Logistics Lane", "Value": str(row.get('lane_id', ''))},
                    {"Field": "Origin State Jurisdiction", "Value": str(row.get('origin_state', ''))},
                    {"Field": "Destination Target State", "Value": str(row.get('destination_state', ''))},
                    {"Field": "Scheduled Departure Window", "Value": str(row.get('scheduled_departure', ''))},
                    {"Field": "Scheduled Expected Arrival", "Value": str(row.get('scheduled_arrival', ''))},
                    {"Field": "Confirmed Gate Inbound Time", "Value": str(row.get('actual_arrival', ''))},
                    {"Field": "Declared Invoice Valuation ($)", "Value": f"${row.get('freight_value_usd', 0):,.2f}"},
                    {"Field": "Gross Freight Mass (lbs)", "Value": f"{row.get('weight_lbs', 0):,}"},
                    {"Field": "Bill of Lading Stop Points", "Value": str(row.get('stop_count', ''))},
                    {"Field": "Calculated Warehouse Dwell (Hours)", "Value": str(row.get('dwell_time_hours', ''))},
                    {"Field": "Resolution Disposition State", "Value": str(row.get('status', ''))}
                ]
                st.dataframe(pd.DataFrame(details_data), hide_index=True, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Anomalous Indicators Status Blocks
            st.markdown("##### System Anomalous Indicators")
            flags_map = {
                "z_score_flag": "Temporal Dwell Deviation Check (Z-Score)",
                "iqr_flag": "Valuation Exposure Analysis (IQR)",
                "carrier_risk_flag": "Historical Carrier Risk Factor Attribution"
            }
            
            for col_name, friendly_name in flags_map.items():
                if row.get(col_name, 0) == 1:
                    st.warning(f"CRITICAL ASSIGNMENT: {friendly_name} — EXCEEDED OUTLIER CONTROL LIMITS")
                else:
                    st.success(f"Verified Clearance: {friendly_name} — Running Normal parameters")
                    
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Contextual Comparison Summary
            with st.container(border=True):
                st.markdown("##### Operational Context Validation")
                carrier_id = row.get('carrier_id')
                carrier_rows = flagged[flagged['carrier_id'] == carrier_id]
                carrier_avg = carrier_rows['risk_score'].mean() if not carrier_rows.empty else 0.0
                
                comp_col1, comp_col2 = st.columns(2)
                with comp_col1:
                    st.metric("Consignment Threat Rating", f"{risk_score:.1f}")
                with comp_col2:
                    st.metric("Carrier Peer Pool Average", f"{carrier_avg:.1f}")
                    
                if risk_score > carrier_avg:
                    st.warning("Elevated Threat Profile: This consignment displays standard deviations significantly higher than the carrier's asset benchmark history.")
                else:
                    st.info("Controlled Variance Profile: This consignment parameters map cleanly inside standard historical deviations recorded for this vendor account.")
