# -*- coding: utf-8 -*-

import asyncio
import logging
import yfinance as yf
import nest_asyncio
import datetime

from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)

# ⚠️ BOT TOKEN (заміни після тестування!)
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"

# Валютні пари
SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "EURJPY=X", "GBPJPY=X",
    "AUDUSD=X", "USDCAD=X", "USDCHF=X", "EURGBP=X", "AUDJPY=X",
    "EURCAD=X", "NZDUSD=X", "GBPCAD=X", "USDNOK=X", "USDSEK=X",
    "USDTRY=X", "EURTRY=X", "USDRUB=X", "EURRUB=X"
]

INTERVAL = "5m"
subscribers = set()

# Логування
logging.basicConfig(level=logging.INFO)

# Меню-клавіатура
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("✅ Старт"), KeyboardButton("❌ Стоп")],
        [KeyboardButton("📈 Історія угод")]
    ],
    resize_keyboard=True
)

# Команди
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    subscribers.add(chat)
    await update.message.reply_text("✅ Ви підписались на сигнали.", reply_markup=keyboard)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
🛠 Команди:
/start – увімкнути сигнали
/stop – вимкнути сигнали
/help – довідка
Або натисніть кнопки нижче.
""", reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat = update.effective_chat.id

    if text == "✅ Старт":
        subscribers.add(chat)
        await update.message.reply_text("🔔 Сигнали увімкнено.", reply_markup=keyboard)

    elif text == "❌ Стоп":
        subscribers.discard(chat)
        await update.message.reply_text("🔕 Сигнали вимкнено.", reply_markup=keyboard)

    elif text == "📈 Історія угод":
        await update.message.reply_text("📊 Історія угод поки не реалізована.", reply_markup=keyboard)

    else:
        await update.message.reply_text("❓ Невідома дія. Скористайтесь кнопками.", reply_markup=keyboard)

# Аналіз
async def analyze(symbol):
    data = yf.download(tickers=symbol, period="1d", interval=INTERVAL)
    if data.empty:
        return None

    close = data["Close"]
    ema = close.ewm(span=14).mean().iloc[-1]
    delta = close.diff().dropna()
    up = delta.clip(lower=0).mean()
    down = -delta.clip(upper=0).mean()
    rsi = 100 - 100 / (1 + up / down) if down != 0 else None
    last = close.iloc[-1]
    signal = "Купити" if last > ema else "Продати"
    return symbol.replace("=X", ""), signal, round(last, 5), round(ema, 5), round(rsi, 2) if rsi else None

# Сигнали
async def send_signals(bot: Bot):
    while True:
        if not subscribers:
            await asyncio.sleep(60)
            continue

        for sym in SYMBOLS:
            try:
                res = await analyze(sym)
                if res:
                    pair, sig, last, ema, rsi = res
                    now = datetime.datetime.now()
                    expiry = (now + datetime.timedelta(minutes=5)).strftime("%H:%M")
                    msg = f"📉 <b>{pair}</b>\nСигнал: {sig}\nЦіна: {last}\nEMA14: {ema}"
                    if rsi:
                        msg += f"\nRSI: {rsi}"
                    msg += f"\n⏳ Угода до: <b>{expiry}</b>"

                    for chat in subscribers:
                        await bot.send_message(chat_id=chat, text=msg, parse_mode="HTML")

            except Exception as e:
                logging.warning(f"Помилка з {sym}: {e}")

            await asyncio.sleep(1)

        await asyncio.sleep(300)  # чекати 5 хв

# Запуск
async def main():
    nest_asyncio.apply()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    asyncio.create_task(send_signals(app.bot))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
