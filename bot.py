import requests
import time
import os
import html

# حذف پسوند .P چون بای‌بیت از BTCUSDT برای فیوچرز استفاده می‌کند
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "LINKUSDT",
    "DOTUSDT", "MATICUSDT", "LTCUSDT", "BCHUSDT", "UNIUSDT",
    "ATOMUSDT", "ETCUSDT", "FILUSDT", "APTUSDT", "ARBUSDT",
    "OPUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "NEARUSDT", "AAVEUSDT", "MKRUSDT", "ALGOUSDT", "XLMUSDT",
    "HBARUSDT", "VETUSDT", "ICPUSDT", "FETUSDT", "RENDERUSDT",
    "WLDUSDT", "PEPEUSDT", "SHIBUSDT", "1000BONKUSDT", "1000FLOKIUSDT",
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

# --- تابع بررسی الگوی FVG از بای‌بیت ---
def check_fvg_pattern(symbol):
    try:
        # آدرس API فیوچرز بای‌بیت (نسخه 5)
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=3"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # بررسی وضعیت پاسخ بای‌بیت
        if data.get('retCode') != 0:
            print(f"خطای API بای‌بیت برای {symbol}: {data.get('retMsg')}")
            return "error", 0, 0, 0

        klines = data['result']['list']
        
        if len(klines) < 3:
            return None, 0, 0, 0

        # نکته مهم: بای‌بیت کندل‌ها را از جدید به قدیم می‌فرستد، پس باید آرایه را برعکس کنیم
        klines = klines[::-1]

        # استخراج دیتا (ایندکس‌های بای‌بیت دقیقاً مثل بایننس است: 1=Open, 2=High, 3=Low, 4=Close)
        c1_h, c1_l = float(klines[0][2]), float(klines[0][3])
        c1_o, c1_c = float(klines[0][1]), float(klines[0][4])
        
        c2_h, c2_l = float(klines[1][2]), float(klines[1][3])
        c2_o, c2_c = float(klines[1][1]), float(klines[1][4])
        
        c3_h, c3_l = float(klines[2][2]), float(klines[2][3])
        c3_o, c3_c = float(klines[2][1]), float(klines[2][4])

        # ==========================================
        # بررسی FVG صعودی (Bullish)
        # ==========================================
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
    print(f"شروع اسکن الگوی FVG از Bybit روی {len(PAIRS)} ارز...")
    alerts_sent = 0
    api_errors = 0
    
    for pair in PAIRS:
        # دیگر نیازی به حذف .P نیست چون از اول نبود
        symbol = pair
        symbol_clean = pair.replace("USDT", "")
        safe_symbol = html.escape(symbol_clean)
        
        pattern_type, gap_top, gap_bottom, gap_size = check_fvg_pattern(symbol)
        
        if pattern_type == "error":
            api_errors += 1
            time.sleep(0.5)
            continue
            
        time.sleep(0.2)

        if pattern_type == "bullish":
            message = (
                f"🟢 <b>شناسایی FVG صعودی (Bullish)</b>\n"
                f"🪙 فیوچرز: <b>{safe_symbol}</b>\n"
                f"🏢 صرافی: Bybit\n"
                f"⏱ تایم فریم: 5 دقیقه\n"
                f"📐 اندازه گپ: <code>{gap_size:.3f}%</code>\n\n"
                f"🎯 <b>محدوده گپ برای رسم روی چارت:</b>\n"
                f"بالا (Top): <code>{gap_top}</code>\n"
                f"پایین (Bottom): <code>{gap_bottom}</code>"
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
                f"🎯 <b>محدوده گپ برای رسم روی چارت:</b>\n"
                f"بالا (Top): <code>{gap_top}</code>\n"
                f"پایین (Bottom): <code>{gap_bottom}</code>"
            )
            try:
                send_telegram_message(message)
                alerts_sent += 1
                print(f"✅ FVG نزولی پیدا شد: {pair}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ خطای تلگرام: {e}")

    if api_errors == len(PAIRS):
        print("🚨 هشدار: بای‌بیت هم تمام درخواست‌ها را رد کرد.")
    
    if alerts_sent == 0:
        print("پایان اسکن: هیچ FVG استانداردی در ۵ دقیقه اخیر شکل نگرفته است.")
    else:
        print(f"پایان اسکن: مجموعاً {alerts_sent} الگوی FVG ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
    
    try:
        send_telegram_message("🔄 اسکن FVG (تایم ۵ دقیقه - دیتا بای‌بیت) انجام شد. فعلاً گپ ارزش منصفانه‌ای تشکیل نشده است.")
    except Exception as e:
        print(f"خطا در ارسال پیام ضربان قلب: {e}")
