import logging
import pytz
import datetime
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import asyncio

TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
chat_id = 992940966  # Твій чат ID

logging.basicConfig(level=logging.INFO)

# Таймфрейм фіксований
interval = "5m"
limit = 100
kyiv_tz = pytz.timezone("Europe/Kyiv")


def is_market_open(symbol):
    try:
        data = yf.Ticker(symbol).history(period="1d")
        return not data.empty
    except Exception:
        return False


async def get_signal(pair: str):
    symbol = pair.replace("/", "") + "=X"

    if not is_market_open(symbol):
        return f"❌ Пара {pair} наразі недоступна для торгівлі."

    try:
        df = yf.download(symbol, interval=interval, period="1d", progress=False)
        if df.empty or len(df) < 20:
            return f"⚠️ Недостатньо даних для {pair}."

        df.dropna(inplace=True)
        close = df['Close']
        rsi = RSIIndicator(close).rsi()
        ema = EMAIndicator(close, window=9).ema_indicator()
        macd = MACD(close).macd_diff()
        stoch = StochasticOscillator(high=df['High'], low=df['Low'], close=close)
        bb_upper = close.rolling(20).mean() + close.rolling(20).std() * 2
        bb_lower = close.rolling(20).mean() - close.rolling(20).std() * 2

        latest = -1
        signal = None
        reason = []

        # Прості фільтри сигналів:
        if rsi.iloc[latest] < 35 and stoch.stoch_signal().iloc[latest] < 30 and macd.iloc[latest] > 0:
            signal = "Купити"
            reason.append("RSI < 35, Стохастік < 30, MACD позитивний")
        elif rsi.iloc[latest] > 65 and stoch.stoch_signal().iloc[latest] > 70 and macd.iloc[latest] < 0:
            signal = "Продати"
            reason.append("RSI > 65, Стохастік > 70, MACD негативний")

        if not signal:
            return f"❌ Наразі немає чітких сигналів на {interval}."

        # Час до якого заходити (Київ)
        now_kyiv = datetime.datetime.now(kyiv_tz)
        exit_time = (now_kyiv + datetime.timedelta(minutes=5)).strftime('%H:%M')

        # Побудова графіка
        plot_file = f"{pair.replace('/', '')}_plot.png"
        mpf.plot(df[-50:], type='candle', style='charles', title=f"{pair} ({interval})",
                 ylabel='Ціна', volume=False, savefig=plot_file)

        # Повідомлення
        text = (
            f"📈 Пара: {pair}\n"
            f"⏱️ Таймфрейм: {interval}\n"
            f"{'🟢' if signal == 'Купити' else '🔴'} Сигнал: {signal}\n\n"
            f"📍 Заходити **до {exit_time}** (за Києвом)\n"
            f"📋 Причина: {reason[0]}"
        )

        return text, plot_file

    except Exception as e:
        return f"❌ Помилка аналізу {pair}: {e}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Вітаю! Надсилаю сигнал...")

    # Випадкова активна пара
    pairs = ["EUR/USD", "USD/JPY", "GBP/USD", "AUD/USD", "USD/CAD", "USD/CHF", "EUR/GBP"]
    for pair in pairs:
        result = await get_signal(pair)
        if isinstance(result, tuple):
            text, image = result
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(image), caption=text)
            os.remove(image)
            return
        else:
            logging.info(f"{pair}: {result}")

    await update.message.reply_text("⚠️ Не вдалося знайти сигнал на даний момент.")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ Бот запущено.")
    app.run_polling()
