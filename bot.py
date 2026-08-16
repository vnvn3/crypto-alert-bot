import telebot
import requests
from pytz import timezone
from datetime import datetime
import os

# --- تنظیمات ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") 

bot = telebot.TeleBot(BOT_TOKEN)

# لیست سیاه استیبل کوین‌ها
STABLECOINS = [
    'tether', 'usd-coin', 'dai', 'binance-usd', 'staked-ether', 
    'true-usd', 'frax', 'first-digital-usd', 'ethena-usde', 'paypal-usd',
    'magic-internet-money', 'usdd', 'gemini-dollar', 'fei-usd', 'terrausd'
]

def get_top_coins_data(limit=60):
    url = "https://api.coingecko.com/api/v3/coins/markets"
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
            if coin['id'] not in STABLECOINS:
                valid_coins.append({
                    'name': coin['name'],
                    'symbol': coin['symbol'].upper(),
                    'change': coin.get('price_change_percentage_24h_in_currency')
                })
                
            if len(valid_coins) >= limit:
                break
                
        return valid_coins
        
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return None

def main():
    # شرط ساعت کاملاً حذف شد تا 24 ساعته تست کنید

    coins_data = get_top_coins_data(limit=60)
    if not coins_data:
        return

    for coin in coins_data:
        change = coin['change']
        
        # شرط رشد موقتاً روی 0.0 تنظیم شد تا هر ارز سبزی هم پیام بدهد (فقط برای تست)
        if change is not None and change >= 0.0:
            message = f"🚀 ارز {coin['symbol']}، رشد {change:.2f} درصد"
            try:
                bot.send_message(CHANNEL_ID, message)
                print(f"آلارم ارسال شد: {coin['symbol']}")
            except Exception as e:
                print(f"خطا در ارسال پیام: {e}")

if __name__ == "__main__":
    main()
