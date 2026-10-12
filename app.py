import json
import os
import re
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

GAMMA = "https://gamma-api.polymarket.com"
SPORT_WORDS = {
    "nfl", "nba", "wnba", "mlb", "nhl", "ufc", "mma", "soccer", "football",
    "basketball", "baseball", "hockey", "tennis", "golf", "cricket", "rugby",
    "formula 1", "f1", "nascar", "boxing", "esports", "champions league",
    "premier league", "world cup", "olympics", "ncaa", "college football",
    "college basketball", "racing", "pga", "atp", "wta", "liga", "la liga",
    "serie a", "bundesliga", "nhl", "wnba", "futures", "match winner"
}

st.set_page_config(page_title="Polymarket Sports Scout", page_icon="🏟️", layout="wide")

st.title("🏟️ Polymarket Sports Scout")
st.caption("A starter research dashboard — not financial advice and not a guarantee of profitable bets.")

with st.sidebar:
    st.header("Scanner settings")
    refresh_seconds = st.selectbox("Refresh while this page is open", [30, 60, 120, 300], index=1)
    min_liquidity = st.number_input("Minimum listed liquidity ($)", min_value=0, value=100, step=50)
    max_price = st.slider("Watch outcomes priced at or below", 0.01, 0.99, 0.40, 0.01)
    only_watchlist = st.checkbox("Show only price-alert candidates", value=False)
    st.divider()
    st.subheader("Optional Telegram alerts")
    st.caption("Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as Streamlit secrets. Alerts are checked only while this app is running/refreshing.")
    telegram_enabled = st.checkbox("Enable Telegram alerts", value=False)
    st.caption("Never put bot tokens in code or a public GitHub repository.")

st_autorefresh(interval=refresh_seconds * 1000, key="market_refresh")

def safe_json(value, fallback):
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback

def get_events():
    """Starter scan: top 500 active events by 24-hour volume; not exhaustive."""
    response = requests.get(
        f"{GAMMA}/events",
        params={
            "active": "true",
            "closed": "false",
            "limit": 500,
            "offset": 0,
            "order": "volume_24hr",
            "ascending": "false",
        },
        timeout=20,
        headers={"User-Agent": "PolymarketSportsScout/0.1"},
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        data = data.get("data", data.get("events", []))
    return data if isinstance(data, list) else []

def event_looks_sporty(event):
    tags = event.get("tags") or []
    tag_text = " ".join(
        str(tag.get("label", "")) + " " + str(tag.get("slug", "")) + " " + str(tag.get("name", ""))
        if isinstance(tag, dict) else str(tag)
        for tag in tags
    ).lower()
    title = str(event.get("title", "")) + " " + str(event.get("slug", ""))
    title = title.lower()
    if any(word in tag_text for word in ("sport", "nfl", "nba", "mlb", "nhl", "soccer", "tennis", "ufc")):
        return True
    return any(word in title for word in SPORT_WORDS)

def flatten_events(events):
    rows = []
    for event in events:
        if not isinstance(event, dict) or not event_looks_sporty(event):
            continue
        event_title = event.get("title") or event.get("slug") or "Untitled event"
        event_slug = event.get("slug", "")
        event_url = f"https://polymarket.com/event/{event_slug}" if event_slug else "https://polymarket.com"
        markets = event.get("markets") or []
        if isinstance(markets, str):
            markets = safe_json(markets, [])
        for market in markets:
            if not isinstance(market, dict):
                continue
            if market.get("closed") is True or market.get("active") is False:
                continue
            question = market.get("question") or market.get("groupItemTitle") or event_title
            outcomes = safe_json(market.get("outcomes"), [])
            prices = safe_json(market.get("outcomePrices"), [])
            if not isinstance(outcomes, list) or not isinstance(prices, list):
                continue
            slug = market.get("slug") or event_slug
            url = f"https://polymarket.com/event/{slug}" if slug else event_url
            try:
                liquidity = float(market.get("liquidityNum", market.get("liquidity", 0)) or 0)
            except (TypeError, ValueError):
                liquidity = 0.0
            try:
                volume = float(market.get("volume24hr", market.get("volumeNum", 0)) or 0)
            except (TypeError, ValueError):
                volume = 0.0
            for i, outcome in enumerate(outcomes):
                try:
                    price = float(prices[i])
                except (IndexError, TypeError, ValueError):
                    continue
                if not (0 < price < 1):
                    continue
                rows.append({
                    "Sport/event": event_title,
                    "Market": question,
                    "Outcome": str(outcome),
                    "Market price": price,
                    "Implied probability": price,
                    "Liquidity ($)": liquidity,
                    "24h volume ($)": volume,
                    "URL": url,
                })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["Market", "Outcome", "URL"])
    return df

