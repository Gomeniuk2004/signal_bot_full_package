import logging
import asyncio
from datetime import datetime, timedelta
import io

import yfinance as yf
import pandas as pd
import ta
import mplfinance as mpf
import matplotlib.pyplot as plt
import pytz

from telegram import Bot, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Токен і chat_id
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = YOUR_CHAT_ID  # Ціле число

# Параметри
TIMEFRAME = "5m"
TZ = pytz.timezone("Europe/Kiev")
PAIRS = [
    "EURUSD=X", "USDCHF=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X",
    "EURGBP=X", "EURJPY=X", "USDJPY=X", "AUDJPY=X", "EURCAD=X",
    "CHFJPY=X", "CADJPY=X", "GBPJPY=X", "EURCHF=X", "AUDCAD=X",
    "AUDCHF=X", "GBPCHF=X", "GBPCAD=X", "CADCHF=X", "GBPAUD=X"
]

# Налаштування логів
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO
)

bot = Bot(token=TOKEN)

# Функція для перевірки чи пара активна (має свіжі дані)
def is_pair_active(ticker: str) -> bool:
    try:
        df = yf.download(ticker, period="1d", interval=TIMEFRAME)
        if df.empty:
            return False
        # Перевірка чи остання свічка близька до поточного часу
        last_time = df.index[-1].to_pydatetime()
        now = datetime.now(TZ)
        # Дозволяємо лаг до 10 хв
        if now - last_time < timedelta(minutes=10):
            return True
        return False
    except Exception as e:
        logging.error(f"Помилка перевірки активності {ticker}: {e}")
        return False

# Функція для аналізу і видачі сигналу купити або продати
def analyze_signal(df: pd.DataFrame) -> str | None:
    # Обчислюємо індикатори
    df["EMA9"] = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
    df["EMA21"] = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
    df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    
    # Прості правила (змінюй під себе):
    # Якщо EMA9 перетинає EMA21 знизу вгору і RSI < 70 -> Купити
    # Якщо EMA9 перетинає EMA21 зверху вниз і RSI > 30 -> Продати
    
    if len(df) < 22:
        return None
    
    ema9_current = df["EMA9"].iloc[-1]
    ema9_prev = df["EMA9"].iloc[-2]
    ema21_current = df["EMA21"].iloc[-1]
    ema21_prev = df["EMA21"].iloc[-2]
    rsi_current = df["RSI"].iloc[-1]
    
    # Перетин знизу вгору
    if ema9_prev < ema21_prev and ema9_current > ema21_current and rsi_current < 70:
        return "Купити"
    # Перетин зверху вниз
    elif ema9_prev > ema21_prev and ema9_current < ema21_current and rsi_current > 30:
        return "Продати"
    
    return None

# Функція для генерації графіка з позначкою сигналу
def generate_chart(df: pd.DataFrame, signal: str, pair: str) -> io.BytesIO:
    # Підпис і колір стрілки
    color = "green" if signal == "Купити" else "red"
    arrow_text = signal
    
    apdict = mpf.make_addplot(df["EMA9"], color="blue")
    fig, axlist = mpf.plot(
        df,
        type='candle',
        style='charles',
        addplot=apdict,
        returnfig=True,
        figsize=(8, 5),
        title=f"{pair} - Сигнал: {signal}",
        datetime_format="%H:%M",
        xrotation=20
    )
    
    ax = axlist[0]
    # Стрілка на останній свічці
    last_idx = len(df) - 1
    last_close = df["Close"].iloc[-1]
    ax.annotate(
        arrow_text,
        xy=(last_idx, last_close),
        xytext=(last_idx, last_close * (1.01 if signal == "Купити" else 0.99)),
        arrowprops=dict(facecolor=color, shrink=0.1, width=2, headwidth=8),
        color=color,
        fontsize=12,
        fontweight='bold'
    )
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

async def send_signal(context: ContextTypes.DEFAULT_TYPE, pair: str, signal: str):
    now = datetime.now(TZ)
    # Формуємо час до якого входити (5 хв від поточного 5m таймфрейму)
    enter_until = now + timedelta(minutes=5)
    time_str = enter_until.strftime("%H:%M")
    
    msg = (
        f"📈 Пара: {pair.replace('=X','')}\n"
        f"⏱ Таймфрейм: 5m\n"
        f"📉 Сигнал: {signal}\n\n"
        f"⏳ Вхід до: {time_str}\n"
    )
    
    df = yf.download(pair, period="2d", interval=TIMEFRAME)
    chart_buf = generate_chart(df, signal, pair.replace('=X',''))
    
    await context.bot.send_photo(chat_id=CHAT_ID, photo=chart_buf, caption=msg)

async def find_and_send_signals(context: ContextTypes.DEFAULT_TYPE):
    while True:
        for pair in PAIRS:
            if not is_pair_active(pair):
                logging.info(f"Пара {pair} неактивна, пропускаємо.")
                continue
            df = yf.download(pair, period="2d", interval=TIMEFRAME)
            signal = analyze_signal(df)
            if signal:
                logging.info(f"Знайдено сигнал {signal} для {pair}")
                await send_signal(context, pair, signal)
                await asyncio.sleep(300)  # чекаємо 5 хв поки сигнал активний
                break  # після сигналу зупиняємо цикл щоб не спамити
        else:
            logging.info("Поки що сигналів немає, повторюємо спробу через 10 секунд...")
            await asyncio.sleep(10)

async def start(update, context):
    await update.message.reply_text("Бот запущено. Шукаємо сигнали...")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    # Запускаємо таску пошуку сигналів
    app.job_queue.run_once(lambda ctx: asyncio.create_task(find_and_send_signals(ctx)), 1)
    
    app.run_polling()

if __name__ == "__main__":
    main()
