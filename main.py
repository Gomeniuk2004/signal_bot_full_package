import logging
import os
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes
)
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
import ta
from datetime import datetime, timedelta
import pytz

# Telegram токен
TOKEN = os.getenv("BOT_TOKEN", "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw")

# Flask сервер
app_web = Flask(__name__)
@app_web.route('/')
def home():
    return "Бот працює!"
def run():
    app_web.run(host='0.0.0.0', port=8080)
Thread(target=run).start()

# Логування
logging.basicConfig(level=logging.INFO)

# Налаштування
available_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
    "EURJPY", "GBPJPY", "EURGBP", "NZDUSD", "USDCAD"
]
user_settings = {}

# Аналіз сигналу
def analyze_signal(df):
    if df is None or df.empty or len(df) < 20:
        return None, "Недостатньо даних для аналізу."

    close = df['Close']
    rsi = ta.momentum.RSIIndicator(close).rsi()
    ema = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    macd = ta.trend.MACD(close)
    stoch = ta.momentum.StochasticOscillator(high=df['High'], low=df['Low'], close=close)
    bb = ta.volatility.BollingerBands(close)

    current_price = close.iloc[-1]
    indicators = {
        "RSI": rsi.iloc[-1],
        "EMA": ema.iloc[-1],
        "MACD_diff": macd.macd_diff().iloc[-1],
        "MACD_line": macd.macd().iloc[-1],
        "STOCH_K": stoch.stoch().iloc[-1],
        "STOCH_D": stoch.stoch_signal().iloc[-1],
        "BB_upper": bb.bollinger_hband().iloc[-1],
        "BB_lower": bb.bollinger_lband().iloc[-1],
        "price": current_price
    }

    # Логіка сигналу
    if indicators["RSI"] < 40 and current_price < indicators["BB_lower"]:
        return "💚 Купити", indicators
    elif indicators["RSI"] > 60 and current_price > indicators["BB_upper"]:
        return "❤️ Продати", indicators
    else:
        return None, indicators

# Побудова графіка
def generate_candle_plot(df, pair):
    df.index.name = 'Date'
    df_plot = df[['Open', 'High', 'Low', 'Close']]
    filename = f'{pair}_chart.png'
    mpf.plot(df_plot, type='candle', style='charles',
             title=f"{pair} - 5m", ylabel='Ціна',
             savefig=filename)
    return filename

# Отримати дату до якої хвилини тримати угоду
def get_target_time(minutes: int):
    kyiv = pytz.timezone('Europe/Kyiv')
    now = datetime.now(kyiv)
    target = now + timedelta(minutes=minutes)
    return target.strftime('%H:%M')

# Команди
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Обрати валютну пару", callback_data='choose_pair')],
        [InlineKeyboardButton("🎲 Випадковий сигнал", callback_data='random_signal')]
    ]
    await update.message.reply_text("Оберіть опцію:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'choose_pair':
        keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in available_pairs]
        await query.edit_message_text("Оберіть валютну пару:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data.startswith("pair_"):
        pair = query.data.split("_")[1]
        await send_signal(context, query, user_id, pair)
    elif query.data == 'random_signal':
        import random
        pair = random.choice(available_pairs)
        await send_signal(context, query, user_id, pair)

# Перевірка активності пари і надсилання сигналу
async def send_signal(context, query, user_id, pair):
    await query.edit_message_text(f"📊 Отримую сигнал для {pair} (5m)...")

    symbol = pair + "=X"
    end = datetime.utcnow()
    start = end - timedelta(minutes=60)
    df = yf.download(symbol, start=start, end=end, interval="5m", progress=False)

    if df is None or df.empty:
        await context.bot.send_message(chat_id=user_id, text=f"❌ Пара {pair} неактивна або не має свічок.")
        return

    signal, indicators = analyze_signal(df)
    if signal:
        time_to = get_target_time(5)
        text = f"📈 Пара: {pair}\n⏱️ Таймфрейм: 5m\n📉 Сигнал: {signal}\n\n" \
               f"📋 Пояснення:\n" \
               f"RSI: {indicators['RSI']:.2f}\n" \
               f"EMA(9): {indicators['EMA']:.5f}\n" \
               f"MACD: {indicators['MACD_line']:.5f} / {indicators['MACD_diff']:.5f}\n" \
               f"Stochastic: %K={indicators['STOCH_K']:.2f}, %D={indicators['STOCH_D']:.2f}\n" \
               f"Bollinger Bands: верхня={indicators['BB_upper']:.5f}, нижня={indicators['BB_lower']:.5f}\n" \
               f"Ціна: {indicators['price']:.5f}\n\n" \
               f"🕒 Угода до {time_to} (Київський час)"
        plot_path = generate_candle_plot(df, pair)
        await context.bot.send_photo(chat_id=user_id, photo=open(plot_path, 'rb'), caption=text)
        os.remove(plot_path)
    else:
        await context.bot.send_message(chat_id=user_id, text=f"📉 Сигнал відсутній для {pair} (5m).")

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    logging.info("Бот запущено")
    app.run_polling()
