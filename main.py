import logging
import os
import datetime
import pytz
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
import yfinance as yf
import ta
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

app_web = Flask('')

@app_web.route('/')
def home():
    return "Бот працює"

def run():
    app_web.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

TOKEN = os.getenv("BOT_TOKEN", "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw")
logging.basicConfig(level=logging.INFO)

user_settings = {}
history = []

available_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURJPY",
    "GBPJPY", "EURGBP", "NZDUSD", "USDCAD"
]
timeframes = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m"
}

def analyze_signal(df):
    if len(df) < 30:
        return None, "Недостатньо даних для аналізу."

    df['EMA'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_SIGNAL'] = macd.macd_signal()
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
    df['%K'] = stoch.stoch()
    df['%D'] = stoch.stoch_signal()
    bb = ta.volatility.BollingerBands(df['Close'], window=20)
    df['BB_UPPER'] = bb.bollinger_hband()
    df['BB_LOWER'] = bb.bollinger_lband()

    latest = df.iloc[-1]
    decision = "❓ Невизначено"

    if latest['RSI'] < 30 and latest['Close'] < latest['BB_LOWER'] and latest['MACD'] > latest['MACD_SIGNAL']:
        decision = "💚 Купити"
    elif latest['RSI'] > 70 and latest['Close'] > latest['BB_UPPER'] and latest['MACD'] < latest['MACD_SIGNAL']:
        decision = "❤️ Продати"
    else:
        return None, "📉 Немає чіткого сигналу (фільтровано)."

    tz = pytz.timezone("Europe/Kyiv")
    now = datetime.datetime.now(tz)
    target_time = now + datetime.timedelta(minutes=5)
    exit_time = target_time.strftime("%H:%M")

    explanation = (
        f"{decision}\n\n"
        f"📋 Пояснення:\n"
        f"RSI: {latest['RSI']:.2f} (перепроданість <30 / перекупленість >70)\n"
        f"EMA(9): {latest['EMA']:.5f} (тренд)\n"
        f"MACD: {latest['MACD']:.5f} / {latest['MACD_SIGNAL']:.5f} (перетин ліній)\n"
        f"Stochastic: %K={latest['%K']:.2f}, %D={latest['%D']:.2f}\n"
        f"Bollinger Bands: верхня={latest['BB_UPPER']:.5f}, нижня={latest['BB_LOWER']:.5f}\n"
        f"Ціна: {latest['Close']:.5f}\n"
        f"\n📅 Угода до: {exit_time} (за Києвом)"
    )

    return decision, explanation

def generate_candle_plot(df, pair, tf):
    df = df[-50:]
    df.index.name = 'Date'
    df.index = pd.to_datetime(df.index)
    mpf.plot(
        df,
        type='candle',
        style='yahoo',
        title=f"{pair} ({tf})",
        ylabel='Ціна',
        volume=False,
        savefig=f"{pair}_{tf}.png"
    )
    return f"{pair}_{tf}.png"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Вибрати валютну пару", callback_data="choose_pair")],
        [InlineKeyboardButton("🎲 Отримати випадковий сигнал", callback_data="random_signal")]
    ]
    await update.message.reply_text("Що бажаєте зробити?", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "choose_pair":
        keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")]
                    for pair in available_pairs]
        await query.edit_message_text("Оберіть валютну пару:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("pair_"):
        pair = query.data.split("_")[1]
        user_settings[user_id] = {"pair": pair}
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")]
                    for tf in timeframes]
        await query.edit_message_text(f"Обрано пару: {pair}. Оберіть таймфрейм:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("tf_"):
        tf = query.data.split("_")[1]
        pair = user_settings[user_id]["pair"]
        await send_signal(update, context, pair, tf, user_id)

    elif query.data == "random_signal":
        import random
        pair = random.choice(available_pairs)
        tf = random.choice(list(timeframes.keys()))
        await send_signal(update, context, pair, tf, user_id)

async def send_signal(update, context, pair, tf, user_id):
    await context.bot.send_message(chat_id=user_id, text=f"📊 Отримую сигнал для {pair} ({tf})...")
    ticker = yf.Ticker(pair + "=X")
    interval = timeframes[tf]
    df = ticker.history(period="1d", interval=interval)

    signal, explanation = analyze_signal(df)

    if not signal:
        await context.bot.send_message(chat_id=user_id, text=f"📉 {explanation}")
        return

    filename = generate_candle_plot(df, pair, tf)
    await context.bot.send_photo(chat_id=user_id, photo=open(filename, "rb"), caption=f"📈 Пара: {pair}\n⏱️ Таймфрейм: {tf}\n{explanation}")
    os.remove(filename)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    logging.info("Бот запущено")
    app.run_polling()
