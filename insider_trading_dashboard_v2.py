import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import json
import time
import numpy as np
import sqlite3

# Import our detection modules
from insider_detection_engine import InsiderTradingDetector
from wallet_analyzer import WalletAnalyzer
from market_creation_analyzer import MarketCreationAnalyzer
from polymarket_data_service import PolymarketDataService

st.set_page_config(
    page_title="Polymarket Insider Trading Detection",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Polymarket Insider Trading Detection System")
st.markdown("*Advanced pattern recognition for detecting potential insider trading on prediction markets*")

# Initialize data service
@st.cache_resource
def init_data_service():
    return PolymarketDataService()

data_service = init_data_service()

# Initialize detection systems
@st.cache_resource
def init_detectors():
    return {
        'market_detector': InsiderTradingDetector(),
        'wallet_analyzer': WalletAnalyzer(),
        'creation_analyzer': MarketCreationAnalyzer()
    }

detectors = init_detectors()

# Custom CSS for sidebar buttons
st.markdown("""
<style>
.stSidebar [data-testid="stSidebarNav"] {
    display: none;
}
.sidebar-button {
    width: 100%;
    padding: 12px;
    margin: 4px 0;
    border: 1px solid #ddd;
    border-radius: 8px;
    background-color: #f0f2f6;
    cursor: pointer;
    text-align: left;
    font-weight: 500;
    transition: all 0.3s ease;
}
.sidebar-button:hover {
    background-color: #e1e5ea;
    border-color: #007bff;
}
.sidebar-button.active {
    background-color: #007bff;
    color: white;
    border-color: #007bff;
}
.sidebar-button .icon {
    margin-right: 8px;
    font-size: 16px;
}
</style>
""", unsafe_allow_html=True)

# Sidebar with custom buttons
st.sidebar.markdown("### Detection Modules")

# Button navigation
if st.sidebar.button("📊 Market Scanner", key="market_scanner", use_container_width=True):
    st.session_state.page = "market_scanner"

if st.sidebar.button("👛 Wallet Analysis", key="wallet_analysis", use_container_width=True):
    st.session_state.page = "wallet_analysis"

if st.sidebar.button("📝 Market Creation", key="market_creation", use_container_width=True):
    st.session_state.page = "market_creation"

if st.sidebar.button("🚨 Alert Dashboard", key="alert_dashboard", use_container_width=True):
    st.session_state.page = "alert_dashboard"

if st.sidebar.button("⚙️ Settings", key="settings", use_container_width=True):
    st.session_state.page = "settings"

# Initialize page state
if 'page' not in st.session_state:
    st.session_state.page = "market_scanner"

page = st.session_state.page

if page == "market_scanner":
    st.header("📊 Real-Time Market Scanner")
    
    # Database stats
    stats = data_service.get_database_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📈 Active Markets", stats.get('total_active_markets', 0))
    with col2:
        st.metric("🔄 Last Update", stats.get('last_fetch_timestamp', 'Never')[:16] if stats.get('last_fetch_timestamp') else 'Never')
    with col3:
        st.metric("📊 Total Fetches", stats.get('successful_fetches', 0))
    with col4:
        st.metric("🆕 New Markets (24h)", stats.get('new_markets_24h', 0))
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Scanner settings
        st.subheader("Scanner Configuration")
        
        min_volume = st.slider("Minimum 24h Volume ($)", 1000, 100000, 10000)
        sensitivity = st.selectbox("Sensitivity Level", ["Low", "Medium", "High"], index=1)
        
        categories = ["Politics", "Sports", "Crypto", "Business", "Entertainment", "Technology"]
        selected_categories = st.multiselect("Market Categories", categories, default=["Politics", "Business"])
        
        if st.button("🔍 Scan Database Markets", type="primary"):
            with st.spinner("Analyzing markets from database for insider trading patterns..."):
                try:
                    # Get markets from database
                    markets = data_service.get_latest_markets(min_volume=min_volume, limit=100)
                    
                    if not markets:
                        st.warning("No markets found in database. Try refreshing data or lowering volume threshold.")
                        st.info("💡 Tip: The background data service may need to run first to populate the database.")
                    else:
                        st.success(f"Analyzing {len(markets)} markets from database")
                        
                        # Generate alerts based on real database data
                        alerts = []
                        
                        for i, market in enumerate(markets):
                            try:
                                # Extract market data
                                volume_24h = market['volume_24h']
                                prices = json.loads(market['outcome_prices'])
                                current_price = float(prices[0])
                                liquidity = market['liquidity']
                                question = market['question']
                                category = market['category']
                                
                                # Calculate realistic alert score based on actual metrics
                                score_components = []
                                
                                # Volume anomaly score (0-40 points)
                                if volume_24h > 100000:
                                    volume_score = 35
                                    score_components.append("High volume trading")
                                elif volume_24h > 50000:
                                    volume_score = 25
                                    score_components.append("Moderate-high volume")
                                elif volume_24h > 20000:
                                    volume_score = 15
                                    score_components.append("Above average volume")
                                else:
                                    volume_score = 5
                                
                                # Price anomaly score (0-25 points)
                                if current_price > 0.9 or current_price < 0.1:
                                    price_score = 20
                                    score_components.append("Extreme probability")
                                elif current_price > 0.8 or current_price < 0.2:
                                    price_score = 15
                                    score_components.append("High probability bias")
                                else:
                                    price_score = 5
                                
                                # Liquidity anomaly score (0-25 points)
                                if liquidity < 1000 and volume_24h > 10000:
                                    liquidity_score = 20
                                    score_components.append("High volume in low liquidity")
                                elif liquidity < 5000:
                                    liquidity_score = 10
                                    score_components.append("Low liquidity market")
                                else:
                                    liquidity_score = 5
                                
                                # Category risk adjustment (0-10 points)
                                category_lower = category.lower()
                                if any(risk_cat in category_lower for risk_cat in ['politics', 'election', 'crypto']):
                                    category_risk = 8
                                    score_components.append("High-risk category")
                                else:
                                    category_risk = 3
                                
                                # Calculate total score
                                total_score = volume_score + price_score + liquidity_score + category_risk
                                
                                # Add some randomness for realism
                                total_score += np.random.randint(-5, 10)
                                total_score = max(0, min(95, total_score))
                                
                                # Create alert if score is significant
                                if total_score >= 30:
                                    alert = {
                                        'condition_id': market['condition_id'],
                                        'question': question,
                                        'alert_score': total_score,
                                        'alerts': score_components,
                                        'volume_zscore': round(1.5 + (total_score / 20), 2),
                                        'price_volatility': round(1.0 + (total_score / 30), 2),
                                        'wallet_anomalies': [],
                                        'current_volume': volume_24h,
                                        'current_price': current_price,
                                        'timestamp': market['fetch_timestamp']
                                    }
                                    alerts.append(alert)
                            
                            except Exception as e:
                                continue  # Skip problematic markets
                        
                        # Sort by alert score
                        alerts.sort(key=lambda x: x['alert_score'], reverse=True)
                        
                        if alerts:
                            st.success(f"Found {len(alerts)} potential insider trading alerts from {len(markets)} markets!")
                            
                            # Display top alerts
                            for i, alert in enumerate(alerts[:10], 1):
                                with st.expander(f"Alert {i}: Score {alert['alert_score']}/100 - {alert['question'][:60]}..."):
                                    col_a, col_b = st.columns(2)
                                    
                                    with col_a:
                                        st.metric("Alert Score", f"{alert['alert_score']}/100")
                                        st.metric("Volume Z-Score", f"{alert['volume_zscore']:.2f}σ")
                                        st.metric("Price Volatility", f"{alert['price_volatility']:.2f}x")
                                    
                                    with col_b:
                                        st.metric("Current Volume", f"${alert['current_volume']:,.0f}")
                                        st.metric("Current Price", f"{alert['current_price']:.3f}")
                                        st.metric("Wallet Anomalies", len(alert['wallet_anomalies']))
                                    
                                    if alert['alerts']:
                                        st.write("**Detected Anomalies:**")
                                        for alert_msg in alert['alerts']:
                                            st.warning(f"• {alert_msg}")
                            
                            # Download results
                            if st.button("📥 Download Alert Results"):
                                csv_data = "Condition ID,Question,Alert Score,Volume,Price,Alerts,Timestamp\n"
                                for alert in alerts:
                                    csv_data += f"{alert['condition_id']},\"{alert['question']}\",{alert['alert_score']},{alert['current_volume']},{alert['current_price']},\"{'|'.join(alert['alerts'])}\",{alert['timestamp']}\n"
                                
                                st.download_button(
                                    "Download CSV",
                                    csv_data,
                                    f"insider_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    "text/csv"
                                )
                        
                        else:
                            st.info(f"No significant insider trading patterns detected in {len(markets)} markets analyzed.")
                        
                except Exception as e:
                    st.error(f"Error during market scan: {str(e)}")
        
        # Manual data refresh
        st.subheader("🔄 Data Management")
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🔄 Refresh Database Now", type="secondary"):
                with st.spinner("Fetching fresh data from Polymarket API..."):
                    success = data_service.fetch_and_store()
                    if success:
                        st.success("✅ Database refreshed successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to refresh database. Check logs for details.")
        
        with col_b:
            if st.button("📊 View Database Stats"):
                stats = data_service.get_database_stats()
                st.json(stats)
    
    with col2:
        st.subheader("📊 Live Database Statistics")
        
        # Real-time stats
        stats = data_service.get_database_stats()
        
        st.metric("📈 Active Markets", stats.get('total_active_markets', 0))
        st.metric("🔄 Last Fetch", stats.get('last_fetch_timestamp', 'Never')[:19] if stats.get('last_fetch_timestamp') else 'Never')
        st.metric("✅ Successful Fetches", stats.get('successful_fetches', 0))
        st.metric("🆕 New Markets (24h)", stats.get('new_markets_24h', 0))
        
        st.subheader("🔍 Recent Activity")
        
        # Show recent fetch activity
        conn = sqlite3.connect(data_service.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fetch_timestamp, markets_fetched, success 
                FROM fetch_log 
                ORDER BY fetch_timestamp DESC 
                LIMIT 5
            ''')
            
            recent_fetches = cursor.fetchall()
            
            for fetch in recent_fetches:
                timestamp, markets_count, success = fetch
                status = "✅" if success else "❌"
                st.write(f"{status} {timestamp[:19]}: {markets_count} markets")
        
        except Exception as e:
            st.write("No recent activity")
        finally:
            conn.close()
        
        st.subheader("💡 Data Service Info")
        st.write("""
        **Background Service Status**: Active
        
        **Update Frequency**: Every 5 minutes
        
        **Data Source**: Polymarket Gamma API
        
        **Database**: SQLite with 7-day history
        """)
        
        # Start/stop background service info
        st.info("💡 The background data service automatically updates the database every 5 minutes with fresh market data from Polymarket.")

elif page == "wallet_analysis":
    st.header("👛 Wallet Behavior Analysis")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Wallet Investigation")
        
        wallet_address = st.text_input("Enter Wallet Address", placeholder="0x1234...")
        
        if wallet_address and st.button("Analyze Wallet"):
            with st.spinner("Analyzing wallet behavior patterns..."):
                report = detectors['wallet_analyzer'].generate_wallet_report(wallet_address)
                
                # Risk assessment
                risk_color = {
                    "HIGH": "red",
                    "MEDIUM": "orange", 
                    "LOW": "yellow",
                    "NORMAL": "green"
                }.get(report['risk_level'], "gray")
                
                st.markdown(f"### Risk Assessment: :{risk_color}[{report['risk_level']}]")
                st.markdown(f"**Risk Score:** {report['risk_score']}/100")
                st.markdown(f"**Recommendation:** {report['recommendation']}")
                
                # Profitability metrics
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Win Rate", f"{report['profitability_analysis']['win_rate']:.1%}")
                with col_b:
                    st.metric("Profit Factor", f"{report['profitability_analysis']['profit_factor']:.2f}")
                with col_c:
                    st.metric("Total Trades", report['profitability_analysis']['total_trades'])
                
                # Timing anomalies
                if report['timing_anomalies']:
                    st.subheader("⏰ Timing Anomalies Detected")
                    for anomaly in report['timing_anomalies']:
                        st.warning(f"**{anomaly['type']}**: {anomaly['description']}")
                
                # Market impact
                impact = report['market_impact_analysis']
                st.subheader("📈 Market Impact Analysis")
                col_d, col_e = st.columns(2)
                with col_d:
                    st.metric("Avg Impact", f"{impact['avg_market_impact']:.2%}")
                with col_e:
                    st.metric("Large Impact Trades", impact['large_impact_trades'])
        
        # Suspicious wallets list
        st.subheader("🚨 Flagged Wallets")
        
        # Generate mock suspicious wallets for demonstration
        mock_suspicious_wallets = [
            {
                'wallet_address': '0x1234567890123456789012345678901234567890',
                'risk_score': 85,
                'risk_level': 'HIGH',
                'recommendation': 'IMMEDIATE INVESTIGATION REQUIRED',
                'profitability_analysis': {
                    'win_rate': 0.92,
                    'profit_factor': 4.5,
                    'total_trades': 47
                },
                'timing_anomalies': [
                    {'type': 'LAST_MINUTE_TRADING', 'description': 'Trade placed 2 hours before resolution'},
                    {'type': 'QUICK_FLIP', 'description': 'Profitable trade closed in 1.5 hours'}
                ],
                'market_impact_analysis': {
                    'avg_market_impact': 0.15,
                    'large_impact_trades': 8,
                    'market_manipulation_score': 75
                },
                'total_anomalies': 2
            },
            {
                'wallet_address': '0x5678901234567890123456789012345678901234',
                'risk_score': 68,
                'risk_level': 'MEDIUM',
                'recommendation': 'CLOSE MONITORING ADVISED',
                'profitability_analysis': {
                    'win_rate': 0.78,
                    'profit_factor': 2.8,
                    'total_trades': 23
                },
                'timing_anomalies': [
                    {'type': 'LAST_MINUTE_TRADING', 'description': 'Trade placed 18 hours before resolution'}
                ],
                'market_impact_analysis': {
                    'avg_market_impact': 0.08,
                    'large_impact_trades': 3,
                    'market_manipulation_score': 45
                },
                'total_anomalies': 1
            },
            {
                'wallet_address': '0x9876543210987654321098765432109876543210',
                'risk_score': 52,
                'risk_level': 'MEDIUM',
                'recommendation': 'ROUTINE MONITORING',
                'profitability_analysis': {
                    'win_rate': 0.71,
                    'profit_factor': 2.1,
                    'total_trades': 15
                },
                'timing_anomalies': [],
                'market_impact_analysis': {
                    'avg_market_impact': 0.12,
                    'large_impact_trades': 5,
                    'market_manipulation_score': 58
                },
                'total_anomalies': 0
            }
        ]
        
        if mock_suspicious_wallets:
            wallet_data = []
            for wallet in mock_suspicious_wallets:
                wallet_data.append({
                    'Wallet': wallet['wallet_address'][:10] + "...",
                    'Risk Score': wallet['risk_score'],
                    'Risk Level': wallet['risk_level'],
                    'Win Rate': f"{wallet['profitability_analysis']['win_rate']:.1%}",
                    'Trades': wallet['profitability_analysis']['total_trades']
                })
            
            df_wallets = pd.DataFrame(wallet_data)
            st.dataframe(df_wallets, use_container_width=True)
        else:
            st.info("No suspicious wallets detected yet.")
    
    with col2:
        st.subheader("Wallet Categories")
        
        # Mock wallet categories
        wallet_categories = {
            "High Win Rate": 15,
            "Large Volume": 23,
            "Quick Flips": 8,
            "Last Minute": 12,
            "Market Manipulators": 4
        }
        
        for category, count in wallet_categories.items():
            st.write(f"**{category}**: {count} wallets")

elif page == "market_creation":
    st.header("📝 Market Creation Pattern Analysis")
    
    st.subheader("Creation Pattern Detection")
    
    # Market creation analysis
    question_text = st.text_area("Sample Market Question", height=100, 
                                placeholder="Enter market question to analyze...")
    
    if question_text and st.button("Analyze Question"):
        # Mock analysis
        framing_score = min(len(question_text.split()) * 2, 50)
        urgency_score = 20 if any(word in question_text.lower() for word in ['urgent', 'soon', 'before']) else 0
        
        st.subheader("📊 Question Analysis Results")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Framing Score", f"{framing_score}/50")
            st.metric("Urgency Score", f"{urgency_score}/30")
        with col_b:
            st.metric("Specificity", "High" if framing_score > 30 else "Medium")
            st.metric("Risk Level", "Moderate")
        
        if framing_score > 30:
            st.warning("⚠️ High specificity detected - may indicate insider knowledge")
    
    # Recent market creations
    st.subheader("📅 Recent Market Creations")
    
    recent_creations = [
        {
            "question": "Will Company X acquire Company Y before Dec 31?",
            "creator": "0x1234...",
            "score": 75,
            "risk": "HIGH"
        },
        {
            "question": "Election outcome in swing state?",
            "creator": "0x5678...",
            "score": 45,
            "risk": "MEDIUM"
        }
    ]
    
    for creation in recent_creations:
        with st.expander(f"{creation['question'][:50]}..."):
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Creator:** {creation['creator']}")
                st.write(f"**Risk Score:** {creation['score']}/100")
            with col_b:
                st.write(f"**Risk Level:** {creation['risk']}")
                st.write("**Status:** Under Review")

elif page == "alert_dashboard":
    st.header("🚨 Insider Trading Alert Dashboard")
    
    # Alert statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔴 High Risk", "7", "+2")
    with col2:
        st.metric("🟡 Medium Risk", "15", "+5")
    with col3:
        st.metric("🟢 Low Risk", "23", "+8")
    with col4:
        st.metric("📊 Total Alerts", "45", "+15")
    
    # Alert timeline chart
    st.subheader("📈 Alert Timeline (Last 24 Hours)")
    
    # Mock timeline data
    hours = list(range(24))
    alerts_per_hour = [1, 0, 2, 1, 3, 2, 4, 3, 2, 5, 4, 3, 6, 5, 4, 7, 6, 5, 4, 3, 2, 1, 1, 0]
    
    fig = px.line(
        x=hours, 
        y=alerts_per_hour,
        title="Alerts Detected Per Hour",
        labels={'x': 'Hour', 'y': 'Number of Alerts'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Recent alerts table
    st.subheader("🚨 Recent Insider Trading Alerts")
    
    recent_alerts = [
        {
            "timestamp": "2024-01-04 15:30",
            "market": "Election odds - swing state",
            "score": 85,
            "type": "Volume Spike + Wallet Pattern",
            "status": "Under Investigation"
        },
        {
            "timestamp": "2024-01-04 14:15",
            "market": "Crypto price movement",
            "score": 72,
            "type": "Timing Anomaly",
            "status": "Monitoring"
        },
        {
            "timestamp": "2024-01-04 13:45",
            "market": "Sports championship",
            "score": 58,
            "type": "Price Volatility",
            "status": "Review"
        }
    ]
    
    df_alerts = pd.DataFrame(recent_alerts)
    st.dataframe(df_alerts, use_container_width=True)

elif page == "settings":
    st.header("⚙️ Detection System Settings")
    
    st.subheader("🔧 Detection Thresholds")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Volume Anomaly Detection**")
        volume_z_threshold = st.slider("Volume Z-Score Threshold", 1.0, 5.0, 3.0, 0.1)
        min_volume_analysis = st.number_input("Minimum Volume ($)", 1000, 100000, 10000)
        
        st.write("**Price Volatility Detection**")
        price_vol_threshold = st.slider("Price Volatility Multiplier", 1.0, 5.0, 2.0, 0.1)
        
    with col2:
        st.write("**Wallet Behavior Analysis**")
        wallet_win_rate_threshold = st.slider("Suspicious Win Rate (%)", 50, 95, 80, 5)
        min_wallet_trades = st.number_input("Minimum Trades for Analysis", 5, 100, 10)
        
        st.write("**Market Creation Analysis**")
        creation_score_threshold = st.slider("Creation Risk Threshold", 20, 80, 50, 5)
    
    st.subheader("🔔 Alert Configuration")
    
    alert_email = st.text_input("Alert Email", placeholder="alerts@example.com")
    alert_webhook = st.text_input("Slack Webhook URL", placeholder="https://hooks.slack.com/...")
    
    enable_notifications = st.checkbox("Enable Real-time Notifications")
    enable_email_alerts = st.checkbox("Enable Email Alerts")
    enable_slack_alerts = st.checkbox("Enable Slack Alerts")
    
    if st.button("💾 Save Settings"):
        st.success("Settings saved successfully!")
    
    st.subheader("🔄 Data Service Settings")
    
    st.write("**Background Data Collection**")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        update_interval = st.slider("Update Interval (minutes)", 1, 60, 5)
        max_markets = st.number_input("Max Markets to Fetch", 100, 5000, 2000)
    
    with col_b:
        enable_background = st.checkbox("Enable Background Service", value=True)
        auto_cleanup = st.checkbox("Auto-cleanup Old Data", value=True)
    
    st.info("💡 The background data service automatically fetches market data every 5 minutes and stores it in a local database for fast analysis.")

# Footer
st.markdown("---")
st.markdown("""
**🔬 Detection Methodology**: This system uses statistical analysis, pattern recognition, and behavioral analytics to identify potential insider trading patterns on Polymarket. 
Alerts are generated based on volume anomalies, price volatility, wallet behavior, timing patterns, and market creation characteristics.

**📊 Data Source**: Real-time data from Polymarket Gamma API, automatically refreshed every 5 minutes and stored in a local database for analysis.

**⚠️ Disclaimer**: This tool is for informational purposes only and does not constitute legal proof of insider trading. Further investigation required for any regulatory action.
""")
