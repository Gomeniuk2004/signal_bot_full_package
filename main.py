import time
import pytz
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime
from telegram import Bot
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands

# 🔐 Вшиті значення
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = "992940966"
bot = Bot(token=TOKEN)

logging.basicConfig(level=logging.INFO)

PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "BTC-USD", "ETH-USD", "USDT-USD"]
INTERVAL = "5m"

def fetch_data(symbol):
    try:
        data = yf.download(tickers=symbol, period="1d", interval=INTERVAL)
        if data.empty:
            return None
        return data
    except Exception as e:
        logging.warning(f"Error fetching {symbol}: {e}")
        return None

def analyze(data):
    close = data["Close"].squeeze()
    high = data["High"].squeeze()
    low = data["Low"].squeeze()

    ema = EMAIndicator(close, window=14).ema_indicator()
    rsi = RSIIndicator(close, window=14).rsi()
    macd = MACD(close).macd_diff()
    stoch = StochasticOscillator(high, low, close).stoch()
    bb = BollingerBands(close)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()

    latest = {
        "price": close.iloc[-1],
        "ema": ema.iloc[-1],
        "rsi": rsi.iloc[-1],
        "macd": macd.iloc[-1],
        "stoch": stoch.iloc[-1],
        "bb_upper": bb_upper.iloc[-1],
        "bb_lower": bb_lower.iloc[-1],
    }

    signal = None
    if (
        latest["price"] > latest["ema"]
        and latest["rsi"] < 70
        and latest["macd"] > 0
        and latest["stoch"] > 50
        and latest["price"] < latest["bb_upper"]
    ):
        signal = "Купити"
    elif (
        latest["price"] < latest["ema"]
        and latest["rsi"] > 30
        and latest["macd"] < 0
        and latest["stoch"] < 50
        and latest["price"] > latest["bb_lower"]
    ):
        signal = "Продати"

    return signal, latest

def format_time():
    kyiv = pytz.timezone("Europe/Kyiv")
    now = datetime.now(kyiv)
    entry_minute = (now.minute // 5 + 1) * 5
    entry_time = now.replace(minute=entry_minute % 60, second=0)
    return entry_time.strftime('%H:%M')

def send_signal(symbol, signal, latest):
    name = symbol.replace("=X", "").replace("-", "")
    message = f"""📡 <b>Сигнал для {name}</b>
Дія: <b>{signal}</b>
Ціна: {latest['price']:.5f}
EMA: {latest['ema']:.5f}
RSI: {latest['rsi']:.2f}
MACD: {latest['macd']:.5f}
Stoch: {latest['stoch']:.2f}
Час входу (Київ): <b>{format_time()}</b>
#Signal24
"""
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")

def main():
    while True:
        for symbol in PAIRS:
            data = fetch_data(symbol)
            if data is not None:
                signal, latest = analyze(data)
                if signal:
                    send_signal(symbol, signal, latest)
        time.sleep(60)

if __name__ == "__main__":
    main()
