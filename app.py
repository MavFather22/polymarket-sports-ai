import json
import math
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

GAMMA = "https://gamma-api.polymarket.com"
DB_PATH = "prediction_history.db"
ESPN_SPORTS = {
    "NFL": ("football", "nfl"),
    "NBA": ("basketball", "nba"),
    "WNBA": ("basketball", "wnba"),
    "MLB": ("baseball", "mlb"),
    "NHL": ("hockey", "nhl"),
    "NCAA Football": ("football", "college-football"),
    "NCAA Basketball": ("basketball", "mens-college-basketball"),
    "MLS": ("soccer", "usa.1"),
    "English Premier League": ("soccer", "eng.1"),
    "La Liga": ("soccer", "esp.1"),
}
SPORT_WORDS = {
    "nfl", "nba", "wnba", "mlb", "nhl", "ufc", "mma", "soccer", "football",
    "basketball", "baseball", "hockey", "tennis", "golf", "cricket", "rugby",
    "formula 1", "f1", "nascar", "boxing", "esports", "champions league",
    "premier league", "world cup", "olympics", "ncaa", "college football",
    "college basketball", "racing", "pga", "atp", "wta", "liga", "la liga",
    "serie a", "bundesliga", "match winner"
}

st.set_page_config(page_title="Polymarket Sports Scout", page_icon="🏟️", layout="wide", initial_sidebar_state="expanded")

