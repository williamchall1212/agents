import requests
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import re

class MarketCreationAnalyzer:
    """
    Analyzes market creation patterns for potential insider trading indicators
    Focuses on timing, question framing, and creator behavior
    """
    
    def __init__(self, db_path: str = "insider_detection.db"):
        self.db_path = db_path
        self.init_market_creation_tables()
    
    def init_market_creation_tables(self):
        """Initialize market creation tracking tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Market creation tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_creation_log (
                condition_id TEXT PRIMARY KEY,
                creator_address TEXT,
                creation_timestamp TIMESTAMP,
                question TEXT,
                category TEXT,
                end_date TIMESTAMP,
                initial_liquidity REAL,
                question_length INTEGER,
                has_specific_dates BOOLEAN,
                has_specific_numbers BOOLEAN,
                urgency_score REAL,
                insider_creation_score REAL
            )
        ''')
        
        # Creator behavior tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS creator_profiles (
                creator_address TEXT PRIMARY KEY,
                first_creation TIMESTAMP,
                total_markets_created INTEGER,
                successful_markets INTEGER,
                avg_initial_liquidity REAL,
                urgency_tendency REAL,
                insider_score REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def analyze_question_framing(self, question: str) -> Dict:
        """Analyze question wording for insider indicators"""
        question_lower = question.lower()
        
        # Specific indicators
        has_specific_dates = bool(re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/\d{1,2}|\d{4})\b', question_lower))
        has_specific_numbers = bool(re.search(r'\b\d+\b', question))
        
        # Urgency indicators
        urgency_words = ['urgent', 'immediate', 'soon', 'within', 'before', 'by', 'asap', 'quickly']
        urgency_count = sum(1 for word in urgency_words if word in question_lower)
        urgency_score = min(urgency_count * 10, 50)  # Max 50 points
        
        # Specificity indicators (could indicate insider knowledge)
        specificity_indicators = [
            'exactly', 'precisely', 'specifically', 'particular',
            'certain', 'definite', 'guaranteed', 'will', 'shall'
        ]
        specificity_count = sum(1 for word in specificity_indicators if word in question_lower)
        specificity_score = min(specificity_count * 15, 45)
        
        # Question length (very specific questions might indicate insider knowledge)
        question_length = len(question.split())
        length_score = min(question_length * 2, 30) if question_length > 20 else 0
        
        return {
            'has_specific_dates': has_specific_dates,
            'has_specific_numbers': has_specific_numbers,
            'urgency_score': urgency_score,
            'specificity_score': specificity_score,
            'length_score': length_score,
            'total_framing_score': urgency_score + specificity_score + length_score
        }
    
    def analyze_creation_timing(self, creation_time: datetime, end_date: datetime) -> Dict:
        """Analyze market creation timing for suspicious patterns"""
        now = datetime.now()
        
        # Time until market resolution
        time_to_resolution = (end_date - creation_time).total_seconds() / 86400  # days
        
        # Creation relative to external events
        weekday = creation_time.weekday()  # 0=Monday, 6=Sunday
        hour = creation_time.hour
        
        # Suspicious timing indicators
        timing_score = 0
        timing_reasons = []
        
        # Markets created very close to resolution (might be based on insider knowledge)
        if time_to_resolution < 7:
            timing_score += 30
            timing_reasons.append("Created very close to resolution date")
        elif time_to_resolution < 30:
            timing_score += 15
            timing_reasons.append("Created relatively close to resolution")
        
        # Markets created during unusual hours (might indicate rushed insider creation)
        if hour < 6 or hour > 22:
            timing_score += 20
            timing_reasons.append(f"Created at unusual hour: {hour}:00")
        
        # Weekend creation (less common, might be urgent)
        if weekday >= 5:  # Saturday or Sunday
            timing_score += 10
            timing_reasons.append("Created on weekend")
        
        return {
            'time_to_resolution_days': time_to_resolution,
            'creation_hour': hour,
            'creation_weekday': weekday,
            'timing_score': min(timing_score, 50),
            'timing_reasons': timing_reasons
        }
    
    def analyze_creator_behavior(self, creator_address: str) -> Dict:
        """Analyze creator's historical behavior patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get creator's market creation history
        cursor.execute('''
            SELECT creation_timestamp, initial_liquidity, urgency_score, insider_creation_score
            FROM market_creation_log
            WHERE creator_address = ?
            ORDER BY creation_timestamp DESC
        ''', (creator_address,))
        
        creations = cursor.fetchall()
        conn.close()
        
        if not creations:
            return {
                'total_markets': 0,
                'avg_liquidity': 0,
                'urgency_tendency': 0,
                'insider_tendency': 0,
                'creator_score': 0
            }
        
        total_markets = len(creations)
        avg_liquidity = np.mean([c[1] for c in creations if c[1]]) if creations else 0
        urgency_tendency = np.mean([c[2] for c in creations if c[2]]) if creations else 0
        insider_tendency = np.mean([c[3] for c in creations if c[3]]) if creations else 0
        
        # Creator behavior scoring
        creator_score = 0
        
        # High urgency tendency
        if urgency_tendency > 30:
            creator_score += 25
        
        # High insider creation scores
        if insider_tendency > 40:
            creator_score += 35
        
        # Many markets (could indicate systematic insider activity)
        if total_markets > 50:
            creator_score += 20
        elif total_markets > 20:
            creator_score += 10
        
        # Low average liquidity (might indicate quick, low-effort insider markets)
        if avg_liquidity < 1000:
            creator_score += 15
        
        return {
            'total_markets': total_markets,
            'avg_liquidity': avg_liquidity,
            'urgency_tendency': urgency_tendency,
            'insider_tendency': insider_tendency,
            'creator_score': min(creator_score, 100)
        }
    
    def detect_market_creation_anomaly(self, market_data: Dict) -> Dict:
        """Comprehensive market creation anomaly detection"""
        condition_id = market_data.get('conditionId', 'N/A')
        question = market_data.get('question', '')
        creator_address = market_data.get('creator', 'unknown')
        
        # Parse timestamps
        creation_time = datetime.now()  # Simplified - would use actual creation time
        end_date_str = market_data.get('endDate', '')
        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except:
            end_date = creation_time + timedelta(days=30)  # Default
        
        # Analyze question framing
        framing_analysis = self.analyze_question_framing(question)
        
        # Analyze creation timing
        timing_analysis = self.analyze_creation_timing(creation_time, end_date)
        
        # Analyze creator behavior
        creator_analysis = self.analyze_creator_behavior(creator_address)
        
        # Initial liquidity analysis
        initial_liquidity = float(market_data.get('liquidity', 0))
        liquidity_score = 0
        if initial_liquidity < 500:
            liquidity_score = 20  # Very low liquidity
        elif initial_liquidity < 1000:
            liquidity_score = 10  # Low liquidity
        
        # Composite insider creation score
        insider_creation_score = (
            framing_analysis['total_framing_score'] * 0.3 +
            timing_analysis['timing_score'] * 0.25 +
            creator_analysis['creator_score'] * 0.25 +
            liquidity_score * 0.2
        )
        
        # Determine anomaly level
        if insider_creation_score >= 70:
            anomaly_level = "EXTREME"
            recommendation = "IMMEDIATE INVESTIGATION"
        elif insider_creation_score >= 50:
            anomaly_level = "HIGH"
            recommendation = "PRIORITY MONITORING"
        elif insider_creation_score >= 30:
            anomaly_level = "MODERATE"
            recommendation = "ROUTINE MONITORING"
        else:
            anomaly_level = "LOW"
            recommendation = "NO CONCERN"
        
        return {
            'condition_id': condition_id,
            'question': question,
            'creator_address': creator_address,
            'insider_creation_score': min(100, insider_creation_score),
            'anomaly_level': anomaly_level,
            'recommendation': recommendation,
            'framing_analysis': framing_analysis,
            'timing_analysis': timing_analysis,
            'creator_analysis': creator_analysis,
            'liquidity_score': liquidity_score,
            'initial_liquidity': initial_liquidity,
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def flag_suspicious_market_creations(self, min_score: float = 30) -> List[Dict]:
        """Flag markets with suspicious creation patterns"""
        # This would scan all markets and flag suspicious ones
        # For demo purposes, return empty list
        return []

def main():
    """Test market creation analyzer"""
    analyzer = MarketCreationAnalyzer()
    
    # Example market data
    test_market = {
        'conditionId': 'test123',
        'question': 'Will Company X announce acquisition of Company Y before December 31, 2025 for exactly $2.5 billion?',
        'creator': '0x1234567890123456789012345678901234567890',
        'endDate': '2025-12-31T23:59:59Z',
        'liquidity': 500
    }
    
    result = analyzer.detect_market_creation_anomaly(test_market)
    
    print("🔍 Market Creation Analysis:")
    print(f"Question: {result['question'][:60]}...")
    print(f"Insider Creation Score: {result['insider_creation_score']:.1f}/100")
    print(f"Anomaly Level: {result['anomaly_level']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Framing Score: {result['framing_analysis']['total_framing_score']}")
    print(f"Timing Score: {result['timing_analysis']['timing_score']}")
    print(f"Creator Score: {result['creator_analysis']['creator_score']}")

if __name__ == "__main__":
    main()
