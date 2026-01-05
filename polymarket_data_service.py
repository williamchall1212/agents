import requests
import json
import time
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import schedule

class PolymarketDataService:
    """
    Background service that continuously fetches Polymarket data
    and stores it in a structured database for analysis
    """
    
    def __init__(self, db_path: str = "polymarket_data.db"):
        self.db_path = db_path
        self.base_url = "https://gamma-api.polymarket.com/markets"
        self.setup_logging()
        self.init_database()
        self.running = False
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('polymarket_data_service.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def init_database(self):
        """Initialize database tables for market data storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Current markets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_markets (
                condition_id TEXT PRIMARY KEY,
                question TEXT,
                description TEXT,
                category TEXT,
                end_date TEXT,
                active BOOLEAN,
                volume_24h REAL,
                volume_total REAL,
                liquidity REAL,
                outcome_prices TEXT,
                clob_token_ids TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                fetch_timestamp TIMESTAMP
            )
        ''')
        
        # Historical market data for trend analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT,
                volume_24h REAL,
                liquidity REAL,
                outcome_prices TEXT,
                fetch_timestamp TIMESTAMP,
                FOREIGN KEY (condition_id) REFERENCES current_markets (condition_id)
            )
        ''')
        
        # Market creation tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_creations (
                condition_id TEXT PRIMARY KEY,
                first_seen TIMESTAMP,
                creator_address TEXT,
                initial_liquidity REAL,
                question TEXT,
                category TEXT
            )
        ''')
        
        # Data fetch log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_timestamp TIMESTAMP,
                markets_fetched INTEGER,
                markets_active INTEGER,
                fetch_duration_seconds REAL,
                success BOOLEAN,
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info("Database initialized successfully")
    
    def fetch_markets_from_api(self) -> List[Dict]:
        """Fetch all active markets from Polymarket API"""
        start_time = time.time()
        all_markets = []
        offset = 0
        limit = 500
        
        try:
            while True:
                response = requests.get(self.base_url, params={
                    "closed": "false",
                    "active": "true",
                    "limit": limit,
                    "offset": offset
                }, timeout=30)
                
                if response.status_code != 200:
                    self.logger.error(f"API error: {response.status_code} - {response.text}")
                    break
                
                markets_batch = response.json()
                if not markets_batch:
                    break
                
                all_markets.extend(markets_batch)
                self.logger.info(f"Fetched {len(markets_batch)} markets (total: {len(all_markets)})")
                
                offset += len(markets_batch)
                if len(markets_batch) < limit:
                    break
                
                # Rate limiting
                time.sleep(0.2)
            
            fetch_duration = time.time() - start_time
            self.logger.info(f"Successfully fetched {len(all_markets)} markets in {fetch_duration:.2f} seconds")
            
            return all_markets
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch markets: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error during fetch: {str(e)}")
            return []
    
    def store_market_data(self, markets: List[Dict], fetch_duration: float = None) -> bool:
        """Store fetched market data in database"""
        if not markets:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            fetch_timestamp = datetime.now()
            new_markets = 0
            updated_markets = 0
            
            for market in markets:
                try:
                    # Extract market data
                    condition_id = market.get('conditionId', '')
                    question = market.get('question', '')
                    description = market.get('description', '')
                    category = market.get('category', 'Uncategorized')
                    end_date = market.get('endDate', '')
                    active = market.get('active', True)
                    volume_24h = float(market.get('volume24hr', 0))
                    volume_total = float(market.get('volume', 0))
                    liquidity = float(market.get('liquidity', 0))
                    outcome_prices = market.get('outcomePrices', '[0.5, 0.5]')
                    clob_token_ids = market.get('clobTokenIds', '[]')
                    
                    # Check if market exists
                    cursor.execute('SELECT condition_id FROM current_markets WHERE condition_id = ?', (condition_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing market
                        cursor.execute('''
                            UPDATE current_markets 
                            SET question = ?, description = ?, category = ?, end_date = ?, 
                                active = ?, volume_24h = ?, volume_total = ?, liquidity = ?, 
                                outcome_prices = ?, clob_token_ids = ?, updated_at = ?, fetch_timestamp = ?
                            WHERE condition_id = ?
                        ''', (question, description, category, end_date, active, volume_24h, 
                              volume_total, liquidity, outcome_prices, clob_token_ids, 
                              datetime.now(), fetch_timestamp, condition_id))
                        updated_markets += 1
                    else:
                        # Insert new market
                        cursor.execute('''
                            INSERT INTO current_markets 
                            (condition_id, question, description, category, end_date, active, 
                             volume_24h, volume_total, liquidity, outcome_prices, clob_token_ids, 
                             created_at, updated_at, fetch_timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (condition_id, question, description, category, end_date, active,
                              volume_24h, volume_total, liquidity, outcome_prices, clob_token_ids,
                              datetime.now(), datetime.now(), fetch_timestamp))
                        new_markets += 1
                        
                        # Track market creation
                        cursor.execute('''
                            INSERT OR IGNORE INTO market_creations 
                            (condition_id, first_seen, creator_address, initial_liquidity, question, category)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (condition_id, fetch_timestamp, 'unknown', liquidity, question, category))
                    
                    # Store historical data point
                    cursor.execute('''
                        INSERT INTO market_history 
                        (condition_id, volume_24h, liquidity, outcome_prices, fetch_timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (condition_id, volume_24h, liquidity, outcome_prices, fetch_timestamp))
                
                except Exception as e:
                    self.logger.error(f"Error processing market {condition_id}: {str(e)}")
                    continue
            
            # Log the fetch
            cursor.execute('''
                INSERT INTO fetch_log 
                (fetch_timestamp, markets_fetched, markets_active, fetch_duration_seconds, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (fetch_timestamp, len(markets), len([m for m in markets if m.get('active', False)]),
                  fetch_duration if fetch_duration else 0, True, None))
            
            conn.commit()
            self.logger.info(f"Stored {len(markets)} markets: {new_markets} new, {updated_markets} updated")
            
            # Clean old historical data (keep last 7 days)
            cursor.execute('DELETE FROM market_history WHERE fetch_timestamp < datetime("now", "-7 days")')
            conn.commit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing market data: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def fetch_and_store(self) -> bool:
        """Main method to fetch and store market data"""
        self.logger.info("Starting market data fetch cycle")
        
        # Fetch data from API
        start_time = time.time()
        markets = self.fetch_markets_from_api()
        fetch_duration = time.time() - start_time
        
        if not markets:
            self.logger.error("No markets fetched from API")
            return False
        
        # Store in database
        success = self.store_market_data(markets, fetch_duration)
        
        if success:
            self.logger.info("Market data fetch cycle completed successfully")
        else:
            self.logger.error("Failed to store market data")
        
        return success
    
    def get_latest_markets(self, min_volume: float = 0, limit: int = 100) -> List[Dict]:
        """Get latest market data from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT condition_id, question, description, category, end_date, active,
                       volume_24h, volume_total, liquidity, outcome_prices, clob_token_ids,
                       fetch_timestamp
                FROM current_markets 
                WHERE active = true AND volume_24h >= ?
                ORDER BY volume_24h DESC
                LIMIT ?
            ''', (min_volume, limit))
            
            columns = [description[0] for description in cursor.description]
            markets = []
            
            for row in cursor.fetchall():
                market = dict(zip(columns, row))
                markets.append(market)
            
            return markets
            
        except Exception as e:
            self.logger.error(f"Error retrieving markets from database: {str(e)}")
            return []
        finally:
            conn.close()
    
    def get_market_history(self, condition_id: str, days: int = 7) -> List[Dict]:
        """Get historical data for a specific market"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT volume_24h, liquidity, outcome_prices, fetch_timestamp
                FROM market_history 
                WHERE condition_id = ? AND fetch_timestamp >= datetime("now", "-{} days")
                ORDER BY fetch_timestamp ASC
            '''.format(days), (condition_id,))
            
            columns = [description[0] for description in cursor.description]
            history = []
            
            for row in cursor.fetchall():
                data_point = dict(zip(columns, row))
                history.append(data_point)
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error retrieving market history: {str(e)}")
            return []
        finally:
            conn.close()
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Total markets
            cursor.execute('SELECT COUNT(*) FROM current_markets WHERE active = true')
            total_active = cursor.fetchone()[0]
            
            # Last fetch time
            cursor.execute('SELECT MAX(fetch_timestamp) FROM current_markets')
            last_fetch = cursor.fetchone()[0]
            
            # Fetch history
            cursor.execute('SELECT COUNT(*) FROM fetch_log WHERE success = true')
            successful_fetches = cursor.fetchone()[0]
            
            # New markets in last 24h
            cursor.execute('''
                SELECT COUNT(*) FROM market_creations 
                WHERE first_seen >= datetime("now", "-1 day")
            ''')
            new_markets_24h = cursor.fetchone()[0]
            
            return {
                'total_active_markets': total_active,
                'last_fetch_timestamp': last_fetch,
                'successful_fetches': successful_fetches,
                'new_markets_24h': new_markets_24h
            }
            
        except Exception as e:
            self.logger.error(f"Error getting database stats: {str(e)}")
            return {}
        finally:
            conn.close()
    
    def start_background_service(self, interval_minutes: int = 5):
        """Start the background data service"""
        self.running = True
        
        def run_service():
            self.logger.info(f"Starting background data service (interval: {interval_minutes} minutes)")
            
            # Schedule regular fetches
            schedule.every(interval_minutes).minutes.do(self.fetch_and_store)
            self.logger.info(f"Scheduled fetch to run every {interval_minutes} minutes")
            
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        
        # Run in background thread
        service_thread = threading.Thread(target=run_service, daemon=True)
        service_thread.start()
        
        self.logger.info("Background data service started")
    
    def stop_background_service(self):
        """Stop the background data service"""
        self.running = False
        self.logger.info("Background data service stopped")

def main():
    """Main function to run the data service"""
    service = PolymarketDataService()
    
    print("🔄 Polymarket Data Service")
    print("Starting background data collection...")
    
    # Start background service with 5-minute intervals
    service.start_background_service(interval_minutes=5)
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(60)
            
            # Print stats every minute
            stats = service.get_database_stats()
            print(f"\n📊 Database Stats:")
            print(f"Active Markets: {stats.get('total_active_markets', 0)}")
            print(f"Last Fetch: {stats.get('last_fetch_timestamp', 'Never')}")
            print(f"Successful Fetches: {stats.get('successful_fetches', 0)}")
            print(f"New Markets (24h): {stats.get('new_markets_24h', 0)}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Stopping data service...")
        service.stop_background_service()
        print("✅ Data service stopped")

if __name__ == "__main__":
    main()
