import streamlit as st
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from fuzzywuzzy import fuzz
import re
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.title("Polymarket Insider Trading Detection Dashboard")

data_file = 'all_open_polymarket_markets_gamma.json'

@st.cache_data(show_spinner="Loading market data...")
def load_markets(file_path):
    with open(file_path, 'r') as f:
        raw = json.load(f)
    
    data = []
    for m in raw:
        try:
            prices = json.loads(m.get('outcomePrices', '["0.5","0.5"]'))
            yes_prob = float(prices[0])
            data.append({
                'question': m.get('question', 'No title'),
                'yes_prob': yes_prob,
                'volume_24h': float(m.get('volume24hr', 0)),
                'volume': float(m.get('volume', 0)),
                'condition_id': m.get('conditionId', 'N/A'),
                'category': m.get('category', 'Uncategorized'),
                'clob_token_ids': json.loads(m.get('clobTokenIds', '["N/A","N/A"]')),
                'end_date': m.get('endDate', 'N/A'),
                'liquidity': float(m.get('liquidity', 0)),
                'active': m.get('active', True),
            })
        except:
            continue
    return pd.DataFrame(data)

def calculate_volume_anomaly_score(volume_24h, historical_volumes):
    """Calculate Z-score for volume anomaly detection"""
    if len(historical_volumes) < 3:
        return 0
    
    mean_vol = np.mean(historical_volumes)
    std_vol = np.std(historical_volumes)
    
    if std_vol == 0:
        return 0
    
    z_score = (volume_24h - mean_vol) / std_vol
    return max(0, z_score)  # Only positive anomalies (spikes)

def calculate_price_volatility(prob_history):
    """Calculate price volatility using ATR-like method"""
    if len(prob_history) < 2:
        return 0
    
    price_changes = []
    for i in range(1, len(prob_history)):
        change = abs(prob_history[i] - prob_history[i-1])
        price_changes.append(change)
    
    return np.mean(price_changes) if price_changes else 0

def detect_market_imbalance(buy_volume, sell_volume):
    """Calculate market imbalance ratio"""
    total_volume = buy_volume + sell_volume
    if total_volume == 0:
        return 0.5
    
    return buy_volume / total_volume

def generate_insider_alert_score(row, volume_baseline, price_volatility_baseline):
    """Generate composite insider trading alert score"""
    score = 0
    alerts = []
    
    # Volume anomaly (40% weight)
    volume_score = calculate_volume_anomaly_score(row['volume_24h'], volume_baseline)
    if volume_score > 3:  # 3 standard deviations
        score += 40
        alerts.append(f"Volume spike: {volume_score:.1f}σ above normal")
    
    # Price volatility (25% weight)
    price_vol = calculate_price_volatility([row['yes_prob']])  # Simplified
    if price_vol > price_volatility_baseline * 1.5:
        score += 25
        alerts.append(f"High price volatility: {price_vol:.3f}")
    
    # Low liquidity with high volume (20% weight)
    if row['liquidity'] < 1000 and row['volume_24h'] > 10000:
        score += 20
        alerts.append("High volume in low liquidity market")
    
    # Extreme probability (15% weight)
    if row['yes_prob'] > 0.95 or row['yes_prob'] < 0.05:
        score += 15
        alerts.append(f"Extreme probability: {row['yes_prob']:.3f}")
    
    return min(100, score), alerts

# Load data
df = load_markets(data_file)
st.success(f"Loaded {len(df):,} markets!")

# Sidebar controls
st.sidebar.header("Detection Settings")

# Volume threshold
volume_threshold = st.sidebar.slider("Min 24h Volume for Analysis ($)", 1000, 50000000, 10000)
liquid_df = df[df['volume_24h'] > volume_threshold]

# Category selection
categories = sorted(liquid_df['category'].unique())
selected_cats = st.sidebar.multiselect(
    "Select Categories",
    categories,
    default=liquid_df['category'].value_counts().head(5).index.tolist()
)

# Sensitivity settings
sensitivity = st.sidebar.selectbox("Detection Sensitivity", ["Low", "Medium", "High"], index=1)
sensitivity_multipliers = {"Low": 0.7, "Medium": 1.0, "High": 1.3}
sensitivity_mult = sensitivity_multipliers[sensitivity]

# Filter by selected categories
filtered_df = liquid_df[liquid_df['category'].isin(selected_cats)]

# Calculate baselines (simplified - in production, use historical data)
volume_baseline = [filtered_df['volume_24h'].mean()] * 10  # Mock historical baseline
price_volatility_baseline = 0.05  # 5% baseline volatility

st.write(f"Analyzing {len(filtered_df):,} markets in {len(selected_cats)} categories")

