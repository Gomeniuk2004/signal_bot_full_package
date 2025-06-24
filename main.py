import logging
import asyncio
import datetime
import pytz
import yfinance as yf
import pandas as pd
import ta
import matplotlib.pyplot as plt
import mplfinance as mpf
from io import BytesIO
from telegram import Bot
from telegram.error import TelegramError

# Токен і чат айді
TOKEN = "8091244631:AAHZRqn2bY3Ow2zH2WNk0J92mar6D0MgfLw"
CHAT_ID = 992940966

# Налаштування логів
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Таймфрейм 5 хв
TIMEFRAME = '5m'

# Параметри пар, які аналізуємо (треба у форматі Yahoo Finance, тобто без "/")
PAIRS = [
    "EURAUD", "CHFJPY", "EURUSD", "CADJPY", "GBPJPY", "EURCAD", "AUDUSD", "EURCHF",
    "EURGBP", "EURJPY", "USDCAD", "AUDCAD", "AUDJPY", "USDJPY", "AUDCHF", "GBPUSD",
    "GBPCHF", "GBPCAD", "CADCHF", "GBPAUD", "USDCHF"
]

# Функція для перевірки чи пара активна (є дані на Yahoo Finance)
def is_pair_active(ticker: str) -> bool:
    try:
        data = yf.Ticker(ticker + "=X").history(period="1d", interval=TIMEFRAME)
        return not data.empty
    except Exception as e:
        logger.error(f"Помилка при перевірці пари {ticker}: {e}")
        return False

# Функція для отримання свіжих даних і сигналів
def get_signal(ticker: str):
    try:
        df = yf.Ticker(ticker + "=X").history(period="1d", interval=TIMEFRAME)
        if df.empty or len(df) < 20:
            return None, None

        # Обчислення індикаторів
        df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()
        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()

        # Аналіз останнього бару
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Простий сигнал: купити, якщо MACD перетинає сигнал знизу вверх
        if (prev['MACD'] < prev['MACD_signal']) and (last['MACD'] > last['MACD_signal']):
            return "Купити", df
        # Продати, якщо MACD перетинає сигнал зверху вниз
        elif (prev['MACD'] > prev['MACD_signal']) and (last['MACD'] < last['MACD_signal']):
            return "Продати", df
        else:
            return None, df
    except Exception as e:
        logger.error(f"Помилка при отриманні сигналу для {ticker}: {e}")
        return None, None

# Функція створення графіку і повернення у байтах
def plot_chart(df, ticker, signal):
    try:
        # Додатково можна стилізувати
        apds = [mpf.make_addplot(df['EMA9'], color='blue'),
                mpf.make_addplot(df['RSI'], panel=1, color='orange')]
        fig, axlist = mpf.plot(df, type='candle', addplot=apds,
                               title=f"{ticker} - Сигнал: {signal}",
                               style='yahoo', returnfig=True,
                               figsize=(8, 6))
        buf = BytesIO()
        fig.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.error(f"Помилка при побудові графіку: {e}")
        return None

async def main():
    bot = Bot(token=TOKEN)

    while True:
        found_signal = False
        for pair in PAIRS:
            if not is_pair_active(pair):
                continue

            signal, df = get_signal(pair)
            if signal:
                chart = plot_chart(df, pair, signal)
                now = datetime.datetime.now(pytz.timezone("Europe/Kiev"))
                text = f"📈 Пара: {pair}\n⏰ Час: {now.strftime('%Y-%m-%d %H:%M:%S')}\n📊 Сигнал: {signal}"
                try:
                    if chart:
                        await bot.send_photo(chat_id=CHAT_ID, photo=chart, caption=text)
                    else:
                        await bot.send_message(chat_id=CHAT_ID, text=text)
                except TelegramError as e:
                    logger.error(f"Помилка надсилання повідомлення: {e}")
                found_signal = True
                break  # Надіслали сигнал — можна чекати наступного циклу

        if not found_signal:
            logger.info("Не знайдено сигналів. Чекаємо 10 секунд...")
            await asyncio.sleep(10)
        else:
            logger.info("Сигнал надіслано. Чекаємо 5 хвилин...")
            await asyncio.sleep(300)  # Чекаємо 5 хвилин перед наступним пошуком

if __name__ == "__main__":
    asyncio.run(main())
