import telebot
import requests
from pytz import timezone
from datetime import datetime
import os
import time

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") 

# --- دیباگ ۱: چک کردن خوانده شدن توکن‌ها ---
print(f"DEBUG: BOT_TOKEN loaded: {'Yes' if BOT_TOKEN else 'NO! TOKEN IS EMPTY'}")
print(f"DEBUG: CHANNEL_ID loaded: {CHANNEL_ID}")

if not BOT_TOKEN or not CHANNEL_ID:
    print("FATAL ERROR: توکن یا آیدی کانال پیدا نشد! اجرا متوقف شد.")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

PAIRS = [
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "BNBUSDT.P", "XRPUSDT.P",
    "DOGEUSDT.P", "ADAUSDT.P", "AVAXUSDT.P", "DOTUSDT.P", "LINKUSDT.P",
    "SUIUSDT.P", "NEARUSDT.P", "INJUSDT.P", "HYPEUSDT.P", "FTMUSDT.P",
    "APTUSDT.P", "SEIUSDT.P", "TIAUSDT.P", "ATOMUSDT.P", "RUNEUSDT.P",
    "AAVEUSDT.P", "UNIUSDT.P", "ARBUSDT.P", "OPUSDT.P", "FILUSDT.P",
    "ONDOUSDT.P", "POLUSDT.P", "IMXUSDT.P", "ENASUSDT.P", "RENDERUSDT.P",
    "PEPEUSDT.P", "WIFUSDT.P", "BONKUSDT.P", "SHIBUSDT.P", "FLOKIUSDT.P",
    "PYTHUSDT.P", "JUPUSDT.P", "WUSDT.P", "ZROUSDT.P", "IOUSDT.P",
    "LTCUSDT.P", "BCHUSDT.P", "TRXUSDT.P", "ETCUSDT.P", "XLMUSDT.P",
    "ALGOUSDT.P", "SNXUSDT.P", "ZECUSDT.P", "ICPUSDT.P", "KASUSDT.P",
    "ORDIUSDT.P", "1000SATSUSDT.P", "WLDUSDT.P", "LDOUSDT.P", "MKRUSDT.P",
    "STXUSDT.P", "CRVUSDT.P", "SANDUSDT.P", "MANAUSDT.P", "GRTUSDT.P"
]

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1: return None
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

def get_rsi_from_binance(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=50"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        klines = response.json()
        closes = [float(k[4]) for k in klines]
        return calculate_rsi(closes)
    except Exception as e:
        return None

def check_binance_futures_prices():
    alerts_found = 0 # شمارنده تعداد آلارم‌ها
    
    for pair in PAIRS:
        symbol_for_api = pair.replace(".P", "")
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol_for_api}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            change = float(data.get('priceChangePercent', 0.0))
            
            # --- دیباگ ۲: اگر ارزی نزدیک به شرط بود چاپ کن تا بدانیم کد کار میکند ---
            if abs(change) > 2.0: 
                print(f"DEBUG: {pair} change is {change:.2f}% (نزدیک به شرط 3 درصد)")
            
            if change >= 3.0 or change <= -3.0:
                alerts_found += 1
                print(f"DEBUG: شرط برقرار شد برای {pair}! در حال دریافت RSI...")
                
                rsi = get_rsi_from_binance(symbol_for_api)
                time.sleep(0.1)
                
                rsi_text = "غیرقابل محاسبه"
                rsi_emoji = "⚠️"
                if rsi is not None:
                    if rsi >= 70:
                        rsi_text = f"اشباع خرید ({rsi:.1f})"
                        rsi_emoji = "🔴"
                    elif rsi <= 30:
                        rsi_text = f"اشباع فروش ({rsi:.1f})"
                        rsi_emoji = "🟢"
                    else:
                        rsi_text = f"خنثی ({rsi:.1f})"
                        rsi_emoji = "⚪"
                
                symbol_clean = pair.replace(".P", "").replace("USDT", "")
                
                if change >= 3.0:
                    emoji, action_word = "🚀", "رشد"
                else:
                    emoji, action_word = "📉", "ریزش"
                    
                message = (
                    f"{emoji} <b>فیوچرز {symbol_clean}</b>\n"
                    f"📉/🚀 {action_word}: <code>{change:.2f}%</code>\n"
                    f"{rsi_emoji} وضعیت RSI: {rsi_text}"
                )
                
                try:
                    bot.send_message(CHANNEL_ID, message, parse_mode="HTML")
                    print(f"✅ SUCCESS: آلارم ارسال شد برای {pair}")
                except Exception as e:
                    # --- دیباگ ۳: چاپ دقیق خطای تلگرام ---
                    print(f"❌ TELEGRAM ERROR for {pair}: {e}")
                    
        except Exception as e:
            print(f"❌ BINANCE ERROR for {pair}: {e}")
            
    # --- دیباگ ۴: آیا اصلا ارزی شرط را داشت؟ ---
    if alerts_found == 0:
        print("INFO: بررسی تمام شد. هیچ ارزی تغییرات 3 درصدی نداشت.")

def main():
    tehran_tz = timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    current_hour = now_tehran.hour
    
    # --- دیباگ ۵: چاپ ساعت دقیق سرور ---
    print(f"DEBUG: ساعت سرور (UTC): {datetime.utcnow().hour}, ساعت تهران: {current_hour}")
    
    if not (9 <= current_hour < 23):
        print("INFO: خارج از ساعات کاری (9 تا 23 به وقت تهران). اجرا لغو شد.")
        return

    print(f"INFO: شروع بررسی لیست {len(PAIRS)} جفت‌ارز فیوچرز...")
    check_binance_futures_prices()
    print("INFO: پایان اجرای برنامه.")

if __name__ == "__main__":
    main()
