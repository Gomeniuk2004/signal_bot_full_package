import os
import asyncio
import logging
from datetime import datetime, timedelta
import pytz
import yfinance as yf
import pandas as pd
import ta
import mplfinance as mpf
from io import BytesIO
from telegram import Bot
from telegram.constants import ParseMode

# Токен і чат
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = "992940966"
bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)

# Валютні пари
currency_pairs = [
    "EURAUD=X", "CHFJPY=X", "EURUSD=X", "CADJPY=X", "GBPJPY=X",
    "EURCAD=X", "AUDUSD=X", "EURCHF=X", "EURGBP=X", "EURJPY=X",
    "USDCAD=X", "AUDCAD=X", "AUDJPY=X", "USDJPY=X", "AUDCHF=X",
    "GBPUSD=X", "GBPCHF=X", "GBPCAD=X", "CADCHF=X", "GBPAUD=X", "USDCHF=X"
]

async def fetch_signal(symbol):
    try:
        df = yf.download(symbol, interval="5m", period="1d", progress=False)
        if df.empty or len(df) < 20:
            return None

        df.dropna(inplace=True)

        df["EMA9"] = ta.trend.ema_indicator(df["Close"], window=9).fillna(0)
        df["RSI"] = ta.momentum.rsi(df["Close"], window=14).fillna(0)
        df["MACD_diff"] = ta.trend.macd_diff(df["Close"]).fillna(0)
        stoch = ta.momentum.stoch(df["High"], df["Low"], df["Close"])
        df["Stoch_K"] = stoch.stoch().fillna(0)
        df["Stoch_D"] = stoch.stoch_signal().fillna(0)

        latest = df.iloc[-1]

        signal = None
        if latest["RSI"] < 35 and latest["Close"] < latest["EMA9"] and latest["MACD_diff"] < 0:
            signal = "Купити"
        elif latest["RSI"] > 65 and latest["Close"] > latest["EMA9"] and latest["MACD_diff"] > 0:
            signal = "Продати"

        if signal:
            now = datetime.now(pytz.timezone("Europe/Kyiv"))
            exit_time = now + timedelta(minutes=5)
            caption = (
                f"📊 <b>Сигнал знайдено!</b>\n\n"
                f"💱 Пара: <code>{symbol.replace('=X', '')}</code>\n"
                f"🕔 Таймфрейм: 5 хв\n"
                f"📈 Сигнал: <b>{signal}</b>\n"
                f"⏳ До: <b>{exit_time.strftime('%H:%M')}</b> (Київ)\n"
                f"📉 RSI: {latest['RSI']:.2f}, EMA9: {latest['EMA9']:.5f}, MACD: {latest['MACD_diff']:.5f}\n"
                f"🎯 Стохастик: %K={latest['Stoch_K']:.2f}, %D={latest['Stoch_D']:.2f}"
            )

            buf = BytesIO()
            mpf.plot(df[-30:], type='candle', style='charles', volume=False, mav=(9),
                     title=f"{symbol.replace('=X', '')} - 5m", savefig=buf)
            buf.seek(0)

            await bot.send_photo(chat_id=CHAT_ID, photo=buf, caption=caption, parse_mode=ParseMode.HTML)
            return True

    except Exception as e:
        logging.error(f"❌ Помилка для {symbol}: {e}")
    return False

async def main_loop():
    while True:
        for pair in currency_pairs:
            logging.info(f"🔍 Перевіряю {pair}")
            result = await fetch_signal(pair)
            if result:
                logging.info(f"✅ Сигнал знайдено для {pair}, пауза 5 хв")
                await asyncio.sleep(300)  # 5 хв пауза після сигналу
                break
            await asyncio.sleep(1)  # коротка пауза між парами
        await asyncio.sleep(30)  # невелика пауза між циклами

if __name__ == "__main__":
    asyncio.run(main_loop())
