#!/usr/bin/env python3
"""
Polymarket Data Service Launcher
Starts the background data collection service
"""

import sys
import os
import time
import signal
import argparse
from polymarket_data_service import PolymarketDataService

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n⏹️  Shutting down data service...")
    if 'service' in globals():
        service.stop_background_service()
    print("✅ Data service stopped")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Polymarket Data Service")
    parser.add_argument("--interval", type=int, default=5, help="Update interval in minutes")
    parser.add_argument("--db-path", type=str, default="polymarket_data.db", help="Database file path")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🔄 Polymarket Data Service Launcher")
    print("=" * 50)
    print(f"Update Interval: {args.interval} minutes")
    print(f"Database Path: {args.db_path}")
    print(f"Verbose Logging: {args.verbose}")
    print("=" * 50)
    
    # Initialize service
    global service
    service = PolymarketDataService(db_path=args.db_path)
    
    # Initial data fetch
    print("📥 Performing initial data fetch...")
    success = service.fetch_and_store()
    
    if not success:
        print("❌ Initial fetch failed. Check logs and try again.")
        return 1
    
    print("✅ Initial fetch completed successfully")
    
    # Start background service
    print(f"🚀 Starting background service (updates every {args.interval} minutes)...")
    service.start_background_service(interval_minutes=args.interval)
    
    try:
        # Keep main thread alive and print periodic stats
        while True:
            time.sleep(60)  # Print stats every minute
            
            stats = service.get_database_stats()
            print(f"\n📊 Status Update:")
            print(f"   Active Markets: {stats.get('total_active_markets', 0)}")
            print(f"   Last Fetch: {stats.get('last_fetch_timestamp', 'Never')[:19] if stats.get('last_fetch_timestamp') else 'Never'}")
            print(f"   Successful Fetches: {stats.get('successful_fetches', 0)}")
            print(f"   New Markets (24h): {stats.get('new_markets_24h', 0)}")
            print(f"   Next Update: In {args.interval} minutes")
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
