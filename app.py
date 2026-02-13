from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import ccxt
import numpy as np
import threading
import time
import os

app = Flask(__name__)

#############################
# BOT STATE
#############################

bot_running = False
current_signal = "Waiting..."

config = {
    "symbol": "BTC/USDT",
    "market": "crypto",
    "leverage": 2
}

#############################
# INDICATORS
#############################

def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def rsi(series, length=14):

    delta = series.diff()

    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))

#############################
# MARKET DATA
#############################

def get_crypto(symbol):

    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)

    df = pd.DataFrame(
        bars,
        columns=["time","open","high","low","close","volume"]
    )

    return df

def get_stock(symbol):

    df = yf.download(symbol, period="5d", interval="1h")
    df.reset_index(inplace=True)
    df.rename(columns={"Close":"close"}, inplace=True)

    return df

#############################
# STRATEGY
#############################

def strategy(df):

    df["EMA20"] = ema(df["close"], 20)
    df["EMA50"] = ema(df["close"], 50)
    df["RSI"] = rsi(df["close"])

    last = df.iloc[-1]

    if last["EMA20"] > last["EMA50"] and last["RSI"] < 70:
        return "BUY"

    if last["EMA20"] < last["EMA50"] and last["RSI"] > 30:
        return "SELL"

    return "HOLD"

#############################
# BOT LOOP
#############################

def bot_loop():

    global current_signal

    while True:

        try:

            if bot_running:

                if config["market"] == "crypto":
                    df = get_crypto(config["symbol"])
                else:
                    df = get_stock(config["symbol"])

                signal = strategy(df)
                current_signal = signal

        except Exception as e:
            current_signal = f"Error: {str(e)}"

        time.sleep(300)

#############################
# WEB ROUTES
#############################

@app.route("/", methods=["GET","POST"])
def index():

    global bot_running

    if request.method == "POST":

        config["symbol"] = request.form["symbol"]
        config["market"] = request.form["market"]
        config["leverage"] = int(request.form["leverage"])

        if "start" in request.form:
            bot_running = True

        if "stop" in request.form:
            bot_running = False

    return render_template(
        "index.html",
        running=bot_running,
        signal=current_signal,
        config=config
    )

#############################
# START SERVER
#############################

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
