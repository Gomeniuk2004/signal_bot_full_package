import os
import logging
import datetime
from threading import Thread

from flask import Flask

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
import ta

# --- Flask для пінгу (щоб Render тримав сервіс живим) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Бот працює"

def run_flask():
    app_web.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()

# --- Налаштування логів ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# --- Дані для бота ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise Exception("Відсутній BOT_TOKEN у змінних оточення")

user_settings = {}  # зберігаємо вибір користувача (pair, timeframe)
history = []  # збереження останніх сигналів

available_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURJPY",
    "GBPJPY", "EURGBP", "NZDUSD", "USDCAD"
]

timeframes = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m"
}

# --- Функції теханалізу ---

def calculate_macd(close):
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def calculate_stochastic(df, k_window=14, d_window=3):
    low_min = df['Low'].rolling(window=k_window).min()
    high_max = df['High'].rolling(window=k_window).max()
    k = 100 * ((df['Close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_window).mean()
    return k, d

def analyze_signal(df: pd.DataFrame):
    if df.shape[0] < 30:
        return "Недостатньо даних для аналізу", None

    close = df['Close']
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    ema = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    macd, macd_signal, _ = calculate_macd(close)
    stochastic_k, stochastic_d = calculate_stochastic(df)

    current_rsi = rsi.iloc[-1]
    current_ema = ema.iloc[-1]
    current_macd = macd.iloc[-1]
    current_macd_signal = macd_signal.iloc[-1]
    current_stochastic_k = stochastic_k.iloc[-1]
    current_stochastic_d = stochastic_d.iloc[-1]
    current_price = close.iloc[-1]

    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    upper_bb = bb.bollinger_hband().iloc[-1]
    lower_bb = bb.bollinger_lband().iloc[-1]

    signal = "Очікуйте"

    # Простий приклад сигналу на купівлю
    if current_rsi < 30 and current_price < lower_bb and current_price > current_ema:
        signal = "💚 Купити"
    # Простий приклад сигналу на продаж
    elif current_rsi > 70 and current_price > upper_bb and current_price < current_ema:
        signal = "❤️ Продати"

    info = {
        "RSI": current_rsi,
        "EMA": current_ema,
        "MACD": current_macd,
        "MACD_signal": current_macd_signal,
        "Stochastic_k": current_stochastic_k,
        "Stochastic_d": current_stochastic_d,
        "BB_upper": upper_bb,
        "BB_lower": lower_bb,
        "Price": current_price
    }

    return signal, info

# --- Функція побудови графіку з японськими свічками та індикаторами ---

def generate_candlestick_chart(df: pd.DataFrame, pair: str, tf: str):
    plt.rcParams.update({'figure.autolayout': True})
    mc = mpf.make_marketcolors(up='g', down='r', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc)

    # Додаткові індикатори:
    # EMA9
    ema9 = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    upper_bb = bb.bollinger_hband()
    lower_bb = bb.bollinger_lband()

    addplots = [
        mpf.make_addplot(ema9, color='blue'),
        mpf.make_addplot(upper_bb, color='green', linestyle='--'),
        mpf.make_addplot(lower_bb, color='red', linestyle='--'),
    ]

    filename = f"{pair}_{tf}_chart.png"
    mpf.plot(df,
             type='candle',
             style=s,
             addplot=addplots,
             title=f"{pair} ({tf})",
             volume=False,
             savefig=filename)

    return filename

# --- Обробники команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Отримати сигнал від бота", callback_data="mode_auto")],
        [InlineKeyboardButton("Обрати валютну пару самому", callback_data="mode_manual")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Виберіть режим роботи бота:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "mode_auto":
        # Бот вибирає випадкову пару і таймфрейм
        import random
        pair = random.choice(available_pairs)
        tf = random.choice(list(timeframes.keys()))
        user_settings[user_id] = {"pair": pair, "timeframe": tf}

        await query.edit_message_text(f"🤖 Бот вибрав пару {pair} і таймфрейм {tf}.\nОтримую сигнал...")

        await send_signal(user_id, pair, tf, context)

    elif query.data == "mode_manual":
        keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in available_pairs]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Оберіть валютну пару:", reply_markup=reply_markup)

    elif query.data.startswith("pair_"):
        pair = query.data.split("_")[1]
        user_settings[user_id] = {"pair": pair}
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")] for tf in timeframes]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Обрано пару: {pair}\nТепер оберіть таймфрейм:", reply_markup=reply_markup)

    elif query.data.startswith("tf_"):
        tf = query.data.split("_")[1]
        pair = user_settings.get(user_id, {}).get("pair")
        if not pair:
            await query.edit_message_text("Сталася помилка: пара не обрана.")
            return
        user_settings[user_id]["timeframe"] = tf

        await query.edit_message_text(f"📊 Отримую сигнал для {pair} ({tf})...")

        await send_signal(user_id, pair, tf, context)

async def send_signal(user_id, pair, tf, context):
    ticker = yf.Ticker(pair + "=X")

    now = datetime.datetime.utcnow()
    past = now - datetime.timedelta(minutes=100)  # достатньо для 5m таймфрейму

    # Завантажуємо історію з yfinance
    try:
        df = ticker.history(start=past, end=now, interval=tf)
    except Exception as e:
        await context.bot.send_message(chat_id=user_id, text=f"Помилка завантаження даних: {e}")
        return

    if df.empty or df.shape[0] < 20:
        await context.bot.send_message(chat_id=user_id,
            text=f"📉 Недостатньо даних для аналізу за пару {pair} з таймфреймом {tf}.\nСпробуйте інший таймфрейм або пару.")
        return

    signal, info = analyze_signal(df)
    filename = generate_candlestick_chart(df, pair, tf)

    explanation = (
        f"📈 Пара: {pair}\n"
        f"⏱️ Таймфрейм: {tf}\n"
        f"📉 Сигнал: {signal}\n\n"
        f"📋 Пояснення:\n"
        f"RSI: {info['RSI']:.2f} (перепроданість <30 / перекупленість >70)\n"
        f"EMA(9): {info['EMA']:.5f} (тренд)\n"
        f"MACD: {info['MACD']:.5f} / {info['MACD_signal']:.5f} (перетин ліній)\n"
        f"Stochastic: %K={info['Stochastic_k']:.2f}, %D={info['Stochastic_d']:.2f} (перекупленість/перепроданість)\n"
        f"Bollinger Bands: верхня={info['BB_upper']:.5f}, нижня={info['BB_lower']:.5f}\n"
        f"Ціна: {info['Price']:.5f}"
    )

    history.append({
        "timestamp": now.strftime("%Y-%m-%d %H:%M"),
        "pair": pair,
        "tf": tf,
        "signal": signal
    })

    await context.bot.send_photo(chat_id=user_id, photo=open(filename, "rb"), caption=explanation)
    os.remove(filename)

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history:
        await update.message.reply_text("Історія сигналів поки що порожня.")
        return

    msg = "📜 Історія сигналів:\n\n"
    for h in history[-10:]:
        msg += f"{h['timestamp']} | {h['pair']} ({h['tf']}) — {h['signal']}\n"
    await update.message.reply_text(msg)

# --- Запуск бота ---

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    logging.info("Бот запущено")
    app.run_polling()
