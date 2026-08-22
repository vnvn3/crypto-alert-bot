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
    
    # --- آلتکوین‌های ترند فیوچرز ---
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
        # فقط 5 کندل آخر را می‌گیریم (برای اطمینان از بسته شدن کندل‌ها)
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=5&limit=5"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('retCode') != 0:
            return "error", 0, 0, 0

        klines = data['result']['list']
        if len(klines) < 4:
            return None, 0, 0, 0

        # بای‌بیت کندل‌ها را از جدید به قدیم می‌فرستد. برعکس می‌کنیم.
        klines.reverse()

        # کندل آخر (ایندکس منهای 1) در حال تشکیل است، پس حذفش می‌کنیم
        closed_klines = klines[:-1]

        # فقط 3 کندل اخیر بسته شده را می‌خواهیم (ایندکس 0, 1, 2)
        c1 = closed_klines[-3]
        c2 = closed_klines[-2]
        c3 = closed_klines[-1]

        c1_h, c1_l = float(c1[2]), float(c1[3])
        c2_h, c2_l = float(c2[2]), float(c2[3])
        c3_h, c3_l = float(c3[2]), float(c3[3])

        # حداقل اندازه گپ برای فیلتر کردن نویزها (0.01%)
        MIN_GAP_PERCENT = 0.01

        # ==========================================
        # بررسی FVG صعودی (Bullish)
        # شرط: Low کندل سوم بالاتر از High کندل اول باشد (اصلی‌ترین شرط FVG)
        # ==========================================
        if c3_l > c1_h:
            gap_top = c3_l
            gap_bottom = c1_h
            gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
            
            if gap_size_percent >= MIN_GAP_PERCENT:
                return "bullish", gap_top, gap_bottom, gap_size_percent

        # ==========================================
        # بررسی FVG نزولی (Bearish)
        # شرط: High کندل سوم پایین‌تر از Low کندل اول باشد
        # ==========================================
        if c3_h < c1_l:
            gap_top = c1_l
            gap_bottom = c3_h
            gap_size_percent = ((gap_top - gap_bottom) / gap_bottom) * 100
            
            if gap_size_percent >= MIN_GAP_PERCENT:
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
            
        time.sleep(0.15) # جلوگیری از بن شدن در بای‌بیت

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
        print("پایان اسکن: هیچ الگوی FVG استانداردی در کندل اخیر یافت نشد.")
    else:
        print(f"پایان اسکن: مجموعاً {alerts_sent} الگوی FVG ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
