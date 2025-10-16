#!/usr/bin/env python3
"""
Whale Watch Bot integrated precisely with your blockchain-dashboard-api routes:
  /api/market
  /api/exchange_flows
  /api/stablecoin
  /api/whale_transfers
"""

import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL")  # e.g. "https://your-api-domain.com"
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
API_KEY = os.getenv("API_KEY")  # optional, if your API needs auth

if not TOKEN:
    raise SystemExit("Missing TELEGRAM_TOKEN in .env")

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger("WhaleWatchBot")

# Fallback sample data (same as before)
SAMPLE_OVERVIEW = {
    "market": {"symbol":"ETH","price_usd":3757.84,"price_change_24h_pct":-13.22,"volume_24h_usd":104_010_000_000,"market_cap_usd":454_450_000_000},
    "exchange_flows": {"total_inflow":530_276_600,"total_outflow":663_261_947,"net_flow":-132_985_346,"sentiment":"Strong Accumulation (Bullish)"},
    "stablecoin": {"stablecoin_inflow_ratio_pct":100.0,"stablecoin_net_flow":-20_000_000,"mode":"Risk-Off -> Deploying"},
    "whale_transfers":[
        {"token":"USDT","from":"0xc0ba...1a09","to":"0x28c6...1d60","amount":1_851_370.43},
        {"token":"USDT","from":"0x17dc...403a","to":"0xaa8b...3efb","amount":39_365_167.96},
    ]
}

