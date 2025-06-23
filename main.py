import logging
import os
import asyncio
import datetime
import pytz
from threading import Thread

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import yfinance as yf
import pandas as pd
import ta
import mplfinance as mpf

# --- Flask для пінгу ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Бот працює"

def run():
    app_web.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# --- Налаштування ---
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

kyiv_tz = pytz.timezone("Europe/Kiev")

# --- Асинхронне завантаження даних ---
async def fetch_data_async(ticker, interval):
    # Використовуємо period="1d" - щоб було достатньо свічок
    return await asyncio.to_thread(ticker.history, period="1d", interval=interval)

# --- Аналіз сигналу ---
def analyze_signal(data):
    if data.empty or len(data) < 20:
        return None

    close = data['Close']
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    ema = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    macd = ta.trend.MACD(close)
    stoch = ta.momentum.StochasticOscillator(data['High'], data['Low'], close, window=14, smooth_window=3)
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)

    current_price = close.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_ema = ema.iloc[-1]
    current_macd = macd.macd().iloc[-1]
    current_macd_signal = macd.macd_signal().iloc[-1]
    current_stoch_k = stoch.stoch().iloc[-1]
    current_stoch_d = stoch.stoch_signal().iloc[-1]
    current_upper = bb.bollinger_hband().iloc[-1]
    current_lower = bb.bollinger_lband().iloc[-1]

    # Простий сигнал: купити або продати
    signal = None
    if current_rsi < 30 and current_price < current_lower and current_price > current_ema:
        signal = "Купити"
    elif current_rsi > 70 and current_price > current_upper and current_price < current_ema:
        signal = "Продати"

    return {
        "signal": signal,
        "rsi": current_rsi,
        "ema": current_ema,
        "macd": current_macd,
        "macd_signal": current_macd_signal,
        "stoch_k": current_stoch_k,
        "stoch_d": current_stoch_d,
        "bb_upper": current_upper,
        "bb_lower": current_lower,
        "price": current_price
    }

# --- Генерація свічкового графіка ---
def generate_candlestick_chart(data, pair, tf):
    data = data.copy()
    data.index.name = "Date"
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    filename = f"{pair}_{tf}_candlestick.png"

    mpf.plot(
        data,
        type='candle',
        style='charles',
        title=f"{pair} ({tf})",
        ylabel='Price',
        savefig=filename,
        volume=True,
        tight_layout=True
    )
    return filename

# --- Розрахунок часу до входу в угоду (5 хв) ---
def get_entry_deadline():
    now = datetime.datetime.now(kyiv_tz)
    deadline = now + datetime.timedelta(minutes=5)
    return deadline.strftime("%H:%M")

# --- Обробка команди /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Випадкова пара", callback_data="random_pair")],
        [InlineKeyboardButton("Обрати пару", callback_data="choose_pair")],
        [InlineKeyboardButton("Історія", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Виберіть опцію:", reply_markup=reply_markup)

# --- Обробка callback ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # Випадкова пара
    if query.data == "random_pair":
        import random
        pair = random.choice(available_pairs)
        user_settings[user_id] = {"pair": pair}
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")] for tf in timeframes]
        await query.edit_message_text(f"Випадкова пара: {pair}\nОберіть таймфрейм:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Вибрати пару
    if query.data == "choose_pair":
        keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in available_pairs]
        await query.edit_message_text("Оберіть валютну пару:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Історія
    if query.data == "history":
        if not history:
            await query.edit_message_text("Історія порожня.")
            return
        msg = "📜 Історія останніх сигналів:\n\n"
        for h in history[-10:]:
            msg += f"{h['timestamp']} | {h['pair']} ({h['tf']}) — {h['signal']}\n"
        await query.edit_message_text(msg)
        return

    # Обрати пару
    if query.data.startswith("pair_"):
        pair = query.data.split("_")[1]
        user_settings[user_id] = {"pair": pair}
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")] for tf in timeframes]
        await query.edit_message_text(f"Оберіть таймфрейм для {pair}:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Обрати таймфрейм
    if query.data.startswith("tf_"):
        tf = query.data.split("_")[1]
        pair = user_settings.get(user_id, {}).get("pair")
        if not pair:
            await query.edit_message_text("Помилка: спочатку оберіть валютну пару.")
            return

        user_settings[user_id]["timeframe"] = tf
        await query.edit_message_text(f"🤖 Обробляю сигнал для {pair} ({tf})...")

        ticker = yf.Ticker(pair + "=X")
        interval = timeframes[tf]

        try:
            df = await fetch_data_async(ticker, interval)

            if df.empty:
                await context.bot.send_message(chat_id=user_id, text=f"📉 Недостатньо даних для аналізу за пару {pair} з таймфреймом {tf}. Спробуйте інший таймфрейм або пару.")
                return

            signal_data = analyze_signal(df)
            if not signal_data or not signal_data["signal"]:
                await context.bot.send_message(chat_id=user_id, text=f"📉 Сигнал відсутній для {pair} ({tf}). Спробуйте інший таймфрейм або пару.")
                return

            filename = generate_candlestick_chart(df, pair, tf)

            deadline = get_entry_deadline()

            text = (
                f"📈 Пара: {pair}\n"
                f"⏱️ Таймфрейм: {tf}\n"
                f"📉 Сигнал: {signal_data['signal']}\n"
                f"⏳ Заходити в угоду до: {deadline}\n\n"
                f"📋 Пояснення:\n"
                f"RSI: {signal_data['rsi']:.2f} (перепроданість <30 / перекупленість >70)\n"
                f"EMA(9): {signal_data['ema']:.5f} (тренд)\n"
                f"MACD: {signal_data['macd']:.5f} / {signal_data['macd_signal']:.5f} (перетин ліній)\n"
                f"Stochastic: %K={signal_data['stoch_k']:.2f}, %D={signal_data['stoch_d']:.2f} (перекупленість/перепроданість)\n"
                f"Bollinger Bands: верхня={signal_data['bb_upper']:.5f}, нижня={signal_data['bb_lower']:.5f}\n"
                f"Ціна: {signal_data['price']:.5f}"
            )

            await context.bot.send_photo(chat_id=user_id, photo=open(filename, "rb"), caption=text)
            os.remove(filename)

            # Запис в історію
            now = datetime.datetime.now(kyiv_tz)
            history.append({
                "timestamp": now.strftime("%Y-%m-%d %H:%M"),
                "pair": pair,
                "tf": tf,
                "signal": signal_data['signal']
            })

        except Exception as e:
            logging.error(f"Помилка при обробці сигналу: {e}")
            await context.bot.send_message(chat_id=user_id, text="Виникла помилка при отриманні сигналу. Спробуйте пізніше.")

# --- Обробка /history ---
async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history:
        await update.message.reply_text("Історія сигналів поки що порожня.")
    else:
        msg = "📜 Історія сигналів:\n\n"
        for h in history[-10:]:
            msg += f"{h['timestamp']} | {h['pair']} ({h['tf']}) — {h['signal']}\n"
        await update.message.reply_text(msg)

# --- Запуск ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    logging.info("Бот запущено")
    app.run_polling()
