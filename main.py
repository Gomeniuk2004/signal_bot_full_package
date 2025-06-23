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
import mplfinance as mpf
import ta
import datetime
import pytz

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

FIXED_TIMEFRAME = "5m"

def analyze_signal(data):
    if len(data) < 20:
        return "Недостатньо даних для аналізу", None

    close = data['Close']
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    ema = ta.trend.EMAIndicator(close, window=9).ema_indicator()

    current_price = close.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_ema = ema.iloc[-1]

    if current_rsi < 50 and current_price < current_ema:
        signal = "💚 Купити"
    else:
        signal = "❤️ Продати"

    return signal, (current_rsi, current_ema, current_price)

def generate_candlestick_chart(data, pair):
    mc = mpf.make_marketcolors(up='green', down='red', inherit=True)
    s  = mpf.make_mpf_style(marketcolors=mc)
    fig, axlist = mpf.plot(data, type='candle', style=s, title=f'{pair} ({FIXED_TIMEFRAME})', returnfig=True)
    filename = f'{pair}_{FIXED_TIMEFRAME}.png'
    fig.savefig(filename)
    plt.close(fig)
    return filename

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Обрати пару", callback_data="choose_pair")],
        [InlineKeyboardButton("Отримати сигнал від бота", callback_data="random_signal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Обери опцію:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "choose_pair":
        keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in available_pairs]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Оберіть валютну пару:", reply_markup=reply_markup)

    elif query.data == "random_signal":
        import random
        pair = random.choice(available_pairs)
        await query.edit_message_text(f"🤖 Бот вибрав пару {pair} і таймфрейм {FIXED_TIMEFRAME}.\nОтримую сигнал...")
        await send_signal(context, user_id, pair)

    elif query.data.startswith("pair_"):
        pair = query.data.split("_")[1]
        user_settings[user_id] = {"pair": pair}
        await query.edit_message_text(f"Обрано пару: {pair}\nОтримую сигнал для {FIXED_TIMEFRAME}...")
        await send_signal(context, user_id, pair)

async def send_signal(context, user_id, pair):
    ticker = yf.Ticker(pair + "=X")
    interval = FIXED_TIMEFRAME

    tz = pytz.timezone('Europe/Kiev')
    now = datetime.datetime.now(tz)
    past = now - datetime.timedelta(minutes=50)

    df = ticker.history(start=past.strftime('%Y-%m-%d %H:%M:%S'), end=now.strftime('%Y-%m-%d %H:%M:%S'), interval=interval)
    if df.empty or len(df) < 20:
        await context.bot.send_message(chat_id=user_id, text=f"📉 Недостатньо даних для аналізу за пару {pair} з таймфреймом {interval}.\nСпробуйте інший час або пару.")
        return

    signal, data_points = analyze_signal(df)
    filename = generate_candlestick_chart(df, pair)

    enter_until = now + datetime.timedelta(minutes=5)
    enter_until_str = enter_until.strftime('%H:%M')

    text = f"📈 Пара: {pair}\n⏱️ Таймфрейм: {interval}\n📉 Сигнал: {signal}\n\n🕒 Заходьте в угоду до: {enter_until_str}\n\n"
    if data_points:
        rsi, ema, price = data_points
        text += (f"📋 Пояснення:\n"
                 f"RSI: {rsi:.2f} (перепроданість <30 / перекупленість >70)\n"
                 f"EMA(9): {ema:.5f} (тренд)\n"
                 f"Ціна: {price:.5f}")

    await context.bot.send_photo(chat_id=user_id, photo=open(filename, 'rb'), caption=text)
    os.remove(filename)

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history:
        await update.message.reply_text("Історія сигналів поки що порожня.")
    else:
        msg = "📜 Історія сигналів:\n\n"
        for h in history[-10:]:
            msg += f"{h['timestamp']} | {h['pair']} ({FIXED_TIMEFRAME}) — {h['signal']}\n"
        await update.message.reply_text(msg)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    logging.info("Бот запущено")
    app.run_polling()
