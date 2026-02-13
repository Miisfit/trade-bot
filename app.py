from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import ccxt
import requests
import threading
import time

app = Flask(__name__)

bot_running = False
current_signal = "Waiting..."

config = {
    "symbol": "BTC/USDT",
    "market": "crypto",
    "leverage": 2
}

################ MARKET DATA ################

def get_crypto(symbol):

    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)

    df = pd.DataFrame(bars, columns=["time","open","high","low","close","volume"])
    return df

def get_stock(symbol):

    df = yf.download(symbol, period="5d", interval="1h")
    return df

################ STRATEGY ################

def strategy(df):

    df["EMA20"] = ta.ema(df["close"], length=20)
    df["EMA50"] = ta.ema(df["close"], length=50)
    df["RSI"] = ta.rsi(df["close"], length=14)

    last = df.iloc[-1]

    if last["EMA20"] > last["EMA50"] and last["RSI"] < 70:
        return "BUY"

    if last["EMA20"] < last["EMA50"] and last["RSI"] > 30:
        return "SELL"

    return "HOLD"

################ BOT LOOP ################

def bot_loop():

    global current_signal

    while True:

        if bot_running:

            if config["market"] == "crypto":
                df = get_crypto(config["symbol"])
            else:
                df = get_stock(config["symbol"])

            signal = strategy(df)
            current_signal = signal

        time.sleep(300)

threading.Thread(target=bot_loop, daemon=True).start()

################ WEB UI ################

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

    return render_template("index.html",
                           running=bot_running,
                           signal=current_signal,
                           config=config)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