def send_telegram(message):
    token = st.secrets.get("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
    if not token or not chat_id:
        st.warning("Telegram is enabled, but TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not configured in app secrets.")
        return False
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=15,
    )
    response.raise_for_status()
    return True

try:
    with st.spinner("Loading active Polymarket events…"):
        events = get_events()
        df = flatten_events(events)
except requests.RequestException as exc:
    st.error(f"Could not load Polymarket data: {exc}")
    st.info("Try refreshing in a minute. Public APIs can rate-limit or temporarily fail.")
    st.stop()
except Exception as exc:
    st.error(f"Unexpected data issue: {exc}")
    st.stop()

if df.empty:
    st.warning("No sports-looking markets were found in this page of results. The starter scans only the top 500 active events, so it can miss sports markets.")
    st.stop()

df["Price alert candidate"] = (df["Market price"] <= max_price) & (df["Liquidity ($)"] >= min_liquidity)
candidates = df[df["Price alert candidate"]].copy()
display_df = candidates if only_watchlist else df
display_df = display_df.sort_values(["24h volume ($)", "Liquidity ($)"], ascending=False)

m1, m2, m3 = st.columns(3)
m1.metric("Sports outcome rows found", f"{len(df):,}")
m2.metric("Price-alert candidates", f"{len(candidates):,}")
m3.metric("Markets/events scanned", f"{len(events):,}")

st.warning(
    "Important: a low price is not proof of value. This starter does not yet estimate true probabilities from independent sports statistics. "
    "It flags prices for review; it does not claim these are profitable bets."
)

st.subheader("Market scanner")
st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
view = display_df.copy()
view["Market price"] = view["Market price"].map(lambda x: f"${x:.3f}")
view["Implied probability"] = view["Implied probability"].map(lambda x: f"{x:.1%}")
view["Liquidity ($)"] = view["Liquidity ($)"].map(lambda x: f"${x:,.0f}")
view["24h volume ($)"] = view["24h volume ($)"].map(lambda x: f"${x:,.0f}")
st.dataframe(
    view[["Sport/event", "Market", "Outcome", "Market price", "Implied probability", "Liquidity ($)", "24h volume ($)", "Price alert candidate", "URL"]],
    use_container_width=True,
    hide_index=True,
    column_config={"URL": st.column_config.LinkColumn("Open market", display_text="View on Polymarket")},
)

st.download_button(
    "Download results as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="polymarket_sports_markets.csv",
    mime="text/csv",
)

st.subheader("Price alerts")
st.write(f"Currently {len(candidates)} outcome(s) meet your selected price and liquidity filters.")
if telegram_enabled and not candidates.empty:
    # Session-level cooldown prevents the same alert from repeating on every refresh
    # during this browser session. A production alert worker should use persistent storage.
    if "sent_alerts" not in st.session_state:
        st.session_state.sent_alerts = set()
    for _, row in candidates.head(10).iterrows():
        key = f"{row['URL']}|{row['Outcome']}|{row['Market price']:.4f}"
        if key not in st.session_state.sent_alerts:
            message = (
                f"Polymarket price alert (not a bet recommendation)\n"
                f"{row['Sport/event']}\n{row['Market']}\n"
                f"Outcome: {row['Outcome']}\nPrice: ${row['Market price']:.3f}\n"
                f"Liquidity: ${row['Liquidity ($)']:,.0f}\n{row['URL']}"
            )
            try:
                if send_telegram(message):
                    st.session_state.sent_alerts.add(key)
            except requests.RequestException as exc:
                st.warning(f"Telegram send failed: {exc}")

with st.expander("What this first version does and does not do"):
    st.markdown(
        """
        **Does:** reads public Polymarket event data, filters likely sports events, displays outcome prices and market activity,
        and flags outcomes matching your price/liquidity filters.

        **Does not yet:** cover every sports market, predict player statistics, calculate a trustworthy independent probability,
        understand every settlement rule, or send guaranteed background alerts when the app is asleep.

        **Next upgrade:** use Polymarket's sports metadata/series and tags for broader coverage; connect a reliable sports statistics
        source; build and backtest probability models; store alert history in a database; run a scheduled background checker for
        Telegram alerts even when the dashboard is closed.
        """
    )
