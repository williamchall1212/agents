import streamlit as st
import json
import pandas as pd
from fuzzywuzzy import fuzz
import re

st.title("Polymarket Arbitrage Detector Dashboard (21,799 Open Markets - Jan 2026)")

data_file = 'all_open_polymarket_markets_gamma.json'

@st.cache_data(show_spinner="Parsing 21k markets (10-20 sec first load)...")
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
                'condition_id': m.get('conditionId', 'N/A'),
                'category': m.get('category', 'Uncategorized'),
                'clob_token_ids': json.loads(m.get('clobTokenIds', '["N/A","N/A"]')),
            })
        except:
            continue
    return pd.DataFrame(data)

df = load_markets(data_file)
st.success(f"Loaded {len(df):,} open markets!")

min_volume = st.slider("Min 24h Volume for Scan ($)", 1000, 50000000, 10000, help="Higher = faster scan")
liquid_df = df[df['volume_24h'] > min_volume]

st.write(f"Analyzing {len(liquid_df):,} liquid markets")

categories = sorted(liquid_df['category'].unique())

# Dynamic safe defaults
common_cats = liquid_df['category'].value_counts().head(5).index.tolist()  # Top 5 categories
selected_cats = st.multiselect(
    "Select Categories to Scan for Arbs",
    categories,
    default=common_cats
)

sim_threshold = st.slider("Question Similarity Threshold", 70, 100, 85)
prob_diff_threshold = st.slider("Min Prob Difference for Flag", 0.01, 0.20, 0.03)

def normalize_question(q):
    return re.sub(r'[^\w\s]', '', q.lower())

def find_arb_pairs(group_df):
    flagged = []
    items = group_df.to_dict('records')
    n = len(items)
    for i in range(n):
        for j in range(i+1, n):
            sim = fuzz.token_sort_ratio(normalize_question(items[i]['question']), normalize_question(items[j]['question']))
            if sim > sim_threshold:
                diff = abs(items[i]['yes_prob'] - items[j]['yes_prob'])
                if diff > prob_diff_threshold:
                    flagged.append({
                        'Category': items[i]['category'],
                        'Market 1': items[i]['question'][:120] + '...',
                        'Prob 1': f"{items[i]['yes_prob']:.4f}",
                        'Vol 1': f"${items[i]['volume_24h']:,.0f}",
                        'Market 2': items[j]['question'][:120] + '...',
                        'Prob 2': f"{items[j]['yes_prob']:.4f}",
                        'Vol 2': f"${items[j]['volume_24h']:,.0f}",
                        'Similarity': sim,
                        'Prob Diff': f"{diff:.4f}",
                    })
    return pd.DataFrame(flagged)

if st.button("Run Arbitrage Scan"):
    results = pd.DataFrame()
    prog = st.progress(0)
    for idx, cat in enumerate(selected_cats):
        group = liquid_df[liquid_df['category'] == cat]
        if len(group) >= 2:
            flagged = find_arb_pairs(group)
            results = pd.concat([results, flagged])
        prog.progress((idx + 1) / len(selected_cats))
    
    if results.empty:
        st.info("No arbs flagged — try lowering thresholds or checking high-duplicate categories like Entertainment/Sports.")
    else:
        st.subheader(f"Found {len(results)} Potential Arbs!")
        st.dataframe(results.sort_values('Prob Diff', ascending=False))
        st.download_button("Download CSV", results.to_csv(index=False), "polymarket_arbs.csv")

st.subheader("Top 20 Markets by Volume (Context)")
top = df.sort_values('volume_24h', ascending=False).head(20)
top_display = top[['question', 'yes_prob', 'volume_24h', 'category']].copy()
top_display['yes_prob'] = top_display['yes_prob'].apply(lambda x: f"{x:.4f}")
top_display['volume_24h'] = top_display['volume_24h'].apply(lambda x: f"${x:,.0f}")
st.dataframe(top_display, use_container_width=True)