import telebot
import requests
from pytz import timezone
from datetime import datetime
import os
import time

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") 

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------------------------------------
# لیست جفت‌ارزهای فیوچرز مد نظر شما
# ---------------------------------------------
PAIRS = [
    # top 10 (مهم‌ترین‌ها)
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "BNBUSDT.P", "XRPUSDT.P",
    "DOGEUSDT.P", "ADAUSDT.P", "AVAXUSDT.P", "DOTUSDT.P", "LINKUSDT.P",
    # آلت‌کوین‌های با حجم بالا و لایه 1
    "SUIUSDT.P", "NEARUSDT.P", "INJUSDT.P", "HYPEUSDT.P", "FTMUSDT.P",
    "APTUSDT.P", "SEIUSDT.P", "TIAUSDT.P", "ATOMUSDT.P", "RUNEUSDT.P",
    # دفای و لایه 2
    "AAVEUSDT.P", "UNIUSDT.P", "ARBUSDT.P", "OPUSDT.P", "FILUSDT.P",
    "ONDOUSDT.P", "POLUSDT.P", "IMXUSDT.P", "ENASUSDT.P", "RENDERUSDT.P",
    # میم‌کوین‌ها و توکن‌های محبوب اخیر
    "PEPEUSDT.P", "WIFUSDT.P", "BONKUSDT.P", "SHIBUSDT.P", "FLOKIUSDT.P",
    "PYTHUSDT.P", "JUPUSDT.P", "WUSDT.P", "ZROUSDT.P", "IOUSDT.P",
    # کلاسیک‌ها و مابقی بازار
    "LTCUSDT.P", "BCHUSDT.P", "TRXUSDT.P", "ETCUSDT.P", "XLMUSDT.P",
    "ALGOUSDT.P", "SNXUSDT.P", "ZECUSDT.P", "ICPUSDT.P", "KASUSDT.P",
    "ORDIUSDT.P", "1000SATSUSDT.P", "WLDUSDT.P", "LDOUSDT.P", "MKRUSDT.P",
    "STXUSDT.P", "CRVUSDT.P", "SANDUSDT.P", "MANAUSDT.P", "GRTUSDT.P"
]

# ---------------------------------------------
# تابع محاسبه RSI با پایتون خالص (بدون نیاز به پانداس)
# ---------------------------------------------
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    
    # محاسبه تغییرات قیمت
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    
    # محاسبه میانگین سود و ضرر اولیه
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # اعمال روش Smoothing (وانیلدر) برای بقیه دیتا
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
    return rsi

# ---------------------------------------------
# تابع دریافت دیتای کندل برای RSI
# ---------------------------------------------
def get_rsi_from_binance(symbol):
    # دریافت ۵۰ کندل ۱۵ دقیقه‌ای برای محاسبه دقیق RSI 14
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=50"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        klines = response.json()
        
        # استخراج قیمت‌های بسته شدن (Close Prices)
        closes = [float(k[4]) for k in klines]
        rsi_value = calculate_rsi(closes)
        return rsi_value
    except Exception as e:
        print(f"خطا در دریافت RSI برای {symbol}: {e}")
        return None

def check_binance_futures_prices():
    """بررسی قیمت‌ها و RSI از API فیوچرز بایننس"""
    for pair in PAIRS:
        # حذف کردن .P برای ارسال به سرور بایننس
        symbol_for_api = pair.replace(".P", "")
        
        # آدرس API فیوچرز بایننس (تغییرات ۲۴ ساعته)
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol_for_api}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            change = float(data.get('priceChangePercent', 0.0))
            
            # شرط تغییرات ۳+ یا 3-
            if change >= 3.0 or change <= -3.0:
                
                # دریافت RSI فقط برای ارزهایی که شرط را دارند (جلوگیری از اسپم API)
                rsi = get_rsi_from_binance(symbol_for_api)
                time.sleep(0.1) # مکث کوتاه برای محترمانه بودن با سرور بایننس
                
                # تشخیص وضعیت RSI
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
                
                # پاک کردن نام نماد
                symbol_clean = pair.replace(".P", "").replace("USDT", "")
                
                if change >= 3.0:
                    emoji = "🚀"
                    action_word = "رشد"
                else:
                    emoji = "📉"
                    action_word = "ریزش"
                    
                # پیام نهایی با فرمت جدید
                message = (
                    f"{emoji} <b>فیوچرز {symbol_clean}</b>\n"
                    f"📉/🚀 {action_word}: <code>{change:.2f}%</code>\n"
                    f"{rsi_emoji} وضعیت RSI: {rsi_text}"
                )
                
                try:
                    # فعالسازی HTML برای پیام
                    bot.send_message(CHANNEL_ID, message, parse_mode="HTML")
                    print(f"آلارم ارسال شد: {pair} | تغییرات: {change}% | RSI: {rsi_text}")
                except Exception as e:
                    print(f"خطا در ارسال پیام تلگرام: {e}")
                    
        except requests.exceptions.RequestException as e:
            print(f"خطا در دریافت دیتا از بایننس برای {pair}: {e}")
        except ValueError:
            print(f"دیتای نامعتبر از بایننس دریافت شد برای {pair}")

def main():
    # 1. بررسی ساعت به وقت تهران (9 تا 23)
    tehran_tz = timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    current_hour = now_tehran.hour
    
    if not (9 <= current_hour < 23):
        print("خارج از ساعات کاری (9 تا 23). اجرا لغو شد.")
        return

    # 2. شروع بررسی قیمت‌ها
    print(f"شروع بررسی لیست {len(PAIRS)} جفت‌ارز فیوچرز...")
    check_binance_futures_prices()
    print("بررسی به پایان رسید.")

if __name__ == "__main__":
    main()
