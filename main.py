# -*- coding: utf-8 -*-
import asyncio
import time
import logging
import yfinance as yf
import nest_asyncio

from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler

# Твій токен і чат
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966
INTERVAL = "5m"

SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X",
    "USDCHF=X", "USDJPY=X", "EURGBP=X", "EURJPY=X", "EURCHF=X",
    "EURAUD=X", "GBPJPY=X", "GBPCHF=X", "CADJPY=X", "CHFJPY=X",
    "AUDJPY=X", "NZDJPY=X", "AUDCAD=X", "AUDNZD=X", "GBPCAD=X"
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

async def start(update: Update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Бот активовано.")

async def analyze(symbol):
    try:
        data = yf.download(tickers=symbol, period="1d", interval=INTERVAL)
        if data.empty:
            return None

        close = data["Close"]
        last_price = close.iloc[-1]
        ema = close.ewm(span=14).mean().iloc[-1]
        signal = "Купити" if last_price > ema else "Продати"

        return (
            symbol.replace("=X", ""),
            signal,
            round(last_price, 5),
            round(ema, 5)
        )
    except Exception as e:
        logging.warning(f"Помилка з {symbol}: {e}")
        return None

async def send_signals(bot):
    while True:
        for symbol in SYMBOLS:
            result = await analyze(symbol)
            if result:
                pair, signal, price, ema = result
                msg = f"Пара: {pair}\nСигнал: {signal}\nЦіна: {price}\nEMA: {ema}"
                try:
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
                except Exception as e:
                    logging.warning(f"Не вдалося надіслати сигнал для {pair}: {e}")
            time.sleep(1)
        await asyncio.sleep(60)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    asyncio.create_task(send_signals(app.bot))
    await app.run_polling()

# Запуск
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())