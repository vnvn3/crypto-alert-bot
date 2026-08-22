import requests
import time
import os
import html
import concurrent.futures

PAIRS = [
    # --- ارزهای اصلی ---
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "TRXUSDT", "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "JUPUSDT", "NEIROUSDT", "ENAUSDT", "PEOPLEUSDT",
    
    # --- آلتکوین‌های پرنوسان و ترند ---
    "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "CHZUSDT", "XLMUSDT", "ALGOUSDT", "EOSUSDT", "NEOUSDT",
    "DASHUSDT", "ZECUSDT", "XECUSDT", "ETCUSDT", "GRTUSDT", "SUSHIUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT", "YFIUSDT",
    "1INCHUSDT", "BALUSDT", "LDOUSDT", "DYDXUSDT", "GMXUSDT", "RUNEUSDT", "AVAILUSDT", "ALTUSDT", "XAIUSDT", "BLURUSDT",
    "APEUSDT", "GMTUSDT", "JTOUSDT", "PYTHUSDT", "DYMUSDT", "PIXELUSDT", "MANTAUSDT", "STRKUSDT", "MNTUSDT", "ORDIUSDT",
    "TIAUSDT", "1000SHIBUSDT", "1000PEPEUSDT", "1000XECUSDT", "1000LUNCUSDT", "LUNAUSDT", "ASTRUSDT", "FLOWUSDT", "XTZUSDT", "KAVAUSDT",
    "ROSEUSDT", "RNDRUSDT", "OCEANUSDT", "AGIXUSDT", "FILUSDT", "ARUSDT", "MINAUSDT", "IMXUSDT", "CFXUSDT", "STXUSDT",
    "KASUSDT", "TAOUSDT", "MEMEUSDT", "TURBOUSDT", "BOMEUSDT", "WUSDT", "ZKUSDT", "ETHFIUSDT", "EIGENUSDT", "TONUSDT",
    "NOTUSDT", "BANANAUSDT", "1000SATSUSDT", "OMNIUSDT", "REZUSDT", "LISTAUSDT", "ZROUSDT", "1000RATSUSDT", "1000CATSUSDT", "SCRUSDT"
]

# --- تابع ارسال به تلگرام ---
def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    
    if not token or not chat_id:
        raise Exception("توکن تلگرام یا CHAT_ID تنظیم نشده است!")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()

# --- تابع بررسی الگوی FVG برای یک ارز ---
def check_fvg_pattern(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=4"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('retCode') != 0:
            return "error", 0, 0, 0

        klines = data['result']['list']
        if len(klines) < 4:
            return None, 0, 0, 0

        # بای‌بیت کندل‌ها را از جدید به قدیم می‌فرستد.
        # ایندکس 0: کندل در حال تشکیل (حذف می‌شود)
        # ایندکس 1: کندل بسته شده سوم (c3)
        # ایندکس 2: کندل بسته شده دوم (c2)
        # ایندکس 3: کندل بسته شده اول (c1)
        
        c1_h, c1_l = float(klines[3][2]), float(klines[3][3])
        c3_h, c3_l = float(klines[1][2]), float(klines[1][3])

        MIN_GAP_PERCENT = 0.01

        # بررسی FVG صعودی
        if c3_l > c1_h:
            gap_top = c3_l
            gap_bottom = c1_h
            gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
            if gap_size_percent >= MIN_GAP_PERCENT:
                return "bullish", gap_top, gap_bottom, gap_size_percent

        # بررسی FVG نزولی
        if c3_h < c1_l:
            gap_top = c1_l
            gap_bottom = c3_h
            gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
            if gap_size_percent >= MIN_GAP_PERCENT:
                return "bearish", gap_top, gap_bottom, gap_size_percent

        return None, 0, 0, 0

    except Exception as e:
        return "error", 0, 0, 0

# --- تابعی که برای هر ارز در Thread جدا اجرا می‌شود ---
def process_pair(pair):
    symbol_clean = pair.replace("USDT", "")
    safe_symbol = html.escape(symbol_clean)
    
    pattern_type, gap_top, gap_bottom, gap_size = check_fvg_pattern(pair)
    
    alert_message = None
    
    if pattern_type == "bullish":
        alert_message = (
            f"🟢 <b>شناسایی FVG صعودی (Bullish)</b>\n"
            f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
            f"🏢 صرافی: Bybit\n"
            f"⏱ تایم فریم: 5 دقیقه\n"
            f"📐 اندازه گپ: <code>{gap_size:.3f}%</code>\n\n"
            f"🎯 <b>محدوده گپ:</b>\n"
            f"بالا: <code>{gap_top}</code>\n"
            f"پایین: <code>{gap_bottom}</code>"
        )
    elif pattern_type == "bearish":
        alert_message = (
            f"🔴 <b>شناسایی FVG نزولی (Bearish)</b>\n"
            f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
            f"🏢 صرافی: Bybit\n"
            f"⏱ تایم فریم: 5 دقیقه\n"
            f"📐 اندازه گپ: <code>{gap_size:.3f}%</code>\n\n"
            f"🎯 <b>محدوده گپ:</b>\n"
            f"بالا: <code>{gap_top}</code>\n"
            f"پایین: <code>{gap_bottom}</code>"
        )
        
    return alert_message

# --- تابع اصلی ---
def check_and_send_alerts():
    print(f"شروع اسکن الگوی FVG روی {len(PAIRS)} ارز به صورت همزمان...")
    alerts_sent = 0
    
    # استفاده از Threading برای بررسی همزمان تمام ارزها (سرعت بسیار بالا)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_pair, PAIRS))
        
    # ارسال پیام‌های پیدا شده
    for msg in results:
        if msg:
            try:
                send_telegram_message(msg)
                alerts_sent += 1
                print("✅ سیگنال ارسال شد.")
                time.sleep(0.5)  # مکث کوتاه برای جلوگیری از محدودیت تلگرام
            except Exception as e:
                print(f"❌ خطای تلگرام: {e}")

    if alerts_sent == 0:
        print("پایان اسکن: هیچ الگوی FVG استانداردی در کندل اخیر یافت نشد.")
    else:
        print(f"پایان اسکن: مجموعاً {alerts_sent} الگوی FVG ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
