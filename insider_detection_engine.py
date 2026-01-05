import requests
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sqlite3
import logging

class InsiderTradingDetector:
    """
    Advanced insider trading detection system for Polymarket
    Implements volume spike detection, wallet analysis, and timing anomalies
    """
    
    def __init__(self, db_path: str = "insider_detection.db"):
        self.gamma_url = "https://gamma-api.polymarket.com"
        self.clob_url = "https://clob.polymarket.com"
        self.db_path = db_path
        self.init_database()
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def init_database(self):
        """Initialize SQLite database for storing historical data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Markets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                condition_id TEXT PRIMARY KEY,
                question TEXT,
                category TEXT,
                created_at TIMESTAMP,
                end_date TIMESTAMP,
                active BOOLEAN
            )
        ''')
        
        # Volume history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS volume_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT,
                volume_24h REAL,
                timestamp TIMESTAMP,
                FOREIGN KEY (condition_id) REFERENCES markets (condition_id)
            )
        ''')
        
        # Price history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT,
                yes_prob REAL,
                timestamp TIMESTAMP,
                FOREIGN KEY (condition_id) REFERENCES markets (condition_id)
            )
        ''')
        
        # Wallet tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT,
                condition_id TEXT,
                trade_amount REAL,
                trade_type TEXT,
                timestamp TIMESTAMP,
                outcome_index INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_current_markets(self) -> List[Dict]:
        """Fetch current active markets from Polymarket API"""
        try:
            response = requests.get(f"{self.gamma_url}/markets", params={
                "active": "true",
                "closed": "false",
                "limit": 1000
            })
            
            if response.status_code == 200:
                markets = response.json()
                self.logger.info(f"Fetched {len(markets)} active markets")
                return markets
            else:
                self.logger.error(f"API error: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error fetching markets: {e}")
            return []
    
    def calculate_volume_zscore(self, current_volume: float, historical_volumes: List[float]) -> float:
        """Calculate Z-score for volume anomaly detection"""
        if len(historical_volumes) < 3:
            return 0.0
        
        mean_vol = np.mean(historical_volumes)
        std_vol = np.std(historical_volumes)
        
        if std_vol == 0:
            return 0.0
        
        z_score = (current_volume - mean_vol) / std_vol
        return max(0, z_score)  # Only positive anomalies (spikes)
    
    def detect_volume_anomaly(self, condition_id: str, current_volume: float) -> Tuple[float, str]:
        """Detect volume anomalies with detailed analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get last 30 days of volume data
        cursor.execute('''
            SELECT volume_24h FROM volume_history 
            WHERE condition_id = ? AND timestamp >= datetime('now', '-30 days')
            ORDER BY timestamp DESC
        ''', (condition_id,))
        
        historical_volumes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if len(historical_volumes) < 5:
            return 0.0, "Insufficient historical data"
        
        z_score = self.calculate_volume_zscore(current_volume, historical_volumes)
        
        # Determine anomaly level
        if z_score > 4:
            level = "EXTREME"
            description = f"Volume spike {z_score:.1f}σ above normal (extremely unusual)"
        elif z_score > 3:
            level = "HIGH"
            description = f"Volume spike {z_score:.1f}σ above normal (highly unusual)"
        elif z_score > 2:
            level = "MODERATE"
            description = f"Volume spike {z_score:.1f}σ above normal (unusual)"
        else:
            level = "NORMAL"
            description = "Normal trading volume"
        
        return z_score, description
    
    def analyze_price_volatility(self, condition_id: str, current_price: float) -> Tuple[float, str]:
        """Analyze price volatility for sudden movements"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get last 24 hours of price data
        cursor.execute('''
            SELECT yes_prob FROM price_history 
            WHERE condition_id = ? AND timestamp >= datetime('now', '-1 day')
            ORDER BY timestamp ASC
        ''', (condition_id,))
        
        price_history = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if len(price_history) < 2:
            return 0.0, "Insufficient price history"
        
        # Calculate price changes
        price_changes = []
        for i in range(1, len(price_history)):
            change = abs(price_history[i] - price_history[i-1])
            price_changes.append(change)
        
        if not price_changes:
            return 0.0, "No price changes detected"
        
        avg_change = np.mean(price_changes)
        current_change = abs(current_price - price_history[-1]) if price_history else 0
        
        # Detect volatility spike
        volatility_ratio = current_change / avg_change if avg_change > 0 else 0
        
        if volatility_ratio > 3:
            level = "HIGH"
            description = f"Price move {volatility_ratio:.1f}x above normal volatility"
        elif volatility_ratio > 2:
            level = "MODERATE"
            description = f"Price move {volatility_ratio:.1f}x above normal volatility"
        else:
            level = "NORMAL"
            description = "Normal price movement"
        
        return volatility_ratio, description
    
    def detect_wallet_anomalies(self, condition_id: str) -> List[Dict]:
        """Detect suspicious wallet activity patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent wallet activity for this market
        cursor.execute('''
            SELECT wallet_address, trade_amount, trade_type, timestamp, outcome_index
            FROM wallet_activity 
            WHERE condition_id = ? AND timestamp >= datetime('now', '-7 days')
            ORDER BY timestamp DESC
        ''', (condition_id,))
        
        activities = cursor.fetchall()
        conn.close()
        
        if not activities:
            return []
        
        # Analyze wallet patterns
        wallet_stats = {}
        for addr, amount, trade_type, timestamp, outcome_idx in activities:
            if addr not in wallet_stats:
                wallet_stats[addr] = {
                    'total_volume': 0,
                    'trade_count': 0,
                    'large_trades': 0,
                    'timing_score': 0
                }
            
            wallet_stats[addr]['total_volume'] += amount
            wallet_stats[addr]['trade_count'] += 1
            
            # Flag large trades (> $1000)
            if amount > 1000:
                wallet_stats[addr]['large_trades'] += 1
        
        anomalies = []
        for addr, stats in wallet_stats.items():
            # High concentration from single wallet
            if stats['total_volume'] > 10000 and stats['trade_count'] <= 5:
                anomalies.append({
                    'type': 'HIGH_CONCENTRATION',
                    'wallet': addr,
                    'description': f"Wallet {addr[:8]}... concentrated ${stats['total_volume']:,.0f} in {stats['trade_count']} trades",
                    'severity': 'HIGH'
                })
            
            # Many large trades
            if stats['large_trades'] >= 3:
                anomalies.append({
                    'type': 'LARGE_TRADES',
                    'wallet': addr,
                    'description': f"Wallet {addr[:8]}... made {stats['large_trades']} trades >$1000",
                    'severity': 'MEDIUM'
                })
        
        return anomalies
    
    def generate_composite_alert(self, market_data: Dict) -> Dict:
        """Generate comprehensive insider trading alert"""
        condition_id = market_data.get('conditionId', 'N/A')
        question = market_data.get('question', 'Unknown')
        current_volume = float(market_data.get('volume24hr', 0))
        current_price = float(json.loads(market_data.get('outcomePrices', '[0.5]'))[0])
        
        # Run all detection modules
        volume_zscore, volume_desc = self.detect_volume_anomaly(condition_id, current_volume)
        price_vol_ratio, price_desc = self.analyze_price_volatility(condition_id, current_price)
        wallet_anomalies = self.detect_wallet_anomalies(condition_id)
        
        # Calculate composite score
        score = 0
        alerts = []
        
        # Volume anomaly (40% weight)
        if volume_zscore > 3:
            score += 40
            alerts.append(volume_desc)
        elif volume_zscore > 2:
            score += 25
            alerts.append(volume_desc)
        
        # Price volatility (25% weight)
        if price_vol_ratio > 3:
            score += 25
            alerts.append(price_desc)
        elif price_vol_ratio > 2:
            score += 15
            alerts.append(price_desc)
        
        # Wallet anomalies (25% weight)
        high_severity_wallets = [a for a in wallet_anomalies if a['severity'] == 'HIGH']
        medium_severity_wallets = [a for a in wallet_anomalies if a['severity'] == 'MEDIUM']
        
        if high_severity_wallets:
            score += 25
            alerts.extend([a['description'] for a in high_severity_wallets])
        elif medium_severity_wallets:
            score += 15
            alerts.extend([a['description'] for a in medium_severity_wallets])
        
        # Liquidity analysis (10% weight)
        liquidity = float(market_data.get('liquidity', 0))
        if liquidity < 1000 and current_volume > 5000:
            score += 10
            alerts.append("High volume in low liquidity market")
        
        return {
            'condition_id': condition_id,
            'question': question,
            'alert_score': min(100, score),
            'alerts': alerts,
            'volume_zscore': volume_zscore,
            'price_volatility': price_vol_ratio,
            'wallet_anomalies': wallet_anomalies,
            'current_volume': current_volume,
            'current_price': current_price,
            'timestamp': datetime.now().isoformat()
        }
    
    def scan_markets(self, min_volume: float = 10000) -> List[Dict]:
        """Scan all markets for insider trading patterns"""
        markets = self.get_current_markets()
        alerts = []
        
        for market in markets:
            try:
                volume = float(market.get('volume24hr', 0))
                if volume >= min_volume:
                    alert = self.generate_composite_alert(market)
                    if alert['alert_score'] > 30:  # Minimum threshold
                        alerts.append(alert)
            except Exception as e:
                self.logger.error(f"Error processing market {market.get('conditionId')}: {e}")
                continue
        
        # Sort by alert score
        alerts.sort(key=lambda x: x['alert_score'], reverse=True)
        self.logger.info(f"Generated {len(alerts)} insider trading alerts")
        
        return alerts
    
    def store_market_data(self, market_data: Dict):
        """Store market data in database for historical analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        condition_id = market_data.get('conditionId')
        
        # Store market info
        cursor.execute('''
            INSERT OR REPLACE INTO markets 
            (condition_id, question, category, created_at, end_date, active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            condition_id,
            market_data.get('question'),
            market_data.get('category'),
            datetime.now(),
            market_data.get('endDate'),
            market_data.get('active', True)
        ))
        
        # Store volume data
        cursor.execute('''
            INSERT INTO volume_history 
            (condition_id, volume_24h, timestamp)
            VALUES (?, ?, ?)
        ''', (
            condition_id,
            float(market_data.get('volume24hr', 0)),
            datetime.now()
        ))
        
        # Store price data
        prices = json.loads(market_data.get('outcomePrices', '[0.5]'))
        cursor.execute('''
            INSERT INTO price_history 
            (condition_id, yes_prob, timestamp)
            VALUES (?, ?, ?)
        ''', (
            condition_id,
            float(prices[0]),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()

def main():
    """Main execution function"""
    detector = InsiderTradingDetector()
    
    print("🔍 Starting insider trading detection scan...")
    
    # Get current markets and store data
    markets = detector.get_current_markets()
    print(f"Fetched {len(markets)} active markets")
    
    # Store current data for historical analysis
    for market in markets[:10]:  # Store first 10 for demo
        detector.store_market_data(market)
    
    # Run detection scan
    alerts = detector.scan_markets(min_volume=5000)
    
    print(f"\n📊 Detection Results:")
    print(f"Total alerts generated: {len(alerts)}")
    
    if alerts:
        print(f"\n🚨 Top 5 Insider Trading Alerts:")
        for i, alert in enumerate(alerts[:5], 1):
            print(f"\n{i}. Alert Score: {alert['alert_score']}/100")
            print(f"   Market: {alert['question'][:80]}...")
            print(f"   Volume Z-score: {alert['volume_zscore']:.2f}")
            print(f"   Price Volatility: {alert['price_volatility']:.2f}x")
            print(f"   Alerts: {len(alert['alerts'])}")
            for alert_msg in alert['alerts']:
                print(f"   - {alert_msg}")
    else:
        print("No significant insider trading alerts detected.")

if __name__ == "__main__":
    main()
