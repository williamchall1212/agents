# Polymarket Insider Trading Detection System

## 🚀 **Automated Data Collection System**

I've created a comprehensive background data service that automatically fetches Polymarket data and stores it in a database for your dashboard to analyze.

## 📁 **New Files Created**

### **1. Background Data Service**
- `polymarket_data_service.py` - Core data collection engine
- `start_data_service.py` - Service launcher with CLI options
- `insider_trading_dashboard_v2.py` - Updated dashboard using database

## 🔄 **How It Works**

### **Background Service Features**
- **Automatic API polling** every 5 minutes (configurable)
- **SQLite database storage** with structured tables
- **Historical data tracking** (7-day retention)
- **Market creation monitoring** and change detection
- **Error handling and logging** with automatic retries
- **Rate limiting** to respect API limits

### **Database Schema**
```sql
-- Current market data
current_markets (condition_id, question, volume, prices, etc.)

-- Historical data for trend analysis  
market_history (condition_id, volume_24h, liquidity, timestamp)

-- Market creation tracking
market_creations (condition_id, first_seen, creator, etc.)

-- Fetch logging and statistics
fetch_log (timestamp, markets_count, success, etc.)
```

## 🚀 **Quick Start**

### **1. Start the Background Service**
```bash
# Start with default settings (5-minute updates)
python start_data_service.py

# Custom interval (e.g., every 2 minutes)
python start_data_service.py --interval 2

# Custom database location
python start_data_service.py --db-path /path/to/custom.db

# Verbose logging
python start_data_service.py --verbose
```

### **2. Run the Dashboard**
```bash
# Use the database-powered dashboard
streamlit run insider_trading_dashboard_v2.py
```

## 📊 **Dashboard Features**

### **Real-Time Database Stats**
- **Active Markets**: Current count from database
- **Last Update**: When data was last fetched
- **Total Fetches**: Successful API calls count
- **New Markets**: Markets created in last 24h

### **Database-Powered Analysis**
- **"Scan Database Markets"** button analyzes stored data
- **Manual Refresh** option for immediate updates
- **Database Statistics** viewer
- **Recent Activity** log

### **Performance Benefits**
- **Instant analysis** - no API wait times
- **Historical trends** - 7-day data for pattern detection
- **Offline capability** - works without internet
- **Consistent data** - same dataset across all modules

## 🔧 **Configuration Options**

### **Service Settings**
```bash
# Update interval (1-60 minutes)
--interval 5

# Database file path
--db-path polymarket_data.db

# Enable verbose logging
--verbose
```

### **Dashboard Integration**
The dashboard automatically:
- Connects to the database
- Shows real-time statistics
- Provides manual refresh options
- Displays fetch history

## 📈 **Data Flow**

```
Polymarket API
       ↓ (every 5 minutes)
Background Service
       ↓ (processes & stores)
SQLite Database
       ↓ (instant access)
Dashboard Analysis
```

## 🎯 **Benefits**

### **For Development**
- **Fast iteration** - no API delays during testing
- **Consistent data** - same dataset for repeated tests
- **Offline development** - work without internet

### **For Production**
- **Real-time updates** - fresh data every few minutes
- **Reliability** - continues working if API temporarily down
- **Performance** - instant analysis from local database
- **Scalability** - can handle multiple dashboard users

### **For Analysis**
- **Historical trends** - detect patterns over time
- **Market creation tracking** - monitor new markets
- **Volume history** - analyze trading patterns
- **Change detection** - spot sudden market changes

## 🚨 **Monitoring**

### **Service Logs**
- `polymarket_data_service.log` - detailed operation logs
- Console output - real-time status updates
- Error tracking with automatic retry logic

### **Database Health**
- Automatic cleanup of old data (7-day retention)
- Fetch success/failure tracking
- Market count monitoring

## 🔄 **Next Steps**

1. **Start the service**: `python start_data_service.py`
2. **Run dashboard**: `streamlit run insider_trading_dashboard_v2.py`
3. **Monitor logs**: Check `polymarket_data_service.log` for issues
4. **Adjust settings**: Use CLI options for your needs

The system now provides a robust, automated data pipeline that keeps your insider trading detection dashboard powered with fresh Polymarket data!
