import logging
import os
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
import yfinance as yf
import matplotlib.pyplot as plt
import ta
import datetime

# Flask для пінгу
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

def analyze_signal(data):
    if len(data) < 30:
        return "Недостатньо даних для аналізу", None

    close = data['Close']
    high = data['High']
    low = data['Low']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    ema = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    macd = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)

    current_price = close.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_ema = ema.iloc[-1]
    current_upper = bb.bollinger_hband().iloc[-1]
    current_lower = bb.bollinger_lband().iloc[-1]
    macd_line = macd.macd().iloc[-1]
    macd_signal = macd.macd_signal().iloc[-1]
    stoch_k = stoch.stoch().iloc[-1]
    stoch_d = stoch.stoch_signal().iloc[-1]

    signal = "Очікуйте"

    buy_conditions = (
        current_rsi < 30 and
        current_price > current_ema and
        macd_line > macd_signal and
        stoch_k < 20 and stoch_k > stoch_d and
        current_price <= current_lower
    )
    sell_conditions = (
        current_rsi > 70 and
        current_price < current_ema and
        macd_line < macd_signal and
        stoch_k > 80 and stoch_k < stoch_d and
        current_price >= current_upper
    )

    if buy_conditions:
        signal = "💚 Купити"
    elif sell_conditions:
        signal = "❤️ Продати"

    explanation = (
        f"RSI: {current_rsi:.2f} (перепроданість <30 / перекупленість >70)\n"
        f"EMA(9): {current_ema:.5f} (тренд)\n"
        f"MACD: {macd_line:.5f} / {macd_signal:.5f} (перетин ліній)\n"
        f"Stochastic: %K={stoch_k:.2f}, %D={stoch_d:.2f} (перекупленість/перепроданість)\n"
        f"Bollinger Bands: верхня={current_upper:.5f}, нижня={current_lower:.5f}\n"
        f"Ціна: {current_price:.5f}"
    )

    return signal, explanation

def generate_plot(data, pair, tf):
    plt.figure(figsize=(10, 4))
    plt.plot(data['Close'], label='Ціна')
    bb = ta.volatility.BollingerBands(data['Close'], window=20, window_dev=2)
    plt.plot(bb.bollinger_hband(), label='Верхня BB', linestyle='--', color='green')
    plt.plot(bb.bollinger_lband(), label='Нижня BB', linestyle='--', color='red')
    plt.title(f'{pair} ({tf})')
    plt.xlabel('Час')
    plt.ylabel('Ціна')
    plt.legend()
    plt.grid()
    plt.tight_layout()
    filename = f'{pair}_{tf}.png'
    plt.savefig(filename)
    plt.close()
    return filename

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")]
                for pair in available_pairs]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть валютну пару:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("pair_"):
        pair = query.data.split("_")[1]
        user_settings[user_id] = {"pair": pair}
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")]
                    for tf in timeframes]
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Обрано пару: {pair}\nТепер оберіть таймфрейм:", reply_markup=markup)

    elif query.data.startswith("tf_"):
        tf = query.data.split("_")[1]
        pair = user_settings[user_id]["pair"]
        user_settings[user_id]["timeframe"] = tf

        await query.edit_message_text(f"📊 Отримую сигнал для {pair} ({tf})...")

        ticker = yf.Ticker(pair + "=X")
        interval = timeframes[tf]

        try:
            df = ticker.history(period="2d", interval=interval)
        except Exception as e:
            logging.error(f"Помилка завантаження даних: {e}")
            await query.edit_message_text(f"❌ Помилка при отриманні даних для {pair} ({tf}). Спробуйте пізніше.")
            return

        if df.empty or len(df) < 30:
            await query.edit_message_text(
                f"📉 Недостатньо даних для аналізу за пару {pair} з таймфреймом {tf}.\n"
                "Спробуйте інший таймфрейм або пару."
            )
            return

        signal, explanation = analyze_signal(df)
        filename = generate_plot(df, pair, tf)

        text = f"📈 Пара: {pair}\n⏱️ Таймфрейм: {tf}\n📉 Сигнал: {signal}\n\n📋 Пояснення:\n{explanation}"

        history.append({
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "pair": pair,
            "tf": tf,
            "signal": signal
        })

        await context.bot.send_photo(chat_id=user_id, photo=open(filename, "rb"), caption=text)
        os.remove(filename)

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history:
        await update.message.reply_text("Історія сигналів поки що порожня.")
    else:
        msg = "📜 Історія сигналів:\n\n"
        for h in history[-10:]:
            msg += f"{h['timestamp']} | {h['pair']} ({h['tf']}) — {h['signal']}\n"
        await update.message.reply_text(msg)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    logging.info("Бот запущено")
    app.run_polling()
