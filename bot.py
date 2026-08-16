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
# لیست جفت‌ارزهای مد نظر شما در بایننس
# می‌توانید به هر تعداد که خواستید اضافه کنید
# ---------------------------------------------
PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "SHIBUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT"
]

def check_binance_prices():
    """بررسی قیمت‌ها از API بایننس"""
    for pair in PAIRS:
        # لینکی که خودتان دادید (اسپات بایننس)
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # بایننس درصد تغییرات ۲۴ ساعته را در این فیلد می‌فرستد
            change = float(data.get('priceChangePercent', 0.0))
            
            # اگر رشد ۳ درصد یا بیشتر بود
            if change >= 3.0:
                # حذف کردن 'USDT' از انتهای نام برای زیبایی پیام (اختیاری)
                symbol_clean = pair.replace("USDT", "")
                
                message = f"🚀 ارز {symbol_clean}، رشد {change:.2f} درصد"
                try:
                    bot.send_message(CHANNEL_ID, message)
                    print(f"آلارم ارسال شد: {pair} با رشد {change}%")
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
    print(f"شروع بررسی لیست {len(PAIRS)} جفت‌ارز...")
    check_binance_prices()
    print("بررسی به پایان رسید.")

if __name__ == "__main__":
    main()
