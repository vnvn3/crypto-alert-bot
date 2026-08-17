import telebot
import requests
from pytz import timezone
from datetime import datetime
import os

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


def check_binance_futures_prices():
    """بررسی قیمت‌ها از API فیوچرز بایننس"""
    for pair in PAIRS:
        # حذف کردن .P برای ارسال به سرور بایننس
        symbol_for_api = pair.replace(".P", "")
        
        # آدرس API فیوچرز بایننس (fapi)
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol_for_api}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # بایننس درصد تغییرات ۲۴ ساعته را در این فیلد می‌فرستد
            change = float(data.get('priceChangePercent', 0.0))
            
            # شرط جدید: اگر رشد 3+ بود یا ریزش 3- بود
            if change >= 3.0 or change <= -3.0:
                
                # پاک کردن .P و USDT برای زیبایی پیام (مثلا میشه SOL)
                symbol_clean = pair.replace(".P", "").replace("USDT", "")
                
                # تشخیص اینکه رشد کرده یا ریزش تا ایموجی مناسب بگذاریم
                if change >= 3.0:
                    emoji = "🚀"
                    action_word = "رشد"
                else:
                    emoji = "📉"
                    action_word = "ریزش"
                    
                message = f"{emoji} فیوچرز {symbol_clean}، {action_word} {change:.2f} درصد"
                
                try:
                    bot.send_message(CHANNEL_ID, message)
                    print(f"آلارم ارسال شد: {pair} با تغییرات {change}%")
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
