import os
import telebot
from datetime import datetime

# دریافت توکن از گیت‌هاب
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

print("--- شروع تست ---")
print(f"توکن لود شد: {'بله' if BOT_TOKEN else 'خیر'}")
print(f"آیدی کانال: {CHANNEL_ID}")

if not BOT_TOKEN or not CHANNEL_ID:
    print("خطا: توکن یا آیدی کانال خالی است!")
else:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        now = datetime.now().strftime("%H:%M:%S")
        message = f"✅ تست موفق بود!\nساعت سرور: {now}"
        bot.send_message(CHANNEL_ID, message)
        print("پیام با موفقیت به تلگرام ارسال شد!")
    except Exception as e:
        print(f"خطای تلگرام: {e}")

print("--- پایان تست ---")
