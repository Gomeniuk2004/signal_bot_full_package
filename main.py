import time
import pytz
import logging
import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime
from telegram import Bot
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands

# Токен і чат ID
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = "992940966"
bot = Bot(token=TOKEN)

logging.basicConfig(level=logging.INFO)

# Валютні пари Pocket Option
PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X",
    "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CHFJPY=X", "NZDJPY=X", "CADJPY=X",
    "EURCHF=X", "EURAUD=X", "GBPAUD=X", "AUDCAD=X", "AUDCHF=X", "NZDCAD=X", "NZDCHF=X",
    "BTC-USD", "ETH-USD", "LTC-USD", "XRP-USD", "BNB-USD", "SOL-USD", "DOGE-USD", "USDT-USD"
]

INTERVAL = "5m"

def fetch_data(symbol):
    try:
        data = yf.download(tickers=symbol, period="1d", interval=INTERVAL)
        if data.empty or len(data) < 21:
            logging.warning(f"Пара {symbol} неактивна або замало даних. Пропускаю.")
            return None
        return data
    except Exception as e:
        logging.warning(f"Помилка при завантаженні {symbol}: {e}")
        return None

def analyze(data):
    # Видаляємо останню (незакриту) свічку
    close = data["Close"].iloc[:-1].squeeze()
    high = data["High"].iloc[:-1].squeeze()
    low = data["Low"].iloc[:-1].squeeze()

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
    next_minute = (now.minute // 5 + 1) * 5
    entry_time = now.replace(minute=next_minute % 60, second=0)
    return entry_time.strftime('%H:%M')

async def send_signal(symbol, signal, latest):
    name = symbol.replace("=X", "").replace("-", "")
    message = (
        f"Пара: {name}\n"
        f"Сигнал: {signal}\n"
        f"Ціна: {latest['price']:.5f}\n"
        f"EMA: {latest['ema']:.5f}\n"
        f"RSI: {latest['rsi']:.2f}\n"
        f"MACD: {latest['macd']:.5f}\n"
        f"Stoch: {latest['stoch']:.2f}\n"
        f"Час входу (Київ): {format_time()}"
    )
    await bot.send_message(chat_id=CHAT_ID, text=message)

def wait_for_next_candle():
    now = datetime.now()
    seconds = now.minute * 60 + now.second
    wait = 300 - (seconds % 300)
    logging.info(f"Очікую {wait} секунд до наступної свічки...")
    time.sleep(wait)

def main():
    wait_for_next_candle()  # Синхронізує запуск
    while True:
        for symbol in PAIRS:
            data = fetch_data(symbol)
            if data is not None:
                signal, latest = analyze(data)
                if signal:
                    asyncio.run(send_signal(symbol, signal, latest))
        wait_for_next_candle()

if __name__ == "__main__":
    main()
