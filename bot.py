import telebot
import requests
from pytz import timezone
from datetime import datetime
import os

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") 

bot = telebot.TeleBot(BOT_TOKEN)

# لیست سیاه استیبل کوین‌ها و توکن‌های بدون نوسان (برای حذف از لیست 60 تایی)
STABLECOINS = [
    'tether', 'usd-coin', 'dai', 'binance-usd', 'staked-ether', 
    'true-usd', 'frax', 'first-digital-usd', 'ethena-usde', 'paypal-usd',
    'magic-internet-money', 'usdd', 'gemini-dollar', 'fei-usd', 'terrausd'
]

def get_top_coins_data(limit=60):
    """دریافت داینامیک 60 ارز اول مارکت"""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    # ما 75 تا درخواست می‌کنیم تا بعد از حذف استیبل‌کوین‌ها، دقیقاً 60 تا باقی بماند
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': limit + 15,
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '24h'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        raw_data = response.json()
        
        valid_coins = []
        for coin in raw_data:
            # اگر ارز در لیست استیبل‌کوین‌ها نبود، اضافه کن
            if coin['id'] not in STABLECOINS:
                valid_coins.append({
                    'name': coin['name'],
                    'symbol': coin['symbol'].upper(), # مثلاً BNB یا BTC
                    'change': coin.get('price_change_percentage_24h_in_currency')
                })
                
            # وقتی به 60 ارز رسیدیم، دیگر حلقه را ادامه نده
            if len(valid_coins) >= limit:
                break
                
        return valid_coins
        
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return None

def main():
    # 1. بررسی ساعت به وقت تهران
    tehran_tz = timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    current_hour = now_tehran.hour
    
    if not (9 <= current_hour < 22):
        print("خارج از ساعات کاری (9 تا 22). اجرا لغو شد.")
        return

    # 2. دریافت لیست 60 ارز برتر
    coins_data = get_top_coins_data(limit=60)
    if not coins_data:
        return

    # 3. بررسی رشد و ارسال آلارم
    for coin in coins_data:
        change = coin['change']
        
        # اگر رشد 3 درصد یا بیشتر بود
        if change is not None and change >= 3.0:
            # فرمت پیام: مثلا "🚀 ارز BNB، رشد 3.50 درصد"
            message = f"🚀 ارز {coin['symbol']}، رشد {change:.2f} درصد"
            try:
                bot.send_message(CHANNEL_ID, message)
                print(f"آلارم ارسال شد: {coin['symbol']}")
            except Exception as e:
                print(f"خطا در ارسال پیام: {e}")

if __name__ == "__main__":
    main()
