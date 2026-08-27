import requests
import time
import os
import html
import concurrent.futures

PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "TRXUSDT", "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "JUPUSDT", "NEIROUSDT", "ENAUSDT", "PEOPLEUSDT",
    "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "CHZUSDT", "XLMUSDT", "ALGOUSDT", "EOSUSDT", "NEOUSDT",
    "DASHUSDT", "ZECUSDT", "XECUSDT", "ETCUSDT", "GRTUSDT", "SUSHIUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT", "YFIUSDT",
    "1INCHUSDT", "BALUSDT", "LDOUSDT", "DYDXUSDT", "GMXUSDT", "RUNEUSDT", "AVAILUSDT", "ALTUSDT", "XAIUSDT", "BLURUSDT",
    "APEUSDT", "GMTUSDT", "JTOUSDT", "PYTHUSDT", "DYMUSDT", "PIXELUSDT", "MANTAUSDT", "STRKUSDT", "MNTUSDT", "ORDIUSDT",
    "1000SHIBUSDT", "1000PEPEUSDT", "1000XECUSDT", "1000LUNCUSDT", "LUNAUSDT", "ASTRUSDT", "FLOWUSDT", "XTZUSDT", "KAVAUSDT",
    "ROSEUSDT", "RNDRUSDT", "OCEANUSDT", "AGIXUSDT", "ARUSDT", "MINAUSDT", "IMXUSDT", "CFXUSDT", "STXUSDT",
    "KASUSDT", "TAOUSDT", "MEMEUSDT", "TURBOUSDT", "BOMEUSDT", "WUSDT", "ZKUSDT", "ETHFIUSDT", "EIGENUSDT", "TONUSDT",
    "NOTUSDT", "BANANAUSDT", "1000SATSUSDT", "OMNIUSDT", "REZUSDT", "LISTAUSDT", "ZROUSDT", "1000RATSUSDT", "1000CATSUSDT", "SCRUSDT"
]

# تنظیمات RSI
RSI_PERIOD = 14
OVERBOUGHT = 70
OVERSOLD = 30

def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    
    if not token or not chat_id:
        print("🚨 خطای بحرانی: BOT_TOKEN یا CHANNEL_ID در سکرت‌های گیت‌هاب تنظیم نشده است!")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطای تلگرام: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطای شبکه: {e}")
        return False

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
        
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
            
    # میانگین اولیه
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # محاسبه میانگین نرم (Wilder's Smoothing)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_rsi_status(symbol):
    try:
        # گرفتن کندل‌های 5 دقیقه (بیش از حد نیاز برای دقت محاسبه RSI)
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=50"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get('retCode') != 0:
            return "error", 0, 0

        klines = data['result']['list']
        klines.reverse() # قدیمی به جدید
        
        # حذف کندل در حال تشکیل
        closed_klines = klines[:-1]
        
        if len(closed_klines) < 16:
            return None, 0, 0
            
        closes = [float(k[4]) for k in closed_klines]
        
        # محاسبه RSI برای کندل اخیر بسته شده
        current_rsi = calculate_rsi(closes, RSI_PERIOD)
        
        # محاسبه RSI برای یک کندل قبل
        prev_rsi = calculate_rsi(closes[:-1], RSI_PERIOD)
        
        if current_rsi is None or prev_rsi is None:
            return None, 0, 0
            
        # بررسی تلاقی به سمت پایین (ورود به اشباع فروش)
        if prev_rsi > OVERSOLD and current_rsi <= OVERSOLD:
            return "oversold", current_rsi, prev_rsi
            
        # بررسی تلاقی به سمت بالا (ورود به اشباع خرید)
        if prev_rsi < OVERBOUGHT and current_rsi >= OVERBOUGHT:
            return "overbought", current_rsi, prev_rsi
            
        return None, 0, 0

    except Exception as e:
        return "error", 0, 0

def process_pair(pair):
    symbol_clean = pair.replace("USDT", "")
    safe_symbol = html.escape(symbol_clean)
    
    status, current_rsi, prev_rsi = check_rsi_status(pair)
    
    alert_message = None
    
    if status == "oversold":
        alert_message = (
            f"🔵 <b>هشدار اشباع فروش (Oversold)</b>\n"
            f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
            f"🏢 صرافی: Bybit | ⏱ تایم فریم: 5 دقیقه\n"
            f"📉 <b>RSI:</b> از <code>{prev_rsi:.2f}</code> به <code>{current_rsi:.2f}</code> رسید\n"
            f"⚡ امکان بازگشت یا اصلاح قیمتی (Long)"
        )
    elif status == "overbought":
        alert_message = (
            f"🟠 <b>هشدار اشباع خرید (Overbought)</b>\n"
            f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
            f"🏢 صرافی: Bybit | ⏱ تایم فریم: 5 دقیقه\n"
            f"📈 <b>RSI:</b> از <code>{prev_rsi:.2f}</code> به <code>{current_rsi:.2f}</code> رسید\n"
            f"⚡ امکان بازگشت یا اصلاح قیمتی (Short)"
        )
        
    return alert_message

def check_and_send_alerts():
    print(f"🔄 شروع اسکن RSI روی {len(PAIRS)} ارز...")
    alerts_sent = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_pair, PAIRS))
        
    for msg in results:
        if msg:
            if send_telegram_message(msg):
                alerts_sent += 1
                print("✅ سیگنال ارسال شد.")
                time.sleep(0.5)

    print(f"📊 پایان اسکن: {alerts_sent} سیگنال ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
