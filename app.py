from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import ccxt
import yfinance as yf
import requests
import threading
import time
import os
from datetime import datetime

# ---------------------------
# APP SETUP
# ---------------------------
app = Flask(__name__)

# ---------------------------
# GLOBAL STATE
# ---------------------------
watchlist = ["BTC/USDT","ETH/USDT","SOL/USDT","ES=F","NQ=F"]  # Futures + crypto
market_data = {}
signals = {}
news_data = {}
trade_history = []
paper_balance = 10000

WEBHOOK = ""  # Add TradingView webhook later

# ---------------------------
# INDICATORS
# ---------------------------
def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rs = gain / loss
    return 100 - (100/(1+rs))

def atr(df, length=14):
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(length).mean()

# ---------------------------
# MARKET DATA
# ---------------------------
def get_crypto(symbol):
    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)
    df = pd.DataFrame(bars, columns=["time","open","high","low","close","volume"])
    return df

def get_stock(symbol):
    df = yf.download(symbol, period="5d", interval="1h")
    df.reset_index(inplace=True)
    df.rename(columns={"Close":"close"}, inplace=True)
    return df

def get_futures(symbol):
    if "USDT" in symbol or symbol in ["BTC/USDT","ETH/USDT","SOL/USDT"]:
        return get_crypto(symbol)
    else:
        return get_stock(symbol)

# ---------------------------
# SIGNAL CALCULATION
# ---------------------------
def compute_signal(df):
    df["EMA20"] = ema(df["close"],20)
    df["EMA50"] = ema(df["close"],50)
    df["RSI"] = rsi(df["close"])
    df["ATR"] = atr(df)

    last = df.iloc[-1]
    if last["EMA20"] > last["EMA50"] and last["RSI"] < 65:
        return "Bullish"
    elif last["EMA20"] < last["EMA50"] and last["RSI"] > 35:
        return "Bearish"
    else:
        return "Neutral"

# ---------------------------
# NEWS FETCHER (SENTIMENT)
# ---------------------------
def fetch_news(symbol):
    try:
        # Replace with your API key
        API_KEY = "d67j109r01qobepi65rgd67j109r01qobepi65s0"
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={datetime.now().strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}&token={API_KEY}"
        news = requests.get(url).json()
        headlines = [n["headline"] for n in news[:5]]
        return headlines
    except:
        return ["No news available"]

# ---------------------------
# PAPER TRADING SIMULATION
# ---------------------------
positions = {}

def update_paper_balance(symbol, signal, price):
    global paper_balance, trade_history, positions
    if signal == "Bullish":
        positions[symbol] = price
    elif signal == "Bearish" and symbol in positions:
        profit = price - positions[symbol]
        paper_balance += profit
        trade_history.append({
            "symbol": symbol,
            "profit": round(profit,2),
            "balance": round(paper_balance,2),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "signal": "Short Closed"
        })
        del positions[symbol]

# ---------------------------
# BOT LOOP
# ---------------------------
def assistant_loop():
    global market_data, signals, news_data
    while True:
        for symbol in watchlist:
            try:
                df = get_futures(symbol)
                market_data[symbol] = df
                signal = compute_signal(df)
                signals[symbol] = signal
                news_data[symbol] = fetch_news(symbol)
                update_paper_balance(symbol, signal, df["close"].iloc[-1])
            except:
                signals[symbol] = "Error"
                news_data[symbol] = ["Error fetching news"]
        time.sleep(300)

threading.Thread(target=assistant_loop, daemon=True).start()

# ---------------------------
# DASHBOARD
# ---------------------------
@app.route("/", methods=["GET","POST"])
def index():
    global watchlist
    if request.method == "POST":
        symbols = request.form.get("symbols","BTC/USDT,ETH/USDT,ES=F,NQ=F").upper()
        watchlist = [s.strip() for s in symbols.split(",")]
    return render_template(
        "index.html",
        watchlist=watchlist,
        signals=signals,
        news=news_data,
        trade_history=trade_history,
        paper_balance=paper_balance
    )

# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
