import telebot

# توکن و آیدی را اینجا مستقیم بنویسید تا از انتقال درست آن‌ها مطمئن شوید
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID =os.environ.get("CHANNEL_ID") 

bot = telebot.TeleBot(BOT_TOKEN)

try:
    bot.send_message(CHANNEL_ID, "تست ارسال پیام به کانال")
    print("پیام با موفقیت ارسال شد!")
except Exception as e:
    print(f"خطا در ارسال پیام: {e}")
