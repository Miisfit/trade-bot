from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import ccxt
import threading
import time
import os
import requests

app = Flask(__name__)

################ STATE ################

bot_running = False
current_signal = "Waiting..."

trade_history = []
paper_balance = 10000
position = None
entry_price = None

config = {
    "symbol": "BTC/USDT",
    "leverage": 3
}

WEBHOOK = ""   # Add TradingView webhook later

################ INDICATORS ################

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
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(length).mean()

################ DATA ################

def get_futures(symbol):

    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=200)

    df = pd.DataFrame(bars, columns=[
        "time","open","high","low","close","volume"
    ])

    return df

################ STRATEGY ################

def strategy(df):

    df["EMA20"] = ema(df["close"],20)
    df["EMA50"] = ema(df["close"],50)
    df["RSI"] = rsi(df["close"])
    df["ATR"] = atr(df)

    last = df.iloc[-1]

    if last["EMA20"] > last["EMA50"] and last["RSI"] < 65:
        return "LONG"

    if last["EMA20"] < last["EMA50"] and last["RSI"] > 35:
        return "SHORT"

    return "HOLD"

################ WEBHOOK ################

def send_webhook(signal, price):

    if WEBHOOK == "":
        return

    payload = {
        "signal": signal,
        "price": price,
        "symbol": config["symbol"],
        "leverage": config["leverage"]
    }

    requests.post(WEBHOOK, json=payload)

################ BOT LOOP ################

def bot_loop():

    global current_signal
    global paper_balance
    global position
    global entry_price

    while True:

        try:

            if bot_running:

                df = get_futures(config["symbol"])
                signal = strategy(df)

                price = df["close"].iloc[-1]
                current_signal = signal

                # ENTRY
                if position is None:

                    if signal == "LONG":
                        position = "LONG"
                        entry_price = price
                        send_webhook("BUY", price)

                    elif signal == "SHORT":
                        position = "SHORT"
                        entry_price = price
                        send_webhook("SELL", price)

                # EXIT LOGIC
                elif position == "LONG":

                    profit = (price - entry_price) * config["leverage"]

                    if signal == "SHORT":
                        paper_balance += profit
                        trade_history.append({
                            "type":"LONG",
                            "profit":round(profit,2),
                            "balance":round(paper_balance,2)
                        })

                        position = None

                elif position == "SHORT":

                    profit = (entry_price - price) * config["leverage"]

                    if signal == "LONG":
                        paper_balance += profit
                        trade_history.append({
                            "type":"SHORT",
                            "profit":round(profit,2),
                            "balance":round(paper_balance,2)
                        })

                        position = None

        except Exception as e:
            current_signal = str(e)

        time.sleep(300)

################ WEB ################

@app.route("/", methods=["GET","POST"])
def index():

    global bot_running

    if request.method == "POST":

        config["symbol"] = request.form["symbol"]
        config["leverage"] = int(request.form["leverage"])

        if "start" in request.form:
            bot_running = True

        if "stop" in request.form:
            bot_running = False

    return render_template(
        "index.html",
        running=bot_running,
        signal=current_signal,
        balance=paper_balance,
        position=position,
        history=trade_history[-6:],
        config=config
    )

################ START ################

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
