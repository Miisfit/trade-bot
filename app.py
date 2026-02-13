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
    if last["EMA20"] > last
