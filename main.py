import os
import logging
import datetime
import pytz
import yfinance as yf
import pandas as pd
import ta
import mplfinance as mpf
from flask import Flask
from threading import Thread
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler

TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966
TIMEFRAME = "5m"
AVAILABLE_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "EURJPY", "GBPJPY", "EURGBP", "NZDUSD", "USDCAD"]

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

def analyze(df):
    if len(df) < 20:
        return None

    close = df['Close']
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    ema = ta.trend.EMAIndicator(close, window=9).ema_indicator().iloc[-1]
    macd_line = ta.trend.MACD(close).macd().iloc[-1]
    macd_signal = ta.trend.MACD(close).macd_signal().iloc[-1]
    stoch_k = ta.momentum.StochasticOscillator(df['High'], df['Low'], close).stoch().iloc[-1]
    stoch_d = ta.momentum.StochasticOscillator(df['High'], df['Low'], close).stoch_signal().iloc[-1]
    bb = ta.volatility.BollingerBands(close)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    price = close.iloc[-1]

    # ÐÑÐ»Ð°Ð±Ð»ÐµÐ½Ñ ÑÐ¼Ð¾Ð²Ð¸
    if rsi < 40 and price < bb_lower and price > ema:
        return "ð ÐÑÐ¿Ð¸ÑÐ¸", (rsi, ema, price, macd_line, macd_signal, stoch_k, stoch_d, bb_upper, bb_lower)
    elif rsi > 60 and price > bb_upper and price < ema:
        return "â¤ï¸ ÐÑÐ¾Ð´Ð°ÑÐ¸", (rsi, ema, price, macd_line, macd_signal, stoch_k, stoch_d, bb_upper, bb_lower)
    return None

def generate_chart(df, pair):
    df.index.name = 'Date'
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    mpf.plot(df, type='candle', style='charles', volume=False,
             title=f'{pair} ({TIMEFRAME})', ylabel='Ð¦ÑÐ½Ð°',
             savefig=f'{pair}.png')

async def start(update, context):
    await update.message.reply_text("ð Ð¨ÑÐºÐ°Ñ Ð½Ð°Ð¹ÐºÑÐ°ÑÐ¸Ð¹ ÑÐ¸Ð³Ð½Ð°Ð»...")

    for pair in AVAILABLE_PAIRS:
        try:
            ticker = yf.Ticker(pair + "=X")
            df = ticker.history(period="1d", interval=TIMEFRAME)
            result = analyze(df)
            if result:
                signal, (rsi, ema, price, macd_line, macd_signal, stoch_k, stoch_d, bb_upper, bb_lower) = result

                generate_chart(df, pair)

                now = datetime.datetime.now(pytz.timezone("Europe/Kyiv"))
                expire_minute = (now + datetime.timedelta(minutes=5)).strftime('%H:%M')

                text = f"""ð ÐÐ°ÑÐ°: {pair}
â±ï¸ Ð¢Ð°Ð¹Ð¼ÑÑÐµÐ¹Ð¼: {TIMEFRAME}
ð Ð¡Ð¸Ð³Ð½Ð°Ð»: {signal}

ð ÐÐ¾ÑÑÐ½ÐµÐ½Ð½Ñ:
RSI: {rsi:.2f}
EMA(9): {ema:.5f}
MACD: {macd_line:.5f} / {macd_signal:.5f}
Stochastic: %K={stoch_k:.2f}, %D={stoch_d:.2f}
Bollinger Bands: Ð²ÐµÑÑÐ½Ñ={bb_upper:.5f}, Ð½Ð¸Ð¶Ð½Ñ={bb_lower:.5f}
Ð¦ÑÐ½Ð°: {price:.5f}

â³ Ð£Ð³Ð¾Ð´Ð° Ð´Ð¾: {expire_minute} (Ð·Ð° ÐÐ¸ÑÐ²Ð¾Ð¼)"""

                await bot.send_photo(chat_id=CHAT_ID, photo=open(f"{pair}.png", "rb"), caption=text)
                os.remove(f"{pair}.png")
                return

        except Exception as e:
            logging.warning(f"ÐÐ¾Ð¼Ð¸Ð»ÐºÐ° Ð· Ð¿Ð°ÑÐ¾Ñ {pair}: {e}")
            continue

    await bot.send_message(chat_id=CHAT_ID, text="â ÐÐ°ÑÐ°Ð·Ñ Ð½ÐµÐ¼Ð°Ñ ÑÑÑÐºÐ¸Ñ ÑÐ¸Ð³Ð½Ð°Ð»ÑÐ² Ð½Ð° 5 ÑÐ²Ð¸Ð»Ð¸Ð½.")

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()
