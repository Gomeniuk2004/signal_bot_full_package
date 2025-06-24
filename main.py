# -*- coding: utf-8 -*-
import asyncio
import logging
import time
import yfinance as yf
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler

# ==== Налаштування ====
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966
INTERVAL = "5m"

SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "USDJPY=X",
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURAUD=X", "GBPJPY=X", "GBPCHF=X", "CADJPY=X",
    "CHFJPY=X", "AUDJPY=X", "NZDJPY=X", "AUDCAD=X", "AUDNZD=X", "GBPCAD=X"
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# === Команда /start ===
async def start(update: Update, context):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Бот активований. Очікую сигнали..."
    )

# === Аналіз однієї пари ===
async def analyze(symbol):
    try:
        data = yf.download(tickers=symbol, period="1d", interval=INTERVAL)
        if data.empty:
            return None

        close = data["Close"]
        last_price = round(close.iloc[-1], 5)
        ema = close.ewm(span=14).mean().iloc[-1]
        signal = "Купити" if last_price > ema else "Продати"

        return (
            symbol.replace("=X", ""),
            signal,
            last_price,
            round(ema, 5)
        )
    except Exception as e:
        logging.warning(f"Помилка з {symbol}: {e}")
        return None

# === Відправка сигналів ===
async def send_signals(bot):
    while True:
        for symbol in SYMBOLS:
            result = await analyze(symbol)
            if result:
                pair, signal, price, ema = result
                msg = (
                    f"Pair: {pair}\n"
                    f"Signal: {signal}\n"
                    f"Price: {price}\n"
                    f"EMA: {ema}"
                )
                try:
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
                except Exception as e:
                    logging.warning(f"Не вдалося надіслати {pair}: {e}")
            time.sleep(1)  # щоб не перевантажувати API
        await asyncio.sleep(60)

# === Головна функція ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    asyncio.create_task(send_signals(app.bot))
    await app.run_polling()

# === Старт ===
if __name__ == "__main__":
    asyncio.run(main())