# Broadcast-style visual layer: Streamlit renders this directly in the app.
st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: radial-gradient(ellipse at 8% 0%, rgba(44,220,174,.13), transparent 32%), radial-gradient(ellipse at 95% 4%, rgba(89,105,255,.14), transparent 29%), #080c14; color:#edf4fc; }
[data-testid="stHeader"] { background:rgba(8,12,20,.86); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#111b2a,#090e17); border-right:1px solid rgba(140,166,197,.15); }
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#eaf3ff; }
.block-container { padding-top:1.25rem; padding-bottom:3rem; max-width:1680px; }
.hero-panel { position:relative; overflow:hidden; padding:clamp(1.3rem,3vw,2.35rem); margin-bottom:1.15rem; border:1px solid rgba(107,240,211,.27); border-radius:24px; background:linear-gradient(115deg,rgba(17,39,49,.98),rgba(14,22,39,.97) 60%,rgba(32,27,58,.95)); box-shadow:0 18px 60px rgba(0,0,0,.25); }
.hero-panel:after { content:""; position:absolute; width:310px; height:310px; right:-75px; top:-175px; border:1px solid rgba(98,255,218,.3); border-radius:50%; box-shadow:0 0 0 28px rgba(98,255,218,.035),0 0 0 60px rgba(98,255,218,.02); pointer-events:none; }
.hero-kicker { color:#78f5d5; text-transform:uppercase; letter-spacing:.19em; font-size:.7rem; font-weight:850; }
.hero-title { color:#f5f8ff; font-size:clamp(1.8rem,4vw,3.1rem); line-height:1.06; font-weight:900; letter-spacing:-.045em; margin:.48rem 0 .65rem; }
.hero-sub { color:#b2c0d1; font-size:.96rem; line-height:1.6; max-width:790px; }
.live-pill { display:inline-block; color:#07140f; background:#72f5c8; border-radius:999px; padding:.24rem .65rem; font-size:.68rem; font-weight:950; letter-spacing:.09em; margin-right:.45rem; }
.section-label { color:#79f5d5; font-size:.7rem; font-weight:850; letter-spacing:.16em; text-transform:uppercase; margin:.3rem 0 .35rem; }
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3 { letter-spacing:-.025em; }
.stMarkdown h2 { margin-top:.3rem; }
div[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(23,36,53,.95),rgba(12,19,30,.96)); border:1px solid rgba(139,164,192,.18); padding:1rem 1.05rem; border-radius:17px; box-shadow:0 8px 24px rgba(0,0,0,.12); }
div[data-testid="stMetricLabel"] { color:#a7b8cc; font-size:.82rem; } div[data-testid="stMetricValue"] { color:#f5f8ff; font-weight:850; }
.stTabs [data-baseweb="tab-list"] { gap:.4rem; background:rgba(14,22,35,.92); padding:.42rem; border:1px solid rgba(139,164,192,.15); border-radius:16px; }
.stTabs [data-baseweb="tab"] { border-radius:11px; padding:.68rem 1rem; color:#aebed1; font-weight:700; }
.stTabs [aria-selected="true"] { background:rgba(84,245,202,.13); color:#8ff7dc; }
.stButton > button, .stDownloadButton > button { border-radius:11px; border:1px solid rgba(117,245,213,.3); font-weight:750; transition:all .15s ease; }
.stButton > button[kind="primary"] { background:linear-gradient(110deg,#69efc7,#43d9b2); color:#06130f; border:0; }
.stTextInput input,.stSelectbox div[data-baseweb="select"],.stNumberInput input,.stTextArea textarea { border-radius:10px; background-color:#111b2a !important; color:#edf4fc !important; border-color:#34445b !important; }
.stSelectbox [data-baseweb="select"] *,.stMultiSelect [data-baseweb="select"] * { color:#edf4fc !important; }
.stMultiSelect [data-baseweb="tag"] { background:#174a42 !important; color:#dffff5 !important; border:1px solid #3d9e86 !important; }
.stRadio label,.stCheckbox label,.stSlider label,.stSelectbox label,.stTextInput label,.stMultiSelect label { color:#d5e0ed !important; }
.stTabs [data-baseweb="tab-list"] { flex-wrap:wrap; }

[data-testid="stDataFrame"] { border:1px solid rgba(139,164,192,.2); border-radius:14px; overflow:hidden; }
.matchup-card { background:linear-gradient(145deg,rgba(21,31,47,.98),rgba(11,17,28,.98)); border:1px solid rgba(128,153,183,.2); border-radius:17px; padding:1.05rem; margin:.25rem 0 .75rem; box-shadow:0 10px 26px rgba(0,0,0,.14); }
.matchup-name { color:#f4f7ff; font-weight:850; font-size:1.03rem; } .matchup-meta { color:#92a6bc; font-size:.78rem; margin-top:.35rem; }
div[data-testid="stAlert"] { border-radius:13px; }
hr { border-color:rgba(139,164,192,.16); }
footer { visibility:hidden; }
@media (max-width: 800px) { .block-container { padding-left:1rem; padding-right:1rem; } .hero-panel { border-radius:18px; } }
</style>
<div class="hero-panel"><div class="hero-kicker">Independent sports intelligence · Research only</div><div class="hero-title">POLYMARKET <span style="color:#72f5c8">SPORTS SCOUT</span></div><div class="hero-sub"><span class="live-pill">SCOUT MODE</span> Market signals, matchup estimates, game-day news and prediction tracking in one clean broadcast-style workspace.</div></div>
""", unsafe_allow_html=True)
st.caption("Personal sports research dashboard · Basic Elo estimates · No automatic betting")

def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_utc TEXT NOT NULL,
            sport TEXT NOT NULL,
            matchup TEXT NOT NULL,
            pick TEXT NOT NULL,
            model_probability REAL NOT NULL,
            opponent_probability REAL NOT NULL,
            event_date TEXT,
            event_id TEXT UNIQUE,
            result TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    return conn

def safe_json(value, fallback):
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback

@st.cache_data(ttl=120, show_spinner=False)
def get_events():
    """Scan several pages so sports markets aren't missed just because they rank below page one."""
    collected = []
    page_size = 100
    max_pages = 5  # Up to 500 active events; kept bounded to avoid excessive API calls.
    for page in range(max_pages):
        response = requests.get(
            f"{GAMMA}/events",
            params={"active": "true", "closed": "false", "limit": page_size, "offset": page * page_size},
            timeout=20,
            headers={"User-Agent": "PolymarketSportsScout/0.3"},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data = data.get("data", data.get("events", []))
        if not isinstance(data, list) or not data:
            break
        collected.extend(data)
        if len(data) < page_size:
            break
    return collected

def event_looks_sporty(event):
    tags = event.get("tags") or []
    tag_text = " ".join(
        str(tag.get("label", "")) + " " + str(tag.get("slug", "")) + " " + str(tag.get("name", ""))
        if isinstance(tag, dict) else str(tag) for tag in tags
    ).lower()
    title = (str(event.get("title", "")) + " " + str(event.get("slug", ""))).lower()
    return any(word in tag_text for word in ("sport", "nfl", "nba", "mlb", "nhl", "soccer", "tennis", "ufc")) or any(
        word in title for word in SPORT_WORDS
    )


NON_GAME_TERMS = {"ballon d'or", "ballon dor", "mvp", "rookie of the year", "player of the year", "coach of the year", "award", "awards", "draft", "hall of fame", "top scorer", "golden boot", "most valuable player", "cy young", "heisman"}

def is_game_market(row):
    text = f"{row.get('Sport/event','')} {row.get('Market','')}".casefold()
    if any(term in text for term in NON_GAME_TERMS):
        return False
    # Keep likely event-level markets; avoid generic futures and season-long awards.
    game_terms = (" vs ", " at ", "winner", "win on", "beat", "spread", "total points", "over/under", "moneyline", "match", "game", "champions league", " vs.")
    return any(term in text for term in game_terms)

def team_tokens(name):
    stop = {"the", "fc", "cf", "club", "university", "state", "of"}
    return {t for t in str(name).casefold().replace(".", " ").replace("-", " ").split() if len(t) > 2 and t not in stop}

def find_market_discrepancies(predictions, markets):
    """Conservative name-based comparison; show only likely matches and label them for review."""
    rows = []
    if markets.empty:
        return pd.DataFrame()
    for pred in predictions:
        for side_key, prob_key in (("Team A", "Team A win probability"), ("Team B", "Team B win probability")):
            team = pred[side_key]
            tokens = team_tokens(team)
            if not tokens:
                continue
            candidates = markets[markets.apply(lambda r: bool(tokens & team_tokens(str(r.get("Outcome", "")) + " " + str(r.get("Market", "")) + " " + str(r.get("Sport/event", "")))), axis=1)]
            if candidates.empty:
                continue
            for _, market in candidates.head(2).iterrows():
                price = float(market["Market price"])
                model_p = float(pred[prob_key])
                edge = model_p - price
                if abs(edge) >= 0.05:
                    rows.append({"Sport": pred["Sport"], "Matchup": pred["Matchup"], "Team": team, "Model probability": model_p, "Market probability": price, "Model minus market": edge, "Market": market["Market"], "Outcome": market["Outcome"], "Review market": market["URL"]})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["Matchup", "Team", "Market", "Outcome"]).sort_values("Model minus market", ascending=False)

def flatten_events(events):
    rows = []
    for event in events:
        if not isinstance(event, dict) or not event_looks_sporty(event):
            continue
        event_title = event.get("title") or event.get("slug") or "Untitled event"
        event_slug = event.get("slug", "")
        markets = event.get("markets") or []
        if isinstance(markets, str):
            markets = safe_json(markets, [])
        for market in markets:
            if not isinstance(market, dict) or market.get("closed") is True or market.get("active") is False:
                continue
            question = market.get("question") or market.get("groupItemTitle") or event_title
            outcomes = safe_json(market.get("outcomes"), [])
            prices = safe_json(market.get("outcomePrices"), [])
            if not isinstance(outcomes, list) or not isinstance(prices, list):
                continue
            slug = market.get("slug") or event_slug
            url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"
            try:
                liquidity = float(market.get("liquidityNum", market.get("liquidity", 0)) or 0)
                volume = float(market.get("volume24hr", market.get("volumeNum", 0)) or 0)
            except (TypeError, ValueError):
                liquidity, volume = 0.0, 0.0
            for i, outcome in enumerate(outcomes):
                try:
                    price = float(prices[i])
                except (IndexError, TypeError, ValueError):
                    continue
                if 0 < price < 1:
                    rows.append({
                        "Sport/event": event_title, "Market": question, "Outcome": str(outcome),
                        "Market price": price, "Implied probability": price,
                        "Liquidity ($)": liquidity, "24h volume ($)": volume, "URL": url,
                    })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["Market", "Outcome", "URL"])
    return df

def espn_scoreboard(sport_name, day=None):
    category, league = ESPN_SPORTS[sport_name]
    params = {}
    if day:
        params["dates"] = day.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/{category}/{league}/scoreboard"
    response = requests.get(url, params=params, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response.json()

def get_competitors(event):
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competitors = competitions[0].get("competitors") or []
    if len(competitors) != 2:
        return None
    parsed = []
    for item in competitors:
        team = item.get("team") or {}
        try:
            score = float(item.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        parsed.append({
            "name": team.get("displayName") or team.get("name") or "Unknown team",
            "abbrev": team.get("abbreviation") or team.get("displayName") or "UNK",
            "home_away": item.get("homeAway", ""),
            "score": score,
            "winner": item.get("winner", False),
        })
    return parsed

def elo_expected(rating_a, rating_b, home_advantage=0):
    return 1.0 / (1.0 + 10 ** ((rating_b - (rating_a + home_advantage)) / 400.0))


@st.cache_data(ttl=1800, show_spinner=False)
def get_espn_feed(sport_name, feed_type):
    """Fetch public ESPN league-wide injuries or news; these endpoints are undocumented and may change."""
    category, league = ESPN_SPORTS[sport_name]
    if feed_type == "injuries":
        endpoint = f"https://site.api.espn.com/apis/site/v2/sports/{category}/{league}/injuries"
    else:
        endpoint = f"https://site.api.espn.com/apis/site/v2/sports/{category}/{league}/news"
    response = requests.get(endpoint, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response.json()

def extract_news_items(payload):
    items = payload.get("articles") or payload.get("news") or []
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = item.get("headline") or item.get("title") or "Untitled report"
        description = item.get("description") or item.get("summary") or item.get("story") or ""
        published = item.get("published") or item.get("lastModified") or item.get("date") or ""
        links = item.get("links") or {}
        web_link = links.get("web") or {}
        href = web_link.get("href") if isinstance(web_link, dict) else ""
        cleaned.append({"headline": headline, "description": description, "published": published, "url": href})
    return cleaned

def extract_injury_items(payload):
    """Normalize common ESPN injury payload shapes without assuming every league matches."""
    groups = payload.get("injuries") or payload.get("items") or []
    cleaned = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        team = group.get("team") or {}
        team_name = team.get("displayName") or team.get("name") or team.get("abbreviation") or ""
        nested = group.get("injuries")
        if not isinstance(nested, list):
            nested = [group]
        for item in nested:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") or item.get("player") or {}
            name = athlete.get("displayName") or athlete.get("fullName") or athlete.get("name") or item.get("displayName") or "Player not listed"
            status = item.get("status") or item.get("type") or item.get("shortComment") or item.get("details") or "Status not provided"
            if isinstance(status, dict):
                status = status.get("description") or status.get("name") or str(status)
            comment = item.get("longComment") or item.get("comment") or item.get("description") or ""
            position = athlete.get("position") or {}
            if isinstance(position, dict):
                position = position.get("abbreviation") or position.get("name") or ""
            cleaned.append({"Team": team_name, "Player": name, "Position": position, "Status": str(status), "Details": str(comment)})
    return cleaned

def sync_saved_results(conn):
    """Check each saved pick against ESPN scoreboard data for its scheduled date ± one day."""
    history = pd.read_sql_query(
        "SELECT id, sport, pick, event_date, event_id, result FROM predictions WHERE result IS NULL OR result='Pending'",
        conn,
    )
    updated = 0
    checked = 0
    for _, row in history.iterrows():
        sport_name = row["sport"]
        if sport_name not in ESPN_SPORTS:
            continue
        raw_id = str(row["event_id"] or "")
        parts = raw_id.split(":", 2)
        if len(parts) < 3:
            continue
        espn_id = parts[1]
        try:
            scheduled = pd.to_datetime(row["event_date"], utc=True).date()
        except (TypeError, ValueError):
            continue
        found = None
        for day in (scheduled - timedelta(days=1), scheduled, scheduled + timedelta(days=1)):
            try:
                payload = espn_scoreboard(sport_name, day)
            except requests.RequestException:
                continue
            for event in payload.get("events", []):
                if str(event.get("id", "")) == espn_id:
                    found = event
                    break
            if found:
                break
        checked += 1
        if not found:
            continue
        status_type = ((found.get("status") or {}).get("type") or {})
        if not status_type.get("completed", False):
            continue
        competitors = get_competitors(found)
        if not competitors:
            continue
        pick = str(row["pick"])
        selected = next((team for team in competitors if team["name"] == pick), None)
        if selected is None:
            continue
        other = next((team for team in competitors if team["name"] != pick), None)
        if other is None or selected["score"] == other["score"]:
            result = "Void"
        else:
            result = "Win" if selected["score"] > other["score"] else "Loss"
        conn.execute("UPDATE predictions SET result=? WHERE id=?", (result, int(row["id"])))
        updated += 1
    conn.commit()
    return updated, checked

@st.cache_data(ttl=3600, show_spinner=False)
def build_elo_ratings(sport_name, days_back=30):
    """Build a simple Elo rating from completed ESPN scoreboard events in the last month."""
    ratings = {}
    games_used = 0
    today = date.today()
    # One request per day, cached for an hour. This is a starter model, not a full historical database.
    for offset in range(days_back, 0, -1):
        day = today - timedelta(days=offset)
        try:
            payload = espn_scoreboard(sport_name, day)
        except requests.RequestException:
            continue
        for event in payload.get("events", []):
            competitors = get_competitors(event)
            if not competitors:
                continue
            status = ((event.get("status") or {}).get("type") or {}).get("completed", False)
            if not status:
                continue
            a, b = competitors
            if a["name"] == "Unknown team" or b["name"] == "Unknown team":
                continue
            ra, rb = ratings.get(a["name"], 1500.0), ratings.get(b["name"], 1500.0)
            actual_a = 1.0 if a["score"] > b["score"] else 0.0 if a["score"] < b["score"] else 0.5
            expected_a = elo_expected(ra, rb, 55 if a["home_away"] == "home" else -55 if b["home_away"] == "home" else 0)
            # K=20 is a deliberately simple, conservative baseline.
            ratings[a["name"]] = ra + 20 * (actual_a - expected_a)
            ratings[b["name"]] = rb - 20 * (actual_a - expected_a)
            games_used += 1
    return ratings, games_used

@st.cache_data(ttl=900, show_spinner=False)
def get_upcoming_games(sport_name):
    payload = espn_scoreboard(sport_name)
    games = []
    for event in payload.get("events", []):
        competitors = get_competitors(event)
        if not competitors:
            continue
        status_type = ((event.get("status") or {}).get("type") or {})
        if status_type.get("completed", False):
            continue
        a, b = competitors
        competition = (event.get("competitions") or [{}])[0]
        games.append({
            "id": str(event.get("id", "")),
            "name": event.get("name", f"{a['name']} vs {b['name']}"),
            "date": event.get("date", ""),
            "a": a, "b": b,
            "status": status_type.get("detail", status_type.get("description", "Scheduled")),
            "venue": (competition.get("venue") or {}).get("fullName", ""),
        })
    return games

def send_telegram(message):
    token = st.secrets.get("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
    if not token or not chat_id:
        st.warning("Telegram is enabled, but its secrets are not configured.")
        return False
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=15,
    )
    response.raise_for_status()
    return True

with st.sidebar:
    st.header("Scanner settings")
    refresh_seconds = st.selectbox("Refresh while this page is open", [60, 120, 300], index=1)
    min_liquidity = st.number_input("Minimum listed liquidity ($)", min_value=0, value=100, step=50)
    max_price = st.slider("Watch outcomes priced at or below", 0.01, 0.99, 0.40, 0.01)
    only_watchlist = st.checkbox("Show only price-alert candidates", value=False)
    market_scope = st.radio("Market type", ["Game markets only", "All sports-related markets"], index=0, help="Game markets filters out awards and season-long futures.")
    st.divider()
    st.subheader("Prediction engine")
    selected_sports = st.multiselect("Sports to model", list(ESPN_SPORTS.keys()), default=["NFL", "NBA", "MLB", "NHL"])
    days_back = st.select_slider("Recent results used for ratings", options=[7, 14, 21, 30], value=14)
    st.caption("Uses public ESPN scoreboard data and a basic Elo model. Coverage depends on ESPN schedules.")
    telegram_enabled = st.checkbox("Enable Telegram alerts", value=False, help="Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Streamlit secrets.")
    alert_price_moves = st.checkbox("Alert on meaningful market price moves", value=True)
    price_move_threshold = st.slider("Price-move alert threshold", 0.01, 0.20, 0.03, 0.01, format="%.2f")
    alert_feed_changes = st.checkbox("Show alerts for new news/injury feed updates", value=True)
    if st.button("↻ Refresh all data now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st_autorefresh(interval=refresh_seconds * 1000, key="market_refresh")
page_refresh_utc = datetime.now(timezone.utc)
st.caption(f"Page refreshed: {page_refresh_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} · Auto-refresh every {refresh_seconds}s while this page is open · cached sources may update less frequently.")
conn = db_connect()
st.session_state.best_bet_rows = []
if "market_price_snapshot" not in st.session_state:
    st.session_state.market_price_snapshot = {}
if "scout_alerts" not in st.session_state:
    st.session_state.scout_alerts = []
if "feed_fingerprints" not in st.session_state:
    st.session_state.feed_fingerprints = {}

tab_market, tab_game, tab_model, tab_best, tab_moonshot, tab_betbuilder, tab_news, tab_history = st.tabs(["📊 Market scanner", "🏟️ Game center", "🧠 Sports predictions", "⭐ Best bet candidates", "🌙 Moonshots", "🎯 Bet builder", "🩹 News & injuries", "🗂️ Prediction tracking"])

with tab_market:
    try:
        with st.spinner("Loading Polymarket markets…"):
            events = get_events()
            df = flatten_events(events)
            if not df.empty and market_scope == "Game markets only":
                df = df[df.apply(is_game_market, axis=1)].copy()
    except requests.RequestException as exc:
        st.error(f"Could not load Polymarket data: {exc}")
        df = pd.DataFrame()
        events = []
    if df.empty:
        st.warning("No sports-looking markets were found in this page of results, or the API is temporarily unavailable.")
    else:
        df["Price alert candidate"] = (df["Market price"] <= max_price) & (df["Liquidity ($)"] >= min_liquidity)
        candidates = df[df["Price alert candidate"]].copy()

        # Compare the latest market snapshot with the prior app run. First run only establishes a baseline.
        current_snapshot = {}
        price_moves = []
        for _, market_row in df.iterrows():
            market_key = f"{market_row.get('URL', '')}|{market_row.get('Outcome', '')}"
            current_price = float(market_row.get("Market price", 0) or 0)
            current_snapshot[market_key] = {
                "price": current_price,
                "sport_event": str(market_row.get("Sport/event", "")),
                "market": str(market_row.get("Market", "")),
                "outcome": str(market_row.get("Outcome", "")),
                "url": str(market_row.get("URL", "")),
            }
            previous = st.session_state.market_price_snapshot.get(market_key)
            if previous and alert_price_moves:
                delta = current_price - float(previous.get("price", current_price))
                if abs(delta) >= float(price_move_threshold):
                    price_moves.append({**current_snapshot[market_key], "previous_price": float(previous["price"]), "delta": delta})
        st.session_state.market_price_snapshot = current_snapshot
        if price_moves:
            for move in price_moves[:15]:
                alert_text = f"Market move: {move['sport_event']} · {move['outcome']} changed from ${move['previous_price']:.3f} to ${move['price']:.3f} ({move['delta']:+.3f}). Verify the market before acting."
                st.session_state.scout_alerts.insert(0, {"time": datetime.now(timezone.utc).isoformat(), "type": "Market move", "message": alert_text, "url": move["url"]})
                if telegram_enabled:
                    try:
                        send_telegram(alert_text + (f"\n{move['url']}" if move["url"] else ""))
                    except requests.RequestException as exc:
                        st.warning(f"Telegram market-move alert failed: {exc}")
            st.session_state.scout_alerts = st.session_state.scout_alerts[:50]

        search_col, sort_col = st.columns([3, 1])
        market_search = search_col.text_input("Find a team, event, or market", placeholder="Search for a team or matchup…", key="market_search")
        sort_choice = sort_col.selectbox("Sort markets by", ["24h volume", "Liquidity", "Lowest price"], key="market_sort")
        display_df = candidates.copy() if only_watchlist else df.copy()
        if market_search.strip():
            needle = market_search.strip().casefold()
            display_df = display_df[display_df[["Sport/event", "Market", "Outcome"]].fillna("").astype(str).apply(lambda col: col.str.casefold().str.contains(needle, regex=False)).any(axis=1)]
        sort_map = {"24h volume": "24h volume ($)", "Liquidity": "Liquidity ($)", "Lowest price": "Market price"}
        display_df = display_df.sort_values(sort_map[sort_choice], ascending=(sort_choice == "Lowest price"))
        m1, m2, m3 = st.columns(3)
        m1.metric("Sports outcome rows found", f"{len(df):,}")
        m2.metric("Price-alert candidates", f"{len(candidates):,}")
        m3.metric("Events scanned", f"{len(events):,}")
        st.info("A low price is not proof of value. Potential model/market differences are shown only when a likely team-name match is found; always verify the contract manually.")
        view = display_df.copy()
        view["Market price"] = view["Market price"].map(lambda x: f"${x:.3f}")
        view["Implied probability"] = view["Implied probability"].map(lambda x: f"{x:.1%}")
        view["Liquidity ($)"] = view["Liquidity ($)"].map(lambda x: f"${x:,.0f}")
        view["24h volume ($)"] = view["24h volume ($)"].map(lambda x: f"${x:,.0f}")
        st.caption(f"Showing {len(view):,} markets · Prices and liquidity are snapshots from the Polymarket API.")
        st.dataframe(view[["Sport/event", "Market", "Outcome", "Market price", "Implied probability", "Liquidity ($)", "24h volume ($)", "Price alert candidate", "URL"]],
                     use_container_width=True, hide_index=True, height=480,
                     column_config={"URL": st.column_config.LinkColumn("Open market", display_text="Open ↗"),
                                    "Price alert candidate": st.column_config.CheckboxColumn("Price alert", disabled=True)})
        st.download_button("Download market scan CSV", data=df.to_csv(index=False).encode("utf-8"),
                           file_name="polymarket_sports_markets.csv", mime="text/csv")
        if telegram_enabled and not candidates.empty:
            if "sent_alerts" not in st.session_state:
                st.session_state.sent_alerts = set()
            for _, row in candidates.head(10).iterrows():
                key = f"{row['URL']}|{row['Outcome']}|{row['Market price']:.4f}"
                if key not in st.session_state.sent_alerts:
                    msg = f"Polymarket price alert (research only)\n{row['Sport/event']}\n{row['Market']}\nOutcome: {row['Outcome']}\nPrice: ${row['Market price']:.3f}\n{row['URL']}"
                    try:
                        if send_telegram(msg):
                            st.session_state.sent_alerts.add(key)
                    except requests.RequestException as exc:
                        st.warning(f"Telegram send failed: {exc}")

        if alert_price_moves:
            if price_moves:
                st.warning(f"Detected {len(price_moves)} meaningful price move(s) since the previous app refresh. See the alerts panel below.")
            else:
                st.caption(f"Price-move monitoring is on (threshold ±{price_move_threshold:.0%}). First refresh establishes a baseline; changes are detected only while the app is open.")

with tab_game:
    st.markdown('<div class="section-label">Game-day command center</div>', unsafe_allow_html=True)
    st.subheader("Scores, schedules and matchup pulse")
    st.caption("Scoreboard information comes from ESPN's public endpoints. Coverage and update timing can vary by league.")
    if not selected_sports:
        st.info("Choose at least one sport in the sidebar to load its scoreboard.")
    else:
        game_sport = st.selectbox("League", selected_sports, key="game_center_sport")
        try:
            payload = espn_scoreboard(game_sport)
            scoreboard_events = payload.get("events", [])
            status_filter = st.radio("Show games", ["All", "Live", "Upcoming", "Final"], horizontal=True, key="game_status_filter")
            if not scoreboard_events:
                st.info(f"ESPN returned no current or upcoming {game_sport} games. Try another league or check back later.")
            else:
                score_rows = []
                for event in scoreboard_events:
                    teams = get_competitors(event)
                    if not teams:
                        continue
                    status_type = ((event.get("status") or {}).get("type") or {})
                    competition = (event.get("competitions") or [{}])[0]
                    start_raw = event.get("date", "")
                    try:
                        start_label = pd.to_datetime(start_raw, utc=True).strftime("%a %b %d · %I:%M %p UTC")
                    except Exception:
                        start_label = start_raw or "Start time unavailable"
                    completed = bool(status_type.get("completed", False))
                    state = "FINAL" if completed else status_type.get("detail") or status_type.get("description") or "UPCOMING"
                    live_now = bool(status_type.get("state") == "in")
                    score_rows.append((event, teams, state, start_label, live_now, completed, competition))
                live_rows = [x for x in score_rows if x[4]]
                upcoming_rows = [x for x in score_rows if not x[4] and not x[5]]
                final_rows = [x for x in score_rows if x[5]]
                a, b, c = st.columns(3)
                a.metric("Live now", len(live_rows))
                b.metric("Upcoming / in progress", len(upcoming_rows))
                c.metric("Final scores listed", len(final_rows))
                # Quick availability/news pulse; feed failures never block the scoreboard.
                pulse_a, pulse_b = st.columns(2)
                try:
                    pulse_news = extract_news_items(get_espn_feed(game_sport, "news"))
                    pulse_a.metric("Recent headlines", len(pulse_news))
                    if pulse_news:
                        with st.expander("📰 Latest news pulse", expanded=False):
                            for headline in pulse_news[:3]:
                                st.markdown(f"**{headline['headline']}**")
                                if headline.get("url"):
                                    st.markdown(f"[Read report]({headline['url']})")
                except requests.RequestException:
                    pulse_a.metric("Recent headlines", "Unavailable")
                try:
                    pulse_injuries = extract_injury_items(get_espn_feed(game_sport, "injuries"))
                    pulse_b.metric("Injury entries returned", len(pulse_injuries))
                    if pulse_injuries:
                        with st.expander("🩹 Availability watch", expanded=False):
                            st.dataframe(pd.DataFrame(pulse_injuries).head(10), use_container_width=True, hide_index=True)
                except requests.RequestException:
                    pulse_b.metric("Injury entries returned", "Unavailable")
                ordered = live_rows + upcoming_rows + final_rows
                if status_filter == "Live": ordered = live_rows
                elif status_filter == "Upcoming": ordered = upcoming_rows
                elif status_filter == "Final": ordered = final_rows
                st.caption("Times are shown in UTC. ESPN public feeds can occasionally omit or delay events.")
                for event, teams, state, start_label, live_now, completed, competition in ordered[:24]:
                    left, right = teams[0], teams[1]
                    venue = (competition.get("venue") or {}).get("fullName", "")
                    state_color = "#72f5c8" if live_now else "#9fb0c4"
                    score_display = f"{int(left['score'])}  —  {int(right['score'])}" if completed or live_now else "VS"
                    st.markdown(f'''<div class="matchup-card"><div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><div class="matchup-name">{left['name']} <span style="color:#71849b">vs</span> {right['name']}</div><div style="color:{state_color};font-weight:900;font-size:.72rem;letter-spacing:.12em">{'🔴 ' if live_now else ''}{state.upper()}</div></div><div style="font-size:1.65rem;font-weight:850;letter-spacing:.05em;color:#f4f7ff;margin:.35rem 0">{score_display}</div><div class="matchup-meta">{start_label}{' · ' + venue if venue else ''}</div></div>''', unsafe_allow_html=True)
        except requests.RequestException as exc:
            st.warning(f"Could not load the ESPN scoreboard for {game_sport}: {exc}")

with tab_model:
    st.subheader("Elo-based matchup estimates")
    st.caption("Elo estimates relative team strength from recent completed games. It is a baseline—not a fully validated betting model, and a short history can be misleading.")
    if not selected_sports:
        st.info("Choose at least one sport in the sidebar.")
    else:
        for sport_name in selected_sports:
            with st.expander(sport_name, expanded=(sport_name == selected_sports[0])):
                try:
                    with st.spinner(f"Building {sport_name} ratings from recent scores…"):
                        ratings, games_used = build_elo_ratings(sport_name, days_back)
                        games = get_upcoming_games(sport_name)
                    st.caption(f"Completed games used in recent window: {games_used}. Teams rated: {len(ratings)}.")
                    if not games:
                        st.info("No upcoming or in-progress matchups were returned by the scoreboard right now.")
                        continue
                    rows = []
                    for game in games:
                        a, b = game["a"], game["b"]
                        ra, rb = ratings.get(a["name"], 1500.0), ratings.get(b["name"], 1500.0)
                        home = 55 if a["home_away"] == "home" else -55 if b["home_away"] == "home" else 0
                        pa = elo_expected(ra, rb, home)
                        rows.append({
                            "Event ID": game["id"], "Sport": sport_name, "Matchup": game["name"],
                            "Team A": a["name"], "Team B": b["name"],
                            "Team A Elo": round(ra), "Team B Elo": round(rb),
                            "Team A win probability": pa, "Team B win probability": 1 - pa,
                            "Start": game["date"], "Status": game["status"],
                        })
                    pred_df = pd.DataFrame(rows)
                    st.markdown("#### Matchup board")
                    for prediction in rows[:12]:
                        pa = float(prediction["Team A win probability"])
                        pb = float(prediction["Team B win probability"])
                        try:
                            start_text = pd.to_datetime(prediction["Start"], utc=True).strftime("%a %b %d · %I:%M %p UTC")
                        except Exception:
                            start_text = str(prediction["Start"] or "Start time unavailable")
                        st.markdown(f"**{prediction['Team A']}**  ·  Elo {prediction['Team A Elo']}  ·  **{pa:.1%}**")
                        st.progress(min(1.0, max(0.0, pa)))
                        st.markdown(f"**{prediction['Team B']}**  ·  Elo {prediction['Team B Elo']}  ·  **{pb:.1%}**")
                        st.progress(min(1.0, max(0.0, pb)))
                        st.caption(f"{prediction['Matchup']} · {start_text} · {prediction['Status']}")
                        st.divider()
                    # Candidate market differences are suggestions only; contract identity is not guaranteed.
                    likely_edges = find_market_discrepancies(rows, df if 'df' in globals() else pd.DataFrame())
                    if not likely_edges.empty:
                        cached = likely_edges.copy()
                        cached["Sport"] = sport_name
                        st.session_state.best_bet_rows.extend(cached.to_dict("records"))
                    if not likely_edges.empty:
                        st.markdown("#### Possible model / market differences")
                        st.warning("These are heuristic name matches, not verified contract matches. Open each market and confirm the exact event and outcome before drawing conclusions.")
                        edge_view = likely_edges.copy()
                        for col in ("Model probability", "Market probability", "Model minus market"):
                            edge_view[col] = edge_view[col].map(lambda x: f"{x:+.1%}" if col == "Model minus market" else f"{x:.1%}")
                        st.dataframe(edge_view, use_container_width=True, hide_index=True, column_config={"Review market": st.column_config.LinkColumn("Verify contract", display_text="Open ↗")})
                    save_choice = st.selectbox(f"Choose a matchup to record ({sport_name})",
                                               options=list(range(len(rows))),
                                               format_func=lambda i: rows[i]["Matchup"],
                                               key=f"save_choice_{sport_name}")
                    chosen = rows[save_choice]
                    pick_side = st.radio(f"Record which side? ({sport_name})",
                                         [chosen["Team A"], chosen["Team B"]],
                                         horizontal=True, key=f"pick_side_{sport_name}")
                    note = st.text_input(f"Optional note ({sport_name})", key=f"note_{sport_name}")
                    if st.button(f"Save prediction ({sport_name})", key=f"save_{sport_name}"):
                        pick_prob = chosen["Team A win probability"] if pick_side == chosen["Team A"] else chosen["Team B win probability"]
                        opp_prob = 1 - pick_prob
                        event_date = chosen["Start"]
                        event_id = f"{sport_name}:{chosen['Event ID']}:{pick_side}"
                        try:
                            conn.execute(
                                "INSERT INTO predictions (created_utc,sport,matchup,pick,model_probability,opponent_probability,event_date,event_id,result,notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (datetime.now(timezone.utc).isoformat(), sport_name, chosen["Matchup"], pick_side,
                                 float(pick_prob), float(opp_prob), event_date, event_id, None, note)
                            )
                            conn.commit()
                            st.success("Prediction saved to this app's local database.")
                        except sqlite3.IntegrityError:
                            st.warning("That same team/matchup prediction is already recorded.")
                except requests.RequestException as exc:
                    st.warning(f"Could not load ESPN data for {sport_name}: {exc}")
                except Exception as exc:
                    st.warning(f"Couldn't build {sport_name} predictions: {exc}")


with tab_best:
    st.markdown('<div class="section-label">Model-versus-market shortlist</div>', unsafe_allow_html=True)
    st.subheader("Best bet candidates")
    st.caption("Ranks possible price disagreements for research. Not a guarantee or betting advice. Team/contract matches are heuristic and must be verified manually.")
    candidates = pd.DataFrame(st.session_state.get("best_bet_rows", []))
    if candidates.empty:
        st.info("No likely model/market matches with at least a 5 percentage-point difference were found in the current scan. Open Sports predictions and wait for selected leagues to load, then revisit this tab.")
    else:
        candidates["Model minus market"] = pd.to_numeric(candidates["Model minus market"], errors="coerce")
        candidates["Model probability"] = pd.to_numeric(candidates["Model probability"], errors="coerce")
        candidates["Market probability"] = pd.to_numeric(candidates["Market probability"], errors="coerce")
        candidates = candidates[(candidates["Model minus market"] >= 0.05) & candidates["Market probability"].between(0.03, 0.97)].copy()
        candidates = candidates.sort_values("Model minus market", ascending=False).drop_duplicates(subset=["Matchup", "Team", "Market", "Outcome"])
        if candidates.empty:
            st.info("No positive model edges passed the shortlist filters. Don't force a pick.")
        else:
            top = candidates.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Positive-edge candidates", f"{len(candidates):,}")
            c2.metric("Largest estimated edge", f"{top['Model minus market']:.1%}")
            c3.metric("Top model probability", f"{top['Model probability']:.1%}")
            st.markdown(f"**Top candidate: {top['Team']} — {top['Matchup']}**")
            st.markdown(f"Market outcome: **{top['Outcome']}** · Market price: **{top['Market probability']:.1%}** · Elo estimate: **{top['Model probability']:.1%}** · Estimated difference: **+{top['Model minus market']:.1%}**")
            st.warning("This shortlist can contain false matches because it uses team-name text similarity. Confirm the exact event, outcome, and contract rules. Elo does not yet incorporate injuries, news, odds movement, or a validated backtest.")
            show = candidates.copy()
            for col in ("Model probability", "Market probability"):
                show[col] = show[col].map(lambda x: f"{x:.1%}")
            show["Model minus market"] = show["Model minus market"].map(lambda x: f"{x:+.1%}")
            st.dataframe(show[["Sport", "Matchup", "Team", "Model probability", "Market probability", "Model minus market", "Market", "Outcome", "Review market"]], use_container_width=True, hide_index=True, column_config={"Review market": st.column_config.LinkColumn("Verify market", display_text="Open ↗")})

with tab_moonshot:
    st.markdown('<div class="section-label">Long-shot research lab</div>', unsafe_allow_html=True)
    st.subheader("🌙 Moonshot candidates")
    st.caption("Looks for low-priced sports outcomes with large potential payouts. Low odds imply low chances; this tab ranks research candidates, not guaranteed wins. Model probabilities only appear when a likely matchup/outcome match exists, and those matches require manual verification.")

    controls = st.columns(4)
    with controls[0]:
        moon_min = st.slider("Minimum market price", 0.01, 0.20, 0.02, 0.01, key="moon_min")
    with controls[1]:
        moon_max = st.slider("Maximum market price", 0.03, 0.35, 0.15, 0.01, key="moon_max")
    with controls[2]:
        moon_liquidity = st.number_input("Minimum liquidity ($)", min_value=0, value=100, step=50, key="moon_liquidity")
    with controls[3]:
        moon_stake = st.number_input("Hypothetical stake ($)", min_value=1.0, max_value=100.0, value=10.0, step=1.0, key="moon_stake")

    if 'df' not in locals() or not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No market data is available in this refresh. Check Market scanner and try again.")
    elif moon_min > moon_max:
        st.warning("Minimum price must be less than or equal to maximum price.")
    else:
        moon = df.copy()
        moon["Market price"] = pd.to_numeric(moon["Market price"], errors="coerce")
        moon["Liquidity ($)"] = pd.to_numeric(moon["Liquidity ($)"], errors="coerce").fillna(0)
        moon = moon[(moon["Market price"] >= moon_min) & (moon["Market price"] <= moon_max) & (moon["Liquidity ($)"] >= moon_liquidity)].copy()
        if market_scope == "Game markets only":
            moon = moon[moon.apply(is_game_market, axis=1)]

        # Only attach a model estimate where the existing heuristic matcher produced a plausible candidate.
        model_rows = pd.DataFrame(st.session_state.get("best_bet_rows", []))
        moon["Model probability"] = float("nan")
        moon["Model edge"] = float("nan")
        moon["Match confidence"] = "Market-only; no model match"
        if not model_rows.empty and {"Market", "Outcome", "Model probability", "Market probability"}.issubset(model_rows.columns):
            for idx, market_row in moon.iterrows():
                same = model_rows[(model_rows["Market"].astype(str) == str(market_row["Market"])) & (model_rows["Outcome"].astype(str) == str(market_row["Outcome"]))]
                if not same.empty:
                    candidate = same.iloc[0]
                    moon.at[idx, "Model probability"] = float(candidate["Model probability"])
                    moon.at[idx, "Model edge"] = float(candidate["Model probability"]) - float(market_row["Market price"])
                    moon.at[idx, "Match confidence"] = "Heuristic match — verify"

        moon["Potential total return ($)"] = moon_stake / moon["Market price"]
        moon["Potential profit ($)"] = moon["Potential total return ($)"] - moon_stake
        moon["Implied chance"] = moon["Market price"]
        moon["Model edge"] = pd.to_numeric(moon["Model edge"], errors="coerce")
        moon["Model probability"] = pd.to_numeric(moon["Model probability"], errors="coerce")
        moon["Ranking signal"] = moon.apply(lambda r: "Model edge" if pd.notna(r["Model edge"]) and r["Model edge"] > 0 else "Liquidity + price only", axis=1)
        # Prefer verified-by-user model edges when available; otherwise show liquid markets, never label them as model-backed.
        moon = moon.sort_values(["Model edge", "Liquidity ($)"], ascending=[False, False], na_position="last")
        moon = moon.drop_duplicates(subset=["Market", "Outcome", "URL"]).head(40)

        if moon.empty:
            st.info("No markets fit these price and liquidity filters. Try a wider price range or lower liquidity minimum.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Long-shot outcomes found", f"{len(moon):,}")
            k2.metric("Largest possible profit", f"${moon['Potential profit ($)'].max():,.2f}")
            k3.metric("Model-matched candidates", f"{moon['Model probability'].notna().sum():,}")
            st.warning("Potential payout is not the same as expected profit. A $10 position at a $0.05 price could return about $200 if it wins, but the market-implied chance is only 5%, and the entire stake can be lost. Don't treat market-only rows as model recommendations.")
            view = moon[["Sport/event", "Market", "Outcome", "Market price", "Implied chance", "Model probability", "Model edge", "Liquidity ($)", "Potential total return ($)", "Potential profit ($)", "Ranking signal", "Match confidence", "URL"]].copy()
            for col in ("Market price", "Implied chance", "Model probability", "Model edge"):
                view[col] = view[col].map(lambda x: "—" if pd.isna(x) else (f"{x:+.1%}" if col == "Model edge" else f"{x:.1%}"))
            for col in ("Liquidity ($)", "Potential total return ($)", "Potential profit ($)"):
                view[col] = view[col].map(lambda x: f"${x:,.2f}")
            st.dataframe(view, use_container_width=True, hide_index=True, height=520, column_config={"URL": st.column_config.LinkColumn("Open market", display_text="Open ↗")})
            st.caption("Moonshot ranking is exploratory. Historical hit rates are not yet calculated from a sufficiently large, settled dataset; model matches are heuristic, and current Elo estimates do not account for injuries or all relevant context.")
            st.download_button("Download moonshot shortlist CSV", data=moon.to_csv(index=False).encode("utf-8"), file_name="moonshot_candidates.csv", mime="text/csv")


with tab_betbuilder:
    st.markdown('<div class="section-label">Stake & payout workspace</div>', unsafe_allow_html=True)
    st.subheader("🎯 Bet builder — highest-probability picks + moonshots")
    st.caption("Uses current Polymarket outcome prices and any available Elo estimates. Payouts are estimates before fees/slippage. Model matches are heuristic; verify the exact event and contract. No bet is placed by this app.")

    amount_col, max_col, filter_col = st.columns([1.2, 1, 1.2])
    with amount_col:
        stake_amount = st.number_input("Hypothetical stake ($)", min_value=1.0, max_value=100.0, value=10.0, step=1.0, key="betbuilder_stake")
    with max_col:
        st.metric("Maximum allowed stake", "$100")
    with filter_col:
        min_ev_edge = st.slider("Minimum estimated edge", 0.00, 0.20, 0.03, 0.01, format="%.0f%%", key="betbuilder_edge")

    best_data = pd.DataFrame(st.session_state.get("best_bet_rows", []))
    if not best_data.empty:
        for col in ("Model probability", "Market probability", "Model minus market"):
            if col in best_data:
                best_data[col] = pd.to_numeric(best_data[col], errors="coerce")
        best_data = best_data.dropna(subset=["Model probability", "Market probability"])
        best_data = best_data[(best_data["Market probability"] > 0) & (best_data["Market probability"] < 1)].copy()
        best_data["Estimated edge"] = best_data["Model probability"] - best_data["Market probability"]
        best_data["Break-even probability"] = best_data["Market probability"]
        best_data["Potential return ($)"] = stake_amount / best_data["Market probability"]
        best_data["Potential profit ($)"] = best_data["Potential return ($)"] - stake_amount
        best_data["Estimated EV ($)"] = best_data["Model probability"] * best_data["Potential profit ($)"] - (1 - best_data["Model probability"]) * stake_amount
        best_data = best_data[best_data["Estimated edge"] >= min_ev_edge].copy()
        best_data = best_data.sort_values(["Model probability", "Estimated EV ($)"], ascending=False)

    st.markdown("### Highest-probability model candidates")
    if best_data.empty:
        st.info("No model-matched candidates currently pass your edge filter. This is a valid result—don't force a pick. Return to Sports predictions and let the selected leagues load, then refresh.")
    else:
        st.caption("Ranked first by estimated win probability, then expected value. These are unvalidated Elo estimates and can be wrong.")
        for _, pick in best_data.head(8).iterrows():
            prob = float(pick["Model probability"])
            market_p = float(pick["Market probability"])
            edge = float(pick["Estimated edge"])
            ev = float(pick["Estimated EV ($)"])
            with st.container(border=True):
                title = f"{pick.get('Team', 'Outcome')} · {pick.get('Matchup', pick.get('Market', 'Market'))}"
                st.markdown(f"**{title}**")
                st.caption(f"{pick.get('Sport', 'Sport')} · {pick.get('Market', '')} · {pick.get('Outcome', '')}")
                x1, x2, x3, x4 = st.columns(4)
                x1.metric("Model win estimate", f"{prob:.1%}")
                x2.metric("Market implied", f"{market_p:.1%}")
                x3.metric("Estimated edge", f"{edge:+.1%}")
                x4.metric("Est. EV at stake", f"${ev:+.2f}")
                st.progress(min(1.0, max(0.0, prob)))
                st.markdown(f"At **${stake_amount:.2f}** stake: potential total return **${float(pick['Potential return ($)']):.2f}**, potential profit **${float(pick['Potential profit ($)']):.2f}** if it wins.")
                url = pick.get("Review market", "")
                if isinstance(url, str) and url.startswith("http"):
                    st.markdown(f"[Open and verify contract ↗]({url})")

    st.markdown("### Moonshots with the biggest payouts")
    st.caption("Long shots are listed separately so large payouts aren't confused with high hit probability.")
    moon_min_price = st.slider("Moonshot price floor", 0.01, 0.20, 0.02, 0.01, key="builder_moon_min")
    moon_max_price = st.slider("Moonshot price ceiling", 0.03, 0.35, 0.15, 0.01, key="builder_moon_max")
    if 'df' not in locals() or not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Market data is unavailable in this run. Open Market scanner and refresh.")
    elif moon_min_price > moon_max_price:
        st.warning("Moonshot price floor must be less than or equal to its ceiling.")
    else:
        moon_builder = df.copy()
        moon_builder["Market price"] = pd.to_numeric(moon_builder["Market price"], errors="coerce")
        moon_builder["Liquidity ($)"] = pd.to_numeric(moon_builder["Liquidity ($)"], errors="coerce").fillna(0)
        moon_builder = moon_builder[moon_builder["Market price"].between(moon_min_price, moon_max_price)].copy()
        if market_scope == "Game markets only":
            moon_builder = moon_builder[moon_builder.apply(is_game_market, axis=1)]
        moon_builder["Market implied chance"] = moon_builder["Market price"]
        moon_builder["Potential return ($)"] = stake_amount / moon_builder["Market price"]
        moon_builder["Potential profit ($)"] = moon_builder["Potential return ($)"] - stake_amount
        moon_builder["Break-even hit rate"] = moon_builder["Market price"]
        moon_builder = moon_builder.sort_values(["Potential profit ($)", "Liquidity ($)"], ascending=[False, False]).drop_duplicates(subset=["Market", "Outcome", "URL"]).head(20)
        if moon_builder.empty:
            st.info("No current market outcomes fit this price range. Try widening the range.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Moonshots found", f"{len(moon_builder)}")
            m2.metric("Largest potential profit", f"${moon_builder['Potential profit ($)'].max():,.2f}")
            m3.metric("Stake at risk", f"${stake_amount:.2f}")
            st.dataframe(
                moon_builder[["Sport/event", "Market", "Outcome", "Market price", "Market implied chance", "Break-even hit rate", "Potential return ($)", "Potential profit ($)", "Liquidity ($)", "URL"]],
                use_container_width=True, hide_index=True, height=420,
                column_config={"URL": st.column_config.LinkColumn("Verify market", display_text="Open ↗")}
            )
            st.download_button("Download bet builder shortlist CSV", data=moon_builder.to_csv(index=False).encode("utf-8"), file_name="bet_builder_shortlist.csv", mime="text/csv", key="download_betbuilder")
            st.warning("Market-only moonshots are ranked by payout, not by validated likelihood. A market price is only the market-implied probability proxy; fees, spreads, liquidity and settlement rules can change realized returns. Never treat the displayed expected value as reliable until the model has been calibrated against a large out-of-sample history.")

with tab_news:
    st.markdown('<div class="section-label">Availability & reporting</div>', unsafe_allow_html=True)
    st.subheader("Injury reports and recent sports news")
    st.caption("Context only: public ESPN feeds are undocumented and can change. Injury/news items are not automatically weighted into Elo probabilities.")
    if not selected_sports:
        st.info("Choose sports in the sidebar to see available feeds.")
    else:
        news_sport = st.selectbox("Sport feed", selected_sports, key="news_sport")
        col_news, col_inj = st.columns(2)
        with col_news:
            st.markdown("#### 📰 Latest headlines")
            try:
                news_payload = get_espn_feed(news_sport, "news")
                news_items = extract_news_items(news_payload)
                news_signature = json.dumps([(item.get("headline", ""), item.get("published", ""), item.get("url", "")) for item in news_items[:20]], sort_keys=True)
                news_key = f"{news_sport}:news"
                previous_signature = st.session_state.feed_fingerprints.get(news_key)
                if previous_signature is not None and previous_signature != news_signature and alert_feed_changes:
                    message = f"News feed updated for {news_sport}: new or changed headlines were detected."
                    st.session_state.scout_alerts.insert(0, {"time": datetime.now(timezone.utc).isoformat(), "type": "News update", "message": message, "url": ""})
                    if telegram_enabled:
                        try:
                            send_telegram(message)
                        except requests.RequestException as exc:
                            st.warning(f"Telegram news alert failed: {exc}")
                st.session_state.feed_fingerprints[news_key] = news_signature
                st.caption(f"Feed checked by app: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} · cached for up to 30 minutes")
                if not news_items:
                    st.info("No headlines were returned in the expected format for this league.")
                for item in news_items[:12]:
                    st.markdown(f"**{item['headline']}**")
                    if item["description"]:
                        st.write(item["description"][:450])
                    if item["published"]:
                        st.caption(str(item["published"]))
                    if item["url"]:
                        st.markdown(f"[Read report]({item['url']})")
                    st.divider()
            except requests.RequestException as exc:
                st.warning(f"News feed unavailable right now: {exc}")
        with col_inj:
            st.markdown("#### 🩹 Injury report & availability signals")
            try:
                injury_payload = get_espn_feed(news_sport, "injuries")
                injury_items = extract_injury_items(injury_payload)
                injury_signature = json.dumps(injury_items, sort_keys=True, default=str)
                injury_key = f"{news_sport}:injuries"
                previous_signature = st.session_state.feed_fingerprints.get(injury_key)
                if previous_signature is not None and previous_signature != injury_signature and alert_feed_changes:
                    message = f"Injury feed updated for {news_sport}: the reported player availability list changed. Verify the individual report."
                    st.session_state.scout_alerts.insert(0, {"time": datetime.now(timezone.utc).isoformat(), "type": "Injury update", "message": message, "url": ""})
                    if telegram_enabled:
                        try:
                            send_telegram(message)
                        except requests.RequestException as exc:
                            st.warning(f"Telegram injury alert failed: {exc}")
                st.session_state.feed_fingerprints[injury_key] = injury_signature
                if not injury_items:
                    st.info("No injuries were returned in the expected format. This does not mean every player is healthy.")
                else:
                    injury_df = pd.DataFrame(injury_items)
                    st.dataframe(injury_df, use_container_width=True, hide_index=True, height=420)
                    st.download_button("Download injury report CSV", data=injury_df.to_csv(index=False).encode("utf-8"), file_name=f"{news_sport.lower().replace(' ', '_')}_injuries.csv", mime="text/csv")
            except requests.RequestException as exc:
                st.warning(f"Injury feed unavailable for {news_sport}: {exc}")

with st.expander("🔔 Recent change alerts", expanded=False):
    st.caption("Alerts are detected only while this app session is active. Market snapshots refresh on the selected timer; ESPN news/injury feeds are cached for up to 30 minutes. This is not a background monitoring service.")
    if st.session_state.scout_alerts:
        alert_cols = st.columns([1, 5])
        if alert_cols[0].button("Clear alerts"):
            st.session_state.scout_alerts = []
            st.rerun()
        for alert in st.session_state.scout_alerts[:25]:
            st.markdown(f"**{alert['type']}** · {str(alert['time']).replace('T', ' ')[:19]} UTC")
            st.write(alert["message"])
            if alert.get("url"):
                st.markdown(f"[Open related market]({alert['url']})")
            st.divider()
    else:
        st.info("No changes detected yet. The app needs at least one baseline refresh before it can detect price moves or feed changes.")

with tab_history:
    st.markdown('<div class="section-label">Model accountability</div>', unsafe_allow_html=True)
    st.subheader("Prediction history and accuracy")
    if st.button("🔄 Check completed games and update results from ESPN"):
        with st.spinner("Checking saved predictions against ESPN scoreboards…"):
            try:
                updated_count, checked_count = sync_saved_results(conn)
                st.success(f"Checked {checked_count} pending prediction(s); updated {updated_count} completed result(s).")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not sync results: {exc}")
    history = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC", conn)
    if history.empty:
        st.info("No predictions recorded yet. Go to Sports predictions and save one.")
    else:
        c1, c2, c3 = st.columns(3)
        settled = history[history["result"].isin(["Win", "Loss"])]
        c1.metric("Predictions saved", len(history))
        c2.metric("Settled predictions", len(settled))
        c3.metric("Accuracy on settled picks", f"{(settled['result'].eq('Win').mean() * 100):.1f}%" if not settled.empty else "Not yet available")
        st.caption("Accuracy is only calculated after you manually enter results. This avoids pretending an unverified outcome was settled.")
        edited = st.data_editor(
            history[["id", "created_utc", "sport", "matchup", "pick", "model_probability", "event_date", "result", "notes"]],
            use_container_width=True, hide_index=True, disabled=["id", "created_utc", "sport", "matchup", "pick", "model_probability", "event_date"],
            column_config={
                "result": st.column_config.SelectboxColumn("Result", options=["Pending", "Win", "Loss", "Void"], required=True),
                "model_probability": st.column_config.NumberColumn("Model probability", format="%.1%%"),
            },
            key="history_editor"
        )
        if st.button("Save result updates"):
            for _, row in edited.iterrows():
                result = row["result"]
                if result == "Pending":
                    result = None
                conn.execute("UPDATE predictions SET result=?, notes=? WHERE id=?", (result, row["notes"], int(row["id"])))
            conn.commit()
            st.success("Results updated.")
            st.rerun()
        if not settled.empty:
            scored = settled.copy()
            scored["actual"] = scored["result"].map({"Win": 1.0, "Loss": 0.0})
            scored["brier_component"] = (scored["model_probability"] - scored["actual"]) ** 2
            st.metric("Brier score (lower is better)", f"{scored['brier_component'].mean():.3f}")
        st.download_button("Download prediction history CSV", data=history.to_csv(index=False).encode("utf-8"),
                           file_name="prediction_history.csv", mime="text/csv")
        st.warning("Important: Streamlit Community Cloud's local files may be reset when the app restarts or redeploys. Download your history CSV regularly; a persistent database can be added later.")

st.divider()
st.caption("Model limitations: recent-results Elo baseline; news/injury feeds may be incomplete and do not change probabilities; possible market matches are heuristic and require manual verification; no independent backtest. No automatic betting is performed.")
