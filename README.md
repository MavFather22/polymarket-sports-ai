# Polymarket Sports Scout — beginner starter

This is a small Streamlit web dashboard that reads public Polymarket event data and displays likely sports outcomes.

## What it does
- Pulls the top 500 active events by 24-hour volume from the public Gamma API.
- Filters likely sports events using tags and keywords.
- Displays outcome prices, implied probabilities, liquidity, volume, and links.
- Flags outcomes that meet a chosen price and liquidity filter.
- Optionally sends Telegram alerts while the app is actively running and refreshing.

## Important limitations
This first version is a starter scanner, not a predictive AI model. It may miss sports events outside the top 500 events it fetches. A low price alone is not an edge. The app does not place trades. Telegram alerts are not guaranteed in the background if the hosted app is asleep. Do not use the output as financial advice.

## Run on your computer
1. Install Python 3.11 or newer from https://www.python.org/downloads/
2. Open Terminal (Mac) or PowerShell (Windows).
3. Move into this folder.
4. Create a virtual environment:
   - Mac/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
   - Windows: `py -m venv .venv` then `.venv\Scripts\activate`
5. Install packages: `pip install -r requirements.txt`
6. Start the app: `streamlit run app.py`
7. A browser tab should open. The same app can be accessed from another device only after it is deployed online.

## Put it online for phone + computer
1. Create a GitHub account at https://github.com/
2. Create a new repository, for example `polymarket-sports-scout`.
3. Upload `app.py`, `requirements.txt`, and `README.md` to the repository.
4. Visit https://share.streamlit.io/ and connect GitHub.
5. Choose the repository, branch `main`, and main file `app.py`, then deploy.
6. Save the app URL. Open it on both your iPhone and computer.

Streamlit Community Cloud is intended for personal/educational apps and has its own availability, usage, and sharing rules. If your dashboard contains sensitive data, configure access controls before sharing it.

## Optional Telegram alerts
1. In Telegram, message the official `@BotFather` account and create a bot. Copy its token.
2. Open a chat with your new bot and press Start. To find your chat ID, send the bot a message, then open `https://api.telegram.org/botYOUR_TOKEN/getUpdates` in a browser, replacing `YOUR_TOKEN` with your token. Do not share that URL or token with anyone.
3. In your Streamlit app settings, open Secrets and add:
   ```
   TELEGRAM_BOT_TOKEN = "your-bot-token"
   TELEGRAM_CHAT_ID = "your-chat-id"
   ```
4. Enable Telegram alerts in the app sidebar.
5. Never commit bot tokens to GitHub. If a token leaks, revoke it with BotFather.

The app sends alerts only when the page is actively refreshing and only for candidates visible in the current scan. For dependable alerts while the dashboard is closed, add a separate scheduled worker and persistent alert history in a later phase.

## Data source
Polymarket Gamma API: https://gamma-api.polymarket.com
API reference: https://gamma-api.polymarket.com/docs
Streamlit deployment docs: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
