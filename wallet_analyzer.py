import requests
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3

class WalletAnalyzer:
    """
    Advanced wallet behavior analysis for insider trading detection
    Tracks profitability, timing patterns, and suspicious activity
    """
    
    def __init__(self, db_path: str = "insider_detection.db"):
        self.db_path = db_path
        self.init_wallet_tables()
    
    def init_wallet_tables(self):
        """Initialize wallet tracking tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced wallet tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_profiles (
                wallet_address TEXT PRIMARY KEY,
                first_seen TIMESTAMP,
                last_active TIMESTAMP,
                total_trades INTEGER,
                total_volume REAL,
                profitable_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                avg_trade_size REAL,
                largest_trade REAL,
                risk_score REAL,
                insider_score REAL
            )
        ''')
        
        # Trade outcomes tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT,
                condition_id TEXT,
                entry_price REAL,
                exit_price REAL,
                trade_amount REAL,
                profit_loss REAL,
                outcome TEXT,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                hold_duration_hours REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def analyze_wallet_profitability(self, wallet_address: str) -> Dict:
        """Analyze wallet's trading profitability and patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get wallet's trade history
        cursor.execute('''
            SELECT profit_loss, trade_amount, entry_time, exit_time, hold_duration_hours
            FROM trade_outcomes 
            WHERE wallet_address = ?
            ORDER BY entry_time DESC
        ''', (wallet_address,))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'max_profit': 0.0,
                'avg_hold_time': 0.0,
                'profit_factor': 0.0,
                'insider_score': 0.0
            }
        
        # Calculate metrics
        profits = [trade[0] for trade in trades]
        amounts = [trade[1] for trade in trades]
        hold_times = [trade[4] for trade in trades if trade[4]]
        
        profitable_trades = len([p for p in profits if p > 0])
        total_trades = len(trades)
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        avg_profit = np.mean(profits) if profits else 0
        max_profit = max(profits) if profits else 0
        avg_hold_time = np.mean(hold_times) if hold_times else 0
        
        # Profit factor (total profits / total losses)
        total_profits = sum([p for p in profits if p > 0])
        total_losses = abs(sum([p for p in profits if p < 0]))
        profit_factor = total_profits / total_losses if total_losses > 0 else float('inf') if total_profits > 0 else 0
        
        # Insider trading score based on profitability patterns
        insider_score = 0
        
        # Extremely high win rate (>80% with 10+ trades)
        if win_rate > 0.8 and total_trades >= 10:
            insider_score += 30
        
        # Consistent profitability (profit factor > 3)
        if profit_factor > 3:
            insider_score += 25
        
        # Large average profits
        if avg_profit > 1000:
            insider_score += 20
        
        # Quick profitable exits (profitable trades held < 24 hours)
        quick_profits = [trade for trade in trades if trade[0] > 0 and trade[4] and trade[4] < 24]
        if len(quick_profits) / profitable_trades > 0.7 if profitable_trades > 0 else 0:
            insider_score += 15
        
        # Large trade concentration
        max_trade = max(amounts) if amounts else 0
        if max_trade > 10000:
            insider_score += 10
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'max_profit': max_profit,
            'avg_hold_time': avg_hold_time,
            'profit_factor': profit_factor,
            'insider_score': min(100, insider_score),
            'quick_profit_ratio': len(quick_profits) / profitable_trades if profitable_trades > 0 else 0
        }
    
    def detect_timing_anomalies(self, wallet_address: str) -> List[Dict]:
        """Detect suspicious timing patterns in wallet trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get wallet's trades with market timing
        cursor.execute('''
            SELECT wo.condition_id, wo.entry_time, wo.exit_time, wo.hold_duration_hours,
                   m.end_date, m.question
            FROM trade_outcomes wo
            JOIN markets m ON wo.condition_id = m.condition_id
            WHERE wo.wallet_address = ?
            ORDER BY wo.entry_time DESC
        ''', (wallet_address,))
        
        trades = cursor.fetchall()
        conn.close()
        
        anomalies = []
        
        for trade in trades:
            condition_id, entry_time, exit_time, hold_duration, market_end, question = trade
            
            # Convert timestamps
            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00')) if isinstance(entry_time, str) else entry_time
            market_end_dt = datetime.fromisoformat(market_end.replace('Z', '+00:00')) if isinstance(market_end, str) else market_end
            
            # Check for trades just before market resolution
            time_to_resolution = (market_end_dt - entry_dt).total_seconds() / 3600  # hours
            
            if time_to_resolution < 24 and time_to_resolution > 0:
                anomalies.append({
                    'type': 'LAST_MINUTE_TRADING',
                    'description': f"Trade placed {time_to_resolution:.1f} hours before market resolution",
                    'severity': 'HIGH' if time_to_resolution < 6 else 'MEDIUM',
                    'market': question[:50] + '...',
                    'condition_id': condition_id
                })
            
            # Check for unusually quick profitable exits
            if hold_duration and hold_duration < 2:
                anomalies.append({
                    'type': 'QUICK_FLIP',
                    'description': f"Profitable trade closed in {hold_duration:.1f} hours",
                    'severity': 'MEDIUM',
                    'market': question[:50] + '...',
                    'condition_id': condition_id
                })
        
        return anomalies
    
    def analyze_market_impact(self, wallet_address: str) -> Dict:
        """Analyze wallet's impact on market prices and liquidity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get wallet's trade sizes relative to market liquidity
        cursor.execute('''
            SELECT wa.trade_amount, wa.condition_id, wa.timestamp,
                   m.liquidity, m.volume24hr
            FROM wallet_activity wa
            JOIN markets m ON wa.condition_id = m.condition_id
            WHERE wa.wallet_address = ?
            ORDER BY wa.timestamp DESC
        ''', (wallet_address,))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return {
                'avg_market_impact': 0.0,
                'large_impact_trades': 0,
                'market_manipulation_score': 0.0
            }
        
        large_impact_trades = 0
        impact_ratios = []
        
        for trade_amount, condition_id, timestamp, liquidity, volume_24h in trades:
            # Calculate market impact ratio
            market_liquidity = liquidity if liquidity > 0 else volume_24h * 0.1  # Estimate
            impact_ratio = trade_amount / market_liquidity if market_liquidity > 0 else 0
            impact_ratios.append(impact_ratio)
            
            # Flag large impact trades (>10% of market liquidity)
            if impact_ratio > 0.1:
                large_impact_trades += 1
        
        avg_market_impact = np.mean(impact_ratios) if impact_ratios else 0
        
        # Market manipulation score
        manipulation_score = 0
        if avg_market_impact > 0.05:  # High average impact
            manipulation_score += 30
        if large_impact_trades > 3:  # Multiple large impact trades
            manipulation_score += 25
        if max(impact_ratios) > 0.2 if impact_ratios else 0:  # Very large single trade
            manipulation_score += 20
        
        return {
            'avg_market_impact': avg_market_impact,
            'large_impact_trades': large_impact_trades,
            'market_manipulation_score': min(100, manipulation_score),
            'max_impact_ratio': max(impact_ratios) if impact_ratios else 0
        }
    
    def generate_wallet_report(self, wallet_address: str) -> Dict:
        """Generate comprehensive wallet analysis report"""
        profitability = self.analyze_wallet_profitability(wallet_address)
        timing_anomalies = self.detect_timing_anomalies(wallet_address)
        market_impact = self.analyze_market_impact(wallet_address)
        
        # Calculate overall risk score
        risk_score = (
            profitability['insider_score'] * 0.4 +
            market_impact['market_manipulation_score'] * 0.3 +
            (len(timing_anomalies) * 10) * 0.3
        )
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
            recommendation = "IMMEDIATE INVESTIGATION REQUIRED"
        elif risk_score >= 50:
            risk_level = "MEDIUM"
            recommendation = "CLOSE MONITORING ADVISED"
        elif risk_score >= 30:
            risk_level = "LOW"
            recommendation = "ROUTINE MONITORING"
        else:
            risk_level = "NORMAL"
            recommendation = "NO CONCERN"
        
        return {
            'wallet_address': wallet_address,
            'risk_score': min(100, risk_score),
            'risk_level': risk_level,
            'recommendation': recommendation,
            'profitability_analysis': profitability,
            'timing_anomalies': timing_anomalies,
            'market_impact_analysis': market_impact,
            'total_anomalies': len(timing_anomalies),
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def flag_suspicious_wallets(self, min_trades: int = 10) -> List[Dict]:
        """Flag wallets with suspicious trading patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get wallets with sufficient trading activity
        cursor.execute('''
            SELECT DISTINCT wallet_address 
            FROM trade_outcomes 
            GROUP BY wallet_address 
            HAVING COUNT(*) >= ?
        ''', (min_trades,))
        
        wallets = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        suspicious_wallets = []
        
        for wallet in wallets:
            report = self.generate_wallet_report(wallet)
            if report['risk_score'] >= 30:  # Minimum threshold
                suspicious_wallets.append(report)
        
        # Sort by risk score
        suspicious_wallets.sort(key=lambda x: x['risk_score'], reverse=True)
        
        return suspicious_wallets

def main():
    """Test wallet analyzer"""
    analyzer = WalletAnalyzer()
    
    print("🔍 Analyzing wallet patterns for insider trading...")
    
    # Example: Analyze a specific wallet
    test_wallet = "0x1234567890123456789012345678901234567890"
    report = analyzer.generate_wallet_report(test_wallet)
    
    print(f"\n📊 Wallet Analysis Report:")
    print(f"Wallet: {report['wallet_address'][:10]}...")
    print(f"Risk Score: {report['risk_score']}/100 ({report['risk_level']})")
    print(f"Recommendation: {report['recommendation']}")
    print(f"Win Rate: {report['profitability_analysis']['win_rate']:.1%}")
    print(f"Profit Factor: {report['profitability_analysis']['profit_factor']:.2f}")
    print(f"Timing Anomalies: {report['total_anomalies']}")
    print(f"Market Manipulation Score: {report['market_impact_analysis']['market_manipulation_score']}/100")
    
    # Flag all suspicious wallets
    suspicious = analyzer.flag_suspicious_wallets(min_trades=5)
    print(f"\n🚨 Found {len(suspicious)} suspicious wallets")

if __name__ == "__main__":
    main()
