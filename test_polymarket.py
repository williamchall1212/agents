import requests
import json
import time

base_url = "https://gamma-api.polymarket.com/markets"
params = {
    "closed": "false",      # Only open/active markets
    "active": "true",       # Extra filter for tradable
    "limit": 500,           # Max per page
    "offset": 0
}

all_open_markets = []
offset = 0

print("Fetching ALL open Polymarket markets from Gamma API (paginated)...\n")

while True:
    response = requests.get(base_url, params={**params, "offset": offset})
    if response.status_code != 200:
        print("API error:", response.status_code, response.text)
        break
    
    markets_batch = response.json()
    if not markets_batch:
        break
    
    all_open_markets.extend(markets_batch)
    print(f"Fetched {len(markets_batch)} markets (total: {len(all_open_markets)}) at offset {offset}")
    
    offset += len(markets_batch)
    if len(markets_batch) < params["limit"]:
        break  # Last page
    
    time.sleep(0.2)  # Polite rate limiting

# Sort by 24h volume descending
all_open_markets.sort(key=lambda m: float(m.get('volume_24h', m.get('volume', 0))), reverse=True)

print(f"\nDone! Total open/active markets: {len(all_open_markets)}\n")

print("Top 10 open markets by 24h volume:\n")
for m in all_open_markets[:10]:
    question = m.get('question', 'No title')[:100]
    yes_prob = m.get('yes_bid') or m.get('probability', 'N/A')
    vol_24h = m.get('volume_24h', m.get('volume', 0))
    condition_id = m.get('condition_id', 'N/A')
    print(f"{question}... | YES Prob: {yes_prob} | 24h Vol: ${vol_24h} | Condition ID: {condition_id}")

# Save full enriched open dataset
with open('all_open_polymarket_markets_gamma.json', 'w') as f:
    json.dump(all_open_markets, f, indent=2)

print(f"\nComplete open markets dataset saved to all_open_polymarket_markets_gamma.json")