import requests
import time
import os
import html

PAIRS = [
    # --- ارزهای اصلی ---
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT",
    "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    
    # --- آلتکوین‌های ترند فیوچرز (20 ارز جدید اضافه شده) ---
    "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT", "FETUSDT",
    "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "TRXUSDT",
    "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT",
    "WIFUSDT", "JUPUSDT", "NEIROUSDT", "ENAUSDT", "PEOPLEUSDT"
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

# --- تابع بررسی الگوی FVG ---
def check_fvg_pattern(symbol):
    try:
        # گرفتن 4 کندل برای در امان ماندن (3 کندل کامل + 1 کندل در حال تشکیل)
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=4"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('retCode') != 0:
            return "error", 0, 0, 0

        klines = data['result']['list']
        if len(klines) < 4:
            return None, 0, 0, 0

        # بای‌بیت کندل‌ها را از جدید به قدیم می‌فرستد
        # klines[0] = کندل فعلی (در حال بسته شدن)
        # klines[1] = آخرین کندل کاملا بسته شده
        # klines[2] = کندل دوم از آخر
        # klines[3] = کندل سوم از آخر
        
        # ما چک میکنیم آیا در 3 کندل اخیر (2 بسته شده + 1 فعلی) گپ شکل گرفته یا خیر
        c1_h, c1_l = float(klines[3][2]), float(klines[3][3])
        c1_o, c1_c = float(klines[3][1]), float(klines[3][4])
        
        c2_h, c2_l = float(klines[2][2]), float(klines[2][3])
        c2_o, c2_c = float(klines[2][1]), float(klines[2][4])
        
        c3_h, c3_l = float(klines[1][2]), float(klines[1][3])
        c3_o, c3_c = float(klines[1][1]), float(klines[1][4])

        # ==========================================
        # بررسی FVG صعودی (Bullish)
        # ==========================================
        # سه کندل صعودی + لوهای بالاتر + لو کندل سوم بالاتر از های کندل اول
        is_bullish_candles = (c1_c > c1_o) and (c2_c > c2_o) and (c3_c > c3_o)
        is_higher_lows = (c3_l > c2_l) and (c2_l > c1_l)
        is_gap_up = c3_l > c1_h

        if is_bullish_candles and is_higher_lows and is_gap_up:
            gap_top = c3_l
            gap_bottom = c1_h
            gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
            return "bullish", gap_top, gap_bottom, gap_size_percent

        # ==========================================
        # بررسی FVG نزولی (Bearish)
        # ==========================================
        is_bearish_candles = (c1_c < c1_o) and (c2_c < c2_o) and (c3_c < c3_o)
        is_lower_highs = (c3_h < c2_h) and (c2_h < c1_h)
        is_gap_down = c3_h < c1_l

        if is_bearish_candles and is_lower_highs and is_gap_down:
            gap_top = c1_l
            gap_bottom = c3_h
            gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
            return "bearish", gap_top, gap_bottom, gap_size_percent

        return None, 0, 0, 0

    except Exception as e:
        print(f"❌ خطا در دریافت دیتای بای‌بیت برای {symbol}: {e}")
        return "error", 0, 0, 0

# --- تابع اصلی ---
def check_and_send_alerts():
    print(f"شروع اسکن الگوی FVG روی {len(PAIRS)} ارز...")
    alerts_sent = 0
    api_errors = 0
    
    for pair in PAIRS:
        symbol = pair
        symbol_clean = pair.replace("USDT", "")
        safe_symbol = html.escape(symbol_clean)
        
        pattern_type, gap_top, gap_bottom, gap_size = check_fvg_pattern(symbol)
        
        if pattern_type == "error":
            api_errors += 1
            time.sleep(0.3)
            continue
            
        time.sleep(0.15) # سرعت اسکن را کمی بالا بردیم

        if pattern_type == "bullish":
            message = (
                f"🟢 <b>شناسایی FVG صعودی (Bullish)</b>\n"
                f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
                f"🏢 صرافی: Bybit\n"
                f"⏱ تایم فریم: 5 دقیقه\n"
                f"📐 اندازه گپ: <code>{gap_size:.3f}%</code>\n\n"
                f"🎯 <b>محدوده گپ:</b>\n"
                f"بالا: <code>{gap_top}</code>\n"
                f"پایین: <code>{gap_bottom}</code>"
            )
            try:
                send_telegram_message(message)
                alerts_sent += 1
                print(f"✅ FVG صعودی پیدا شد: {pair}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ خطای تلگرام: {e}")

        elif pattern_type == "bearish":
            message = (
                f"🔴 <b>شناسایی FVG نزولی (Bearish)</b>\n"
                f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
                f"🏢 صرافی: Bybit\n"
                f"⏱ تایم فریم: 5 دقیقه\n"
                f"📐 اندازه گپ: <code>{gap_size:.3f}%</code>\n\n"
                f"🎯 <b>محدوده گپ:</b>\n"
                f"بالا: <code>{gap_top}</code>\n"
                f"پایین: <code>{gap_bottom}</code>"
            )
            try:
                send_telegram_message(message)
                alerts_sent += 1
                print(f"✅ FVG نزولی پیدا شد: {pair}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ خطای تلگرام: {e}")

    if api_errors == len(PAIRS):
        print("🚨 هشدار: بای‌بیت درخواست‌ها را رد کرد.")
    
    if alerts_sent == 0:
        print("پایان اسکن: هیچ FVG استانداردی یافت نشد.")
    else:
        print(f"پایان اسکن: مجموعاً {alerts_sent} الگوی FVG ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
    
    try:
        send_telegram_message("🔄 اسکن FVG (تایم ۵ دقیقه - Bybit) انجام شد.\nبازار مثبت است اما الگوی دقیق ۳ کندلی FVG تشکیل نشده است.")
    except Exception as e:
        print(f"خطا در ارسال پیام ضربان قلب: {e}")
