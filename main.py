import asyncio
import logging
import pytz
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from telegram import Bot
from io import BytesIO

# --- Конфіг ---
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966
PAIRS = ["EURAUD=X","CHFJPY=X","EURUSD=X","CADJPY=X","GBPJPY=X","EURCAD=X","AUDUSD=X","EURCHF=X","EURGBP=X","EURJPY=X",
         "USDCAD=X","AUDCAD=X","AUDJPY=X","USDJPY=X","AUDCHF=X","GBPUSD=X","GBPCHF=X","GBPCAD=X","CADCHF=X","GBPAUD=X","USDCHF=X"]

TIMEZONE = pytz.timezone("Europe/Kyiv")

# --- Сигнальна логіка ---
def get_signal(df):
    rsi = RSIIndicator(close=df['Close'], window=14).rsi().iloc[-1]
    ema_fast = EMAIndicator(close=df['Close'], window=5).ema_indicator().iloc[-1]
    ema_slow = EMAIndicator(close=df['Close'], window=20).ema_indicator().iloc[-1]

    if rsi < 30 and ema_fast > ema_slow:
        return "Купити"
    elif rsi > 70 and ema_fast < ema_slow:
        return "Продати"
    return None

# --- Завантаження графіку ---
def generate_chart(df, signal_time, signal_action):
    df = df.tail(50)
    mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc)

    signal_index = df.index.get_loc(signal_time) if signal_time in df.index else -1
    alines = [[(df.index[signal_index], df['Close'].iloc[signal_index]),
               (df.index[signal_index], df['Close'].iloc[signal_index] + 0.002)]]

    fig, axlist = mpf.plot(df, type='candle', style=s, returnfig=True, alines=dict(alines=alines, colors=['b']))

    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    return buf

# --- Основна логіка ---
async def send_signal(bot: Bot):
    while True:
        for pair in PAIRS:
            try:
                df = yf.download(pair, interval="5m", period="1d", progress=False)
                if df.empty: continue
                signal = get_signal(df)
                if signal:
                    now = datetime.now(TIMEZONE)
                    exit_time = (now + timedelta(minutes=5)).strftime("%H:%M")
                    chart = generate_chart(df, df.index[-1], signal)
                    text = f"📈 <b>Пара:</b> {pair.replace('=X','')}
💡 <b>Сигнал:</b> <u>{signal}</u>
⏱ <b>До:</b> {exit_time}"
                    await bot.send_photo(chat_id=CHAT_ID, photo=chart, caption=text, parse_mode="HTML")
            except Exception as e:
                print(f"❌ Error: {e}")
        await asyncio.sleep(10)

# --- Старт ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    asyncio.run(send_signal(bot))