def headers():
    h = {"Accept": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h

def try_get(path):
    """GET request to DASHBOARD_API_URL + path; returns JSON or None."""
    if not DASHBOARD_API_URL:
        return None
    url = DASHBOARD_API_URL.rstrip("/") + path
    try:
        resp = requests.get(url, headers=headers(), timeout=8)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("GET %s failed: %s", url, e)
        return None

def fetch_dashboard_overview():
    """
    Fetch segmented endpoints and build the overview object.
    """
    market = try_get("/api/market")
    flows = try_get("/api/exchange_flows")
    stable = try_get("/api/stablecoin")
    whales = try_get("/api/whale_transfers")

    # If all succeeded and contain data, return combined object
    if market and flows and stable and whales is not None:
        return {
            "market": market,
            "exchange_flows": flows,
            "stablecoin": stable,
            "whale_transfers": whales
        }
    # Else, fallback to sample or partial
    ov = {}
    ov["market"] = market or SAMPLE_OVERVIEW["market"]
    ov["exchange_flows"] = flows or SAMPLE_OVERVIEW["exchange_flows"]
    ov["stablecoin"] = stable or SAMPLE_OVERVIEW["stablecoin"]
    ov["whale_transfers"] = whales or SAMPLE_OVERVIEW["whale_transfers"]
    return ov

def fmt_usd(n):
    try:
        if isinstance(n, (int, float)):
            return f"${n:,.2f}"
        return str(n)
    except:
        return str(n)

def short_addr(addr):
    if not addr or len(addr) < 10:
        return addr or ""
    return f"{addr[:6]}...{addr[-4:]}"

# -- Telegram command handlers --

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Whale Watch Bot\n\n"
        "Use these commands:\n"
        "/market — ETH market overview\n"
        "/flows — Exchange inflow/outflow stats\n"
        "/risk — Stablecoin rotation metrics\n"
        "/whales — Recent whale transfers\n"
        "/insight — Market interpretation\n\n"
        "Make sure DASHBOARD_API_URL is correctly set to your API."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = fetch_dashboard_overview()
    m = ov["market"]
    msg = (
        f"ETH Market Overview\n\n"
        f"Price: {fmt_usd(m.get('price_usd','N/A'))} (24h: {m.get('price_change_24h_pct',0):+.2f}%)\n"
        f"24h Volume: {fmt_usd(m.get('volume_24h_usd','N/A'))}\n"
        f"Market Cap: {fmt_usd(m.get('market_cap_usd','N/A'))}\n"
        f"As of {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def flows_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = fetch_dashboard_overview()
    f = ov["exchange_flows"]
    msg = (
        "Exchange Flows\n\n"
        f"Total Inflow: {fmt_usd(f.get('total_inflow','N/A'))}\n"
        f"Total Outflow: {fmt_usd(f.get('total_outflow','N/A'))}\n"
        f"Net Flow: {fmt_usd(f.get('net_flow','N/A'))}\n"
        f"Sentiment: {f.get('sentiment','N/A')}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def risk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = fetch_dashboard_overview()
    s = ov["stablecoin"]
    msg = (
        "Stablecoin Rotation / Risk\n\n"
        f"Stablecoin Inflow Ratio: {s.get('stablecoin_inflow_ratio_pct','N/A')}%\n"
        f"Stablecoin Net Flow: {fmt_usd(s.get('stablecoin_net_flow','N/A'))}\n"
        f"Mode: {s.get('mode','N/A')}\n\n"
        "High inflow ratio → risk-off. Outflows → deploying to buy crypto."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def whales_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = fetch_dashboard_overview()
    transfers = ov["whale_transfers"][:10]
    if not transfers:
        await update.message.reply_text("No recent whale transfers.")
        return
    lines = ["Recent Whale Transfers"]
    for t in transfers:
        lines.append(
            f"- {t.get('token','')} {short_addr(t.get('from'))} → {short_addr(t.get('to'))} : {fmt_usd(t.get('amount','N/A'))}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def insight_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = fetch_dashboard_overview()
    f = ov["exchange_flows"]
    s = ov["stablecoin"]
    m = ov["market"]
    netf = f.get("net_flow")
    ratio = s.get("stablecoin_inflow_ratio_pct")
    stable_net = s.get("stablecoin_net_flow")

    lines = []
    # Header with price
    lines.append(f"Insight — ETH {fmt_usd(m.get('price_usd','N/A'))}")

    # Flow interpretation
    if isinstance(netf, (int, float)):
        if netf < 0:
            lines.append("🔵 Flows: Net outflows → accumulation (bullish signal).")
        elif netf > 0:
            lines.append("🔴 Flows: Net inflows → distribution / sell pressure.")
        else:
            lines.append("⚪ Flows: Neutral.")

    # Stablecoin signals
    if isinstance(ratio, (int, float)):
        if ratio >= 70:
            lines.append("🟠 Stablecoin: High inflow ratio → risk-off (whales holding safety).")
        elif ratio <= 30:
            lines.append("🟢 Stablecoin: Low ratio → deploying into crypto (accumulation).")
        else:
            lines.append("🟡 Stablecoin: Mixed / transitional state.")

    # Combined heuristic
    if isinstance(netf, (int, float)) and isinstance(stable_net, (int, float)):
        if netf < 0 and stable_net < 0:
            lines.append("✅ Combined: Whales pulling assets and deploying stablecoins → strong accumulation.")
        elif netf < 0 < stable_net:
            lines.append("⚠ Tokens leaving but stablecoins coming in — watch closely.")
        elif netf > 0 and stable_net > 0:
            lines.append("❌ Distribution + stablecoin build-up → bearish posture.")

    lines.append(f"\n_As of {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# Alerts scheduler
scheduler = BackgroundScheduler()

def check_and_send_alert(app: Application):
    if not ADMIN_CHAT_ID:
        return
    ov = fetch_dashboard_overview()
    f = ov["exchange_flows"]
    whales = ov["whale_transfers"]
    netf = f.get("net_flow", 0)
    alerts = []

    # thresholds
    ACCUM_THRESHOLD = -50_000_000
    DIST_THRESHOLD = 50_000_000
    BIG_TX_THRESHOLD = 10_000_000

    if isinstance(netf, (int, float)):
        if netf <= ACCUM_THRESHOLD:
            alerts.append(f"🚨 Strong accumulation: Net Flow = {fmt_usd(netf)}")
        if netf >= DIST_THRESHOLD:
            alerts.append(f"⚠ Strong distribution: Net Flow = {fmt_usd(netf)}")

    for t in whales:
        amt = t.get("amount", 0)
        if isinstance(amt, (int, float)) and amt >= BIG_TX_THRESHOLD:
            alerts.append(f"🐋 Whale transfer: {fmt_usd(amt)} {t.get('token')} from {short_addr(t.get('from'))} to {short_addr(t.get('to'))}")

    if alerts:
        text = "\n".join(alerts)
        app.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("market", market_cmd))
    app.add_handler(CommandHandler("flows", flows_cmd))
    app.add_handler(CommandHandler("risk", risk_cmd))
    app.add_handler(CommandHandler("whales", whales_cmd))
    app.add_handler(CommandHandler("insight", insight_cmd))

    scheduler.add_job(lambda: check_and_send_alert(app), "interval", minutes=5, id="alerts", replace_existing=True)
    scheduler.start()
    logger.info("Bot started")
    app.run_polling()

