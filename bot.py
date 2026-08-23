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
    "1000SHIBUSDT", "1000PEPEUSDT", "1000XECUSDT", "1000LUNCUSDT", "LUNAUSDT", "ASTRUSDT", "FLOWUSDT", "XTZUSDT", "KAVAUSDT",
    "ROSEUSDT", "RNDRUSDT", "OCEANUSDT", "AGIXUSDT", "ARUSDT", "MINAUSDT", "IMXUSDT", "CFXUSDT", "STXUSDT",
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

# --- تابع بررسی الگوی FVG در 10 کندل اخیر ---
def check_fvg_pattern(symbol):
    try:
        # گرفتن 11 کندل (10 کندل بسته شده + 1 کندل در حال تشکیل)
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=11"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('retCode') != 0:
            return "error", 0, 0, 0, 0

        klines = data['result']['list']
        if len(klines) < 11:
            return None, 0, 0, 0, 0

        # بای‌بیت کندل‌ها را از جدید به قدیم می‌فرستد.
        klines.reverse()
        
        # حذف کندل در حال تشکیل (ایندکس آخر)
        closed_klines = klines[:-1] # حالا 10 کندل بسته شده داریم

        MIN_GAP_PERCENT = 0.01

        # بررسی از جدیدترین به قدیمی‌ترین (ایندکس 7 یعنی 3 کندل اخیر)
        # برای اینکه فقط جدیدترین الگو را پیدا کنیم، از آخر به اول حلقه می‌زنیم
        for i in range(len(closed_klines) - 3, -1, -1):
            c1 = closed_klines[i]
            c2 = closed_klines[i+1]
            c3 = closed_klines[i+2]

            c1_o, c1_h, c1_l, c1_c = float(c1[1]), float(c1[2]), float(c1[3]), float(c1[4])
            c2_o, c2_h, c2_l, c2_c = float(c2[1]), float(c2[2]), float(c2[3]), float(c2[4])
            c3_o, c3_h, c3_l, c3_c = float(c3[1]), float(c3[2]), float(c3[3]), float(c3[4])

            # ==========================================
            # بررسی FVG صعودی (3 کندل سبز + گپ)
            # ==========================================
            is_bullish_candles = (c1_c > c1_o) and (c2_c > c2_o) and (c3_c > c3_o)
            is_gap_up = c3_l > c1_h

            if is_bullish_candles and is_gap_up:
                gap_top = c3_l
                gap_bottom = c1_h
                gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
                if gap_size_percent >= MIN_GAP_PERCENT:
                    # محاسبه اینکه الگو چند کندل پیش تشکیل شده
                    candles_ago = len(closed_klines) - (i + 3)
                    return "bullish", gap_top, gap_bottom, gap_size_percent, candles_ago

            # ==========================================
            # بررسی FVG نزولی (3 کندل قرمز + گپ)
            # ==========================================
            is_bearish_candles = (c1_c < c1_o) and (c2_c < c2_o) and (c3_c < c3_o)
            is_gap_down = c3_h < c1_l

            if is_bearish_candles and is_gap_down:
                gap_top = c1_l
                gap_bottom = c3_h
                gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
                if gap_size_percent >= MIN_GAP_PERCENT:
                    candles_ago = len(closed_klines) - (i + 3)
                    return "bearish", gap_top, gap_bottom, gap_size_percent, candles_ago

        return None, 0, 0, 0, 0

    except Exception:
        return "error", 0, 0, 0, 0

# --- تابع پردازش همزمان ارزها ---
def process_pair(pair):
    symbol_clean = pair.replace("USDT", "")
    safe_symbol = html.escape(symbol_clean)
    
    pattern_type, gap_top, gap_bottom, gap_size, candles_ago = check_fvg_pattern(pair)
    
    alert_message = None
    time_text = "الان (کندل اخیر)" if candles_ago == 0 else f"{candles_ago} کندل پیش"
    
    if pattern_type == "bullish":
        alert_message = (
            f"🟢 <b>شناسایی FVG صعودی (Bullish)</b>\n"
            f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
            f"🏢 صرافی: Bybit | ⏱ تایم فریم: 5 دقیقه\n"
            f"⌛ زمان تشکیل الگو: <b>{time_text}</b>\n"
            f"📐 اندازه گپ: <code>{gap_size:.3f}%</code>\n\n"
            f"🎯 <b>محدوده گپ:</b>\n"
            f"بالا: <code>{gap_top}</code>\n"
            f"پایین: <code>{gap_bottom}</code>"
        )
    elif pattern_type == "bearish":
        alert_message = (
            f"🔴 <b>شناسایی FVG نزولی (Bearish)</b>\n"
            f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
            f"🏢 صرافی: Bybit | ⏱ تایم فریم: 5 دقیقه\n"
            f"⌛ زمان تشکیل الگو: <b>{time_text}</b>\n"
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
    
    # استفاده از Threading برای سرعت بسیار بالا
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_pair, PAIRS))
        
    for msg in results:
        if msg:
            try:
                send_telegram_message(msg)
                alerts_sent += 1
                print("✅ سیگنال ارسال شد.")
                time.sleep(0.5)  # جلوگیری از بن شدن تلگرام
            except Exception as e:
                print(f"❌ خطای تلگرام: {e}")

    if alerts_sent == 0:
        print("پایان اسکن: هیچ الگوی FVG استانداردی در 10 کندل اخیر یافت نشد.")
    else:
        print(f"پایان اسکن: مجموعاً {alerts_sent} الگوی FVG ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
