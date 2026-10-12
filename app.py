None selected 

Skip to content
Using Gmail with screen readers
1 of 5,429
app
Inbox

Maverick Whitfield <maverickwhit2@gmail.com>
Attachments
11:09 PM (0 minutes ago)
to me

 One attachment
  •  Scanned by Gmail
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

st.set_page_config(page_title="Polymarket Sports Scout", page_icon="🏟️", layout="wide")
st.title("🏟️ Polymarket Sports Scout")
st.caption("Research dashboard with a basic Elo model and prediction tracking. Not financial advice.")

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

def get_events():
    response = requests.get(
        f"{GAMMA}/events",
        params={"active": "true", "closed": "false", "limit": 100, "offset": 0},
        timeout=20,
        headers={"User-Agent": "PolymarketSportsScout/0.2"},
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
        if isinstance(tag, dict) else str(tag) for tag in tags
    ).lower()
    title = (str(event.get("title", "")) + " " + str(event.get("slug", ""))).lower()
    return any(word in tag_text for word in ("sport", "nfl", "nba", "mlb", "nhl", "soccer", "tennis", "ufc")) or any(
        word in title for word in SPORT_WORDS
    )

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
    st.divider()
    st.subheader("Prediction engine")
    selected_sports = st.multiselect("Sports to model", list(ESPN_SPORTS.keys()), default=["NFL", "NBA", "MLB", "NHL"])
    days_back = st.select_slider("Recent results used for ratings", options=[7, 14, 21, 30], value=14)
    st.caption("Uses public ESPN scoreboard data and a basic Elo model. Coverage depends on ESPN schedules.")
    telegram_enabled = st.checkbox("Enable Telegram price alerts", value=False)

st_autorefresh(interval=refresh_seconds * 1000, key="market_refresh")
conn = db_connect()

tab_market, tab_model, tab_news, tab_history = st.tabs(["Market scanner", "Sports predictions", "News & injuries", "Prediction tracking"])

with tab_market:
    try:
        with st.spinner("Loading Polymarket markets…"):
            events = get_events()
            df = flatten_events(events)
    except requests.RequestException as exc:
        st.error(f"Could not load Polymarket data: {exc}")
        df = pd.DataFrame()
        events = []
    if df.empty:
        st.warning("No sports-looking markets were found in this page of results, or the API is temporarily unavailable.")
    else:
        df["Price alert candidate"] = (df["Market price"] <= max_price) & (df["Liquidity ($)"] >= min_liquidity)
        candidates = df[df["Price alert candidate"]].copy()
        display_df = candidates if only_watchlist else df
        display_df = display_df.sort_values(["24h volume ($)", "Liquidity ($)"], ascending=False)
        m1, m2, m3 = st.columns(3)
        m1.metric("Sports outcome rows found", f"{len(df):,}")
        m2.metric("Price-alert candidates", f"{len(candidates):,}")
        m3.metric("Events scanned", f"{len(events):,}")
        st.info("A low price is not proof of value. Model probabilities appear in the Sports predictions tab for ESPN-listed matchups; they are not automatically matched to Polymarket markets.")
        view = display_df.copy()
        view["Market price"] = view["Market price"].map(lambda x: f"${x:.3f}")
        view["Implied probability"] = view["Implied probability"].map(lambda x: f"{x:.1%}")
        view["Liquidity ($)"] = view["Liquidity ($)"].map(lambda x: f"${x:,.0f}")
        view["24h volume ($)"] = view["24h volume ($)"].map(lambda x: f"${x:,.0f}")
        st.dataframe(view[["Sport/event", "Market", "Outcome", "Market price", "Implied probability", "Liquidity ($)", "24h volume ($)", "Price alert candidate", "URL"]],
                     use_container_width=True, hide_index=True,
                     column_config={"URL": st.column_config.LinkColumn("Open market", display_text="View on Polymarket")})
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
                    pretty = pred_df.copy()
                    pretty["Team A win probability"] = pretty["Team A win probability"].map(lambda x: f"{x:.1%}")
                    pretty["Team B win probability"] = pretty["Team B win probability"].map(lambda x: f"{x:.1%}")
                    st.dataframe(pretty[["Matchup", "Team A Elo", "Team B Elo", "Team A win probability", "Team B win probability", "Start", "Status"]],
                                 use_container_width=True, hide_index=True)
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

with tab_history:
    st.subheader("Prediction history and accuracy")
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
st.caption("Model limitations: recent-results Elo baseline; news/injury feeds may be incomplete; news is not yet used to change probabilities; no independent backtest yet; no automatic matching to Polymarket contracts. No automatic betting is performed.")
app.py
Displaying app.py. 
