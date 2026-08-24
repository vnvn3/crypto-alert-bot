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

def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    
    if not token or not chat_id:
        print("🚨 خطای بحرانی: BOT_TOKEN یا CHANNEL_ID در سکرت‌های گیت‌هاب تنظیم نشده است!")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطای تلگرام ({response.status_code}): {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطای شبکه در ارسال تلگرام: {e}")
        return False

def check_fvg_pattern(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=11"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get('retCode') != 0:
            print(f"⚠️ خطای API بای‌بیت برای {symbol}: {data.get('retMsg')}")
            return "error", 0, 0, 0, 0

        klines = data['result']['list']
        if len(klines) < 11:
            return None, 0, 0, 0, 0

        klines.reverse()
        closed_klines = klines[:-1] 
        MIN_GAP_PERCENT = 0.01

        for i in range(len(closed_klines) - 3, -1, -1):
            c1 = closed_klines[i]
            c2 = closed_klines[i+1]
            c3 = closed_klines[i+2]

            c1_o, c1_h, c1_l, c1_c = float(c1[1]), float(c1[2]), float(c1[3]), float(c1[4])
            c2_o, c2_h, c2_l, c2_c = float(c2[1]), float(c2[2]), float(c2[3]), float(c2[4])
            c3_o, c3_h, c3_l, c3_c = float(c3[1]), float(c3[2]), float(c3[3]), float(c3[4])

            # بررسی FVG صعودی
            is_bullish_candles = (c1_c > c1_o) and (c2_c > c2_o) and (c3_c > c3_o)
            is_gap_up = c3_l > c1_h

            if is_bullish_candles and is_gap_up:
                gap_top = c3_l
                gap_bottom = c1_h
                gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
                if gap_size_percent >= MIN_GAP_PERCENT:
                    candles_ago = len(closed_klines) - (i + 3)
                    return "bullish", gap_top, gap_bottom, gap_size_percent, candles_ago

            # بررسی FVG نزولی
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

    except Exception as e:
        print(f"❌ خطای ناشناخته برای {symbol}: {e}")
        return "error", 0, 0, 0, 0

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

def check_and_send_alerts():
    print(f"🔄 شروع اسکن الگوی FVG روی {len(PAIRS)} ارز...")
    alerts_sent = 0
    api_errors = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_pair, PAIRS))
        
    for msg in results:
        if msg:
            if send_telegram_message(msg):
                alerts_sent += 1
                print("✅ سیگنال با موفقیت به تلگرام ارسال شد.")
                time.sleep(0.5)
            else:
                print("❌ ارسال سیگنال به تلگرام با خطا مواجه شد!")

    print(f"📊 پایان اسکن: {alerts_sent} سیگنال ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
