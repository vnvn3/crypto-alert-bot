import requests
import os
import time

# --- تنظیمات از گیت‌هاب ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("FATAL ERROR: BOT_TOKEN یا CHANNEL_ID در تنظیمات گیت‌هاب پیدا نشد!")
    exit(1)

# --- لیست ۸۰ جفت ارز فیوچرز (بهینه شده) ---
PAIRS = [
    # ترندهای برتر
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "BNBUSDT.P", "XRPUSDT.P",
    "DOGEUSDT.P", "ADAUSDT.P", "AVAXUSDT.P", "DOTUSDT.P", "LINKUSDT.P",
    "SUIUSDT.P", "NEARUSDT.P", "INJUSDT.P", "HYPEUSDT.P", "FTMUSDT.P",
    "APTUSDT.P", "SEIUSDT.P", "TIAUSDT.P", "ATOMUSDT.P", "RUNEUSDT.P",
    
    # دیفای و لایه دو
    "AAVEUSDT.P", "UNIUSDT.P", "ARBUSDT.P", "OPUSDT.P", "FILUSDT.P",
    "ONDOUSDT.P", "POLUSDT.P", "IMXUSDT.P", "ENAUSDT.P", "RENDERUSDT.P",
    "PEPEUSDT.P", "WIFUSDT.P", "BONKUSDT.P", "SHIBUSDT.P", "FLOKIUSDT.P",
    "PYTHUSDT.P", "JUPUSDT.P", "WUSDT.P", "ZROUSDT.P", "IOUSDT.P",
    
    # پایه و قدیمی‌تر
    "LTCUSDT.P", "BCHUSDT.P", "TRXUSDT.P", "ETCUSDT.P", "XLMUSDT.P",
    "ALGOUSDT.P", "SNXUSDT.P", "ZECUSDT.P", "ICPUSDT.P", "KASUSDT.P",
    "ORDIUSDT.P", "1000SATSUSDT.P", "WLDUSDT.P", "LDOUSDT.P", "MKRUSDT.P",
    "STXUSDT.P", "CRVUSDT.P", "SANDUSDT.P", "MANAUSDT.P", "GRTUSDT.P","THETAUSDT.P"
    
    # توکن‌های جدید و پرنوسان (شامل تسلا)
    "TSLAUSDT.P", "NOTUSDT.P", "ZKUSDT.P", "BBUSDT.P", "LISTAUSDT.P",
    "AEVOUSDT.P", "BOMEUSDT.P", "MEWUSDT.P", "POPCATUSDT.P", "NEIROUSDT.P",
    "GOATUSDT.P", "DRIFTUSDT.P", "JTOUSDT.P", "BLURUSDT.P", "PENDLEUSDT.P",
    "ETHFIUSDT.P", "WUSDT.P", "REZUSDT.P", "GRAMUSDT.P", "JUPUSDT.P","SPCXUSDT.P","SKHYUSDT.P","SNXXUSDT.P","SKHYNIXUSDT.P","SNDKUSDT.P"
    ,"MUUSDT.P","GPSUSDT.P","KORUUSDT.P","SOXLUSDT.P","ACEUSDT.P","BTWUSDT.P","ALPINEUSDT.P"
]

# حذف ارزهای تکراری در صورت وجود (برای ایمنی)
PAIRS = list(set(PAIRS))

# --- تابع محاسبه RSI ---
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0: return 100.0
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

# --- تابع گرفتن RSI از بایننس ---
def get_rsi(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=50"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        klines = response.json()
        closes = [float(k[4]) for k in klines]
        return calculate_rsi(closes)
    except Exception as e:
        print(f"خطا در دریافت RSI برای {symbol}: {e}")
        return None

# --- تابع ارسال به تلگرام ---
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            print(f"خطای تلگرام: {result}")
            raise Exception("Telegram API Error")
    except Exception as e:
        print(f"❌ خطا در ارسال پیام به تلگرام: {e}")
        raise e

# --- تابع اصلی بررسی و ارسال ---
def check_and_send_alerts():
    print(f"شروع بررسی {len(PAIRS)} ارز...")
    alerts_sent = 0
    
    for pair in PAIRS:
        symbol = pair.replace(".P", "")
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            change = float(data.get('priceChangePercent', 0.0))
            
            # --- سطح بندی پامپ و دامپ ---
            if change >= 7.0:
                emoji, action_word = "🚀🚀🚀", "پامپ شدید"
            elif change >= 4.0:
                emoji, action_word = "🚀🚀", "پامپ"
            elif change >= 2.0:
                emoji, action_word = "🚀", "رشد"
            elif change <= -7.0:
                emoji, action_word = "💀💀💀", "دامپ شدید"
            elif change <= -4.0:
                emoji, action_word = "💀💀", "دامپ"
            elif change <= -2.0:
                emoji, action_word = "📉", "ریزش"
            else:
                continue # بهینه‌سازی: اگر زیر 2 درصد بود، کلاً رد شو و زمان صرف نکن
                
            # --- فقط برای ارزهایی که شرط را داشتند RSI محاسبه می‌شود ---
            print(f"سیگنال پیدا شد: {pair} با تغییرات {change:.2f}%")
            rsi = get_rsi(symbol)
            time.sleep(0.2) # مکث کوتاه برای محدودیت درخواست‌ها
            
            if rsi is not None:
                if rsi >= 70:
                    rsi_text, rsi_emoji = f"اشباع خرید ({rsi:.1f})", "🔴"
                elif rsi <= 30:
                    rsi_text, rsi_emoji = f"اشباع فروش ({rsi:.1f})", "🟢"
                else:
                    rsi_text, rsi_emoji = f"خنثی ({rsi:.1f})", "⚪"
            else:
                rsi_text, rsi_emoji = "خطا در محاسبه", "⚠️"
            
            symbol_clean = pair.replace(".P", "").replace("USDT", "")
            message = (
                f"{emoji} <b>فیوچرز {symbol_clean}</b>\n"
                f"📊 {action_word}: <code>{change:.2f}%</code>\n"
                f"{rsi_emoji} RSI: {rsi_text}"
            )
            
            send_telegram_message(message)
            alerts_sent += 1
            print(f"✅ پیام {pair} ارسال شد.")
            time.sleep(1) # مکث بین ارسال پیام‌ها به تلگرام
                    
        except Exception as e:
            # اگر ارزی مثل TSLA در فیوچرز بایننس موجود نباشد یا خطایی بدهد، ربات متوقف نمی‌شود
            print(f"خطا در دریافت دیتای بایننس برای {pair}: {e}")
            
    if alerts_sent == 0:
        print("پایان بررسی: هیچ ارزی شرط ۲ درصدی را نداشت (تیک سبز طبیعی است).")
    else:
        print(f"پایان بررسی: مجموعاً {alerts_sent} آلارم ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
