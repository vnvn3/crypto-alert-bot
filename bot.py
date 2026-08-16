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
# دقت کنید که .P در انتهای آن‌ها قرار دارد
# ---------------------------------------------
PAIRS = [
    "BTCUSDT.P", "ETHUSDT.P", "SOLUSDT.P", "BNBUSDT.P", "XRPUSDT.P",
    "DOGEUSDT.P", "ADAUSDT.P", "AVAXUSDT.P", "DOTUSDT.P", "LINKUSDT.P"
]

def check_binance_futures_prices():
    """بررسی قیمت‌ها از API فیوچرز بایننس"""
    for pair in PAIRS:
        # حذف کردن .P برای ارسال به سرور بایننس (سرور بایننس .P را نمی‌شناسد)
        symbol_for_api = pair.replace(".P", "")
        
        # آدرس API فیوچرز بایننس (fapi)
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol_for_api}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # بایننس درصد تغییرات ۲۴ ساعته را در این فیلد می‌فرستد
            change = float(data.get('priceChangePercent', 0.0))
            
            # اگر رشد ۳ درصد یا بیشتر بود
            if change >= 2.0:
                # پاک کردن .P و USDT برای زیبایی پیام (مثلا میشه BTC)
                symbol_clean = pair.replace(".P", "").replace("USDT", "")
                
                message = f"🚀 فیوچرز {symbol_clean}، رشد {change:.2f} درصد"
                try:
                    bot.send_message(CHANNEL_ID, message)
                    print(f"آلارم فیوچرز ارسال شد: {pair} با رشد {change}%")
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
