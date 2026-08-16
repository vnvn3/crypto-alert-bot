import telebot
import requests
from pytz import timezone
from datetime import datetime
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") # مثلاً @your_channel_name

bot = telebot.TeleBot(BOT_TOKEN)

COINS = {
    "bitcoin": "بیت کوین",
    "ethereum": "اتریوم",
    "solana": "سولانا",
    "ripple": "ریپل",
    "dogecoin": "دوج کوین"
}

def get_crypto_prices():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        'ids': ','.join(COINS.keys()),
        'vs_currencies': 'usd',
        'include_24hr_change': 'true'
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return None

def main():
    # 1. بررسی ساعت به وقت تهران
    tehran_tz = timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    current_hour = now_tehran.hour
    
    # اگر قبل از 9 صبح یا بعد از 22 بود، کد متوقف شود
    if not (9 <= current_hour < 22):
        print("خارج از ساعات کاری (9 تا 22). اجرا لغو شد.")
        return

    # 2. دریافت قیمت‌ها
    data = get_crypto_prices()
    if not data:
        return

    # 3. بررسی و ارسال آلارم
    for coin_id, persian_name in COINS.items():
        if coin_id in data and 'usd_24h_change' in data[coin_id]:
            change = data[coin_id]['usd_24h_change']
            
            if change >= 3.0:
                message = f"🚀 ارز {persian_name}، رشد {change:.2f} درصد"
                try:
                    bot.send_message(CHANNEL_ID, message)
                    print(f"آلارم ارسال شد برای {persian_name}")
                except Exception as e:
                    print(f"خطا در ارسال پیام: {e}")

if __name__ == "__main__":
    main()