# bot_signal.py
# -*- coding: utf-8 -*-

import asyncio
import logging
import yfinance as yf
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

# ⚠️ ВСТАВЛЕНИЙ ТОКЕН (НЕБЕЗПЕЧНИЙ — ЗАМІНИ ПІСЛЯ ТЕСТУВАННЯ)
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"

SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "EURJPY=X", "GBPJPY=X",
    "AUDUSD=X", "USDCAD=X", "USDCHF=X", "EURGBP=X", "AUDJPY=X",
    "EURCAD=X", "NZDUSD=X", "GBPCAD=X", "USDNOK=X", "USDSEK=X",
    "USDTRY=X", "EURTRY=X", "USDRUB=X", "EURRUB=X"
]

INTERVAL = "5m"
subscribers = set()

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    subscribers.add(chat)
    await context.bot.send_message(chat_id=chat, text="✅ Ви підписались на сигнали.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    subscribers.discard(chat)
    await context.bot.send_message(chat_id=chat, text="❌ Ви відписались від сигналів.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="""
🛠 Команди:
/start – увімкнути сигнали
/stop – вимкнути сигнали
/help – довідка
""")

async def analyze(symbol):
    data = yf.download(tickers=symbol, period="1d", interval=INTERVAL)
    if data.empty:
        return None
    close = data["Close"]
    ema = close.ewm(span=14).mean().iloc[-1]
    rsi_delta = close.diff().dropna()
    up = rsi_delta.clip(lower=0).mean()
    down = -rsi_delta.clip(upper=0).mean()
    rsi = 100 - 100 / (1 + up / down) if down != 0 else None
    last = close.iloc[-1]
    signal = "Купити" if last > ema else "Продати"
    return symbol.replace("=X", ""), signal, round(last, 5), round(ema, 5), round(rsi, 2) if rsi else None

async def send_signals(bot: Bot):
    while True:
        if not subscribers:
            await asyncio.sleep(60)
            continue
        for sym in SYMBOLS:
            res = await analyze(sym)
            if res:
                pair, sig, last, ema, rsi = res
                msg = f"📉 <b>{pair}</b>\nСигнал: {sig}\nЦіна: {last}\nEMA14: {ema}"
                if rsi:
                    msg += f"\nRSI: {rsi}"
                for chat in subscribers:
                    try:
                        await bot.send_message(chat, msg, parse_mode="HTML")
                    except Exception as e:
                        logging.warning(f"Не надіслано {pair} → {e}")
            await asyncio.sleep(1)
        await asyncio.sleep(300)

async def main():
    nest_asyncio.apply()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_cmd))

    asyncio.create_task(send_signals(app.bot))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
