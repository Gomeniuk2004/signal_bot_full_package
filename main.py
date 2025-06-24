import logging
import os
import pytz
import asyncio
import datetime
import yfinance as yf
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands
from ta.trend import MACD
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler

# Токен і чат
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966

# Логування
logging.basicConfig(level=logging.INFO)

# Валютні пари для аналізу
PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "EURGBP=X"]

# Таймфрейм
INTERVAL = "5m"

# Скільки свічок качати
LIMIT = 100

# Київський час
kyiv_tz = pytz.timezone("Europe/Kyiv")

def get_signal(df):
    df = df.copy()
    df["EMA"] = EMAIndicator(df["Close"], window=9).ema_indicator()
    df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()
    df["MACD"] = MACD(df["Close"]).macd_diff()
    stoch = StochasticOscillator(df["High"], df["Low"], df["Close"])
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()
    bb = BollingerBands(df["Close"])
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_lower"] = bb.bollinger_lband()
    last = df.iloc[-1]

    if last["RSI"] < 35 and last["MACD"] > 0 and last["Close"] > last["EMA"]:
        return "Купити"
    elif last["RSI"] > 65 and last["MACD"] < 0 and last["Close"] < last["EMA"]:
        return "Продати"
    else:
        return None

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🔍 Шукаю найкращий сигнал...")

    for pair in PAIRS:
        try:
            df = yf.download(pair, interval=INTERVAL, period="1d", progress=False)

            if len(df) < LIMIT:
                continue

            df = df.tail(LIMIT)

            signal = get_signal(df)
            if signal:
                now_kyiv = datetime.datetime.now(kyiv_tz)
                next_time = now_kyiv + datetime.timedelta(minutes=5)
                minute_target = next_time.strftime("%H:%M")

                name = pair.replace("=X", "")
                message = f"""
📈 Валютна пара: {name}
⏱️ Таймфрейм: 5 хв
💡 Сигнал: *{signal}*

🕒 Вхід до: *{minute_target}* (Київ)

📊 Індикатори:
RSI: {round(df['RSI'].iloc[-1], 2)}
EMA: {round(df['EMA'].iloc[-1], 5)}
MACD: {round(df['MACD'].iloc[-1], 5)}
Stoch %K: {round(df['Stoch_K'].iloc[-1], 2)} / %D: {round(df['Stoch_D'].iloc[-1], 2)}
BB: Верхня={round(df['BB_upper'].iloc[-1], 5)} / Нижня={round(df['BB_lower'].iloc[-1], 5)}
Ціна: {round(df['Close'].iloc[-1], 5)}
""".strip()

                await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode="Markdown")
                return

        except Exception as e:
            logging.error(f"Помилка для {pair}: {e}")
            continue

    await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Наразі немає чітких сигналів на 5 хвилин.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
