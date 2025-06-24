import asyncio
import datetime
import pytz
import logging
import os
import io
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import yfinance as yf
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands

TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966
PAIRS = ["EURUSD=X", "GBPUSD=X", "USDCHF=X", "USDJPY=X", "AUDUSD=X"]
INTERVAL = "5m"
TIMEZONE = "Europe/Kyiv"

logging.basicConfig(level=logging.INFO)

def analyze_signals(df):
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema = EMAIndicator(close, window=9).ema_indicator().iloc[-1]
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    macd = MACD(close).macd_diff().iloc[-1]
    stochastic = StochasticOscillator(close, high, low).stoch_signal().iloc[-1]
    bb_upper = BollingerBands(close).bollinger_hband().iloc[-1]
    bb_lower = BollingerBands(close).bollinger_lband().iloc[-1]

    signal = None
    if rsi < 35 and macd > 0 and stochastic < 40:
        signal = "Купити"
    elif rsi > 65 and macd < 0 and stochastic > 60:
        signal = "Продати"
    return signal, ema, rsi, macd, stochastic, bb_upper, bb_lower

def plot_candlestick(df, pair):
    df.index.name = 'Date'
    df_plot = df[['Open', 'High', 'Low', 'Close']]
    buffer = io.BytesIO()
    mpf.plot(df_plot, type='candle', style='charles', title=pair, ylabel='Ціна',
             volume=False, savefig=dict(fname=buffer, dpi=100, bbox_inches='tight'))
    buffer.seek(0)
    return buffer

def get_kyiv_time():
    return datetime.datetime.now(pytz.timezone(TIMEZONE))

async def send_signal(app):
    for pair in PAIRS:
        try:
            df = yf.download(pair, interval=INTERVAL, period="90m", progress=False)
            if df.empty:
                continue

            signal, ema, rsi, macd, stochastic, bb_upper, bb_lower = analyze_signals(df)
            if signal:
                now = get_kyiv_time()
                entry_until = (now + datetime.timedelta(minutes=5)).strftime("%H:%M")
                buffer = plot_candlestick(df.tail(30), pair)

                msg = f"""
📊 Валютна пара: {pair.replace('=X', '')}
⏱️ Таймфрейм: 5 хв
📈 Сигнал: {signal}
🕐 Угоду слід відкрити ДО: *{entry_until}* (за Києвом)

📋 Пояснення:
RSI: {rsi:.2f}
EMA(9): {ema:.5f}
MACD: {macd:.5f}
Stochastic: {stochastic:.2f}
Bollinger Bands: верхня={bb_upper:.5f}, нижня={bb_lower:.5f}
Ціна: {df['Close'].iloc[-1]:.5f}
                """.strip()

                await app.bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=buffer,
                    caption=msg,
                    parse_mode='Markdown'
                )
                return
        except Exception as e:
            logging.error(f"Помилка з парою {pair}: {e}")

    await app.bot.send_message(chat_id=CHAT_ID, text="❌ Наразі немає чітких сигналів на 5 хвилин.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Бот активний. Шукаю сигнал...")
    await send_signal(context.application)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    async def periodic():
        while True:
            await send_signal(app)
            await asyncio.sleep(300)

    async def main():
        await app.initialize()
        await app.start()
        asyncio.create_task(periodic())
        await app.updater.start_polling()
        await app.updater.idle()

    asyncio.run(main())