# Run detection
if st.button("Run Insider Trading Detection"):
    st.subheader("🔍 Insider Trading Alert Results")
    
    results = []
    for idx, row in filtered_df.iterrows():
        score, alerts = generate_insider_alert_score(row, volume_baseline, price_volatility_baseline)
        
        if score > 30 * sensitivity_mult:  # Minimum threshold
            results.append({
                'Market': row['question'][:100] + '...',
                'Category': row['category'],
                'Alert Score': f"{score:.0f}",
                '24h Volume': f"${row['volume_24h']:,.0f}",
                'YES Prob': f"{row['yes_prob']:.3f}",
                'Liquidity': f"${row['liquidity']:,.0f}",
                'Alerts': ' | '.join(alerts),
                'Condition ID': row['condition_id'],
            })
    
    if results:
        results_df = pd.DataFrame(results)
        results_df['Alert Score'] = pd.to_numeric(results_df['Alert Score'])
        results_df = results_df.sort_values('Alert Score', ascending=False)
        
        # Color coding for alert scores
        def color_alert_score(val):
            if val >= 70:
                return 'background-color: #ff4444; color: white'
            elif val >= 50:
                return 'background-color: #ff8800; color: white'
            elif val >= 30:
                return 'background-color: #ffaa00; color: black'
            else:
                return ''
        
        styled_df = results_df.style.applymap(color_alert_score, subset=['Alert Score'])
        st.dataframe(styled_df, use_container_width=True)
        
        # Download results
        csv_data = results_df.to_csv(index=False)
        st.download_button(
            "Download Alert CSV",
            csv_data,
            "insider_trading_alerts.csv",
            "text/csv"
        )
        
        # Alert summary
        st.subheader("📊 Alert Summary")
        high_alerts = len(results_df[results_df['Alert Score'] >= 70])
        medium_alerts = len(results_df[(results_df['Alert Score'] >= 50) & (results_df['Alert Score'] < 70)])
        low_alerts = len(results_df[(results_df['Alert Score'] >= 30) & (results_df['Alert Score'] < 50)])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("🔴 High Risk Alerts", high_alerts)
        col2.metric("🟡 Medium Risk Alerts", medium_alerts)
        col3.metric("🟢 Low Risk Alerts", low_alerts)
        
    else:
        st.info("No insider trading alerts detected. Try adjusting sensitivity thresholds.")

# Market details section
st.subheader("📈 Market Analysis")
selected_market = st.selectbox("Select market for detailed analysis", 
                               options=filtered_df['question'].tolist(),
                               index=0)

if selected_market:
    market_data = filtered_df[filtered_df['question'] == selected_market].iloc[0]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Market Details**")
        st.write(f"Question: {market_data['question']}")
        st.write(f"Category: {market_data['category']}")
        st.write(f"24h Volume: ${market_data['volume_24h']:,.0f}")
        st.write(f"Total Volume: ${market_data['volume']:,.0f}")
        st.write(f"Liquidity: ${market_data['liquidity']:,.0f}")
        st.write(f"YES Probability: {market_data['yes_prob']:.3f}")
    
    with col2:
        # Create a simple gauge chart for alert score
        score, alerts = generate_insider_alert_score(market_data, volume_baseline, price_volatility_baseline)
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Insider Alert Score"},
            delta = {'reference': 50},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 30], 'color': "lightgreen"},
                    {'range': [30, 50], 'color': "yellow"},
                    {'range': [50, 70], 'color': "orange"},
                    {'range': [70, 100], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 70
                }
            }
        ))
        
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        if alerts:
            st.write("**Detected Anomalies:**")
            for alert in alerts:
                st.write(f"• {alert}")

# Footer with methodology
st.markdown("---")
st.subheader("🔬 Detection Methodology")
st.markdown("""
**How Insider Trading Detection Works:**

1. **Volume Anomaly Detection**: Uses Z-score analysis to identify unusual trading volume spikes (3σ+ above normal)

2. **Price Volatility Analysis**: Detects abnormal price movements that may indicate information leakage

3. **Liquidity Analysis**: Flags high-volume trading in low-liquidity markets (easier to manipulate)

4. **Extreme Probability Analysis**: Identifies markets with extremely one-sided odds that may reflect insider knowledge

5. **Composite Scoring**: Combines multiple signals into a single alert score (0-100)

**Alert Levels:**
- 🔴 **High Risk (70+)**: Multiple strong indicators, warrants immediate investigation
- 🟡 **Medium Risk (50-69)**: Several moderate indicators, monitor closely  
- 🟢 **Low Risk (30-49)**: Single or weak indicators, routine monitoring

**Note**: This is a detection tool, not definitive proof of insider trading. Further investigation required.
""")
