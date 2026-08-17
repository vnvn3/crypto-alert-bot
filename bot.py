import telebot
import requests
import os
import time

# --- تنظیمات از گیت‌هاب ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

# بررسی اولیه اینکه آیا توکن‌ها در گیت‌هاب تنظیم شده‌اند یا نه
if not BOT_TOKEN or not CHANNEL_ID:
    print("FATAL ERROR: BOT_TOKEN یا CHANNEL_ID در تنظیمات گیت‌هاب پیدا نشد!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# --- لیست ۶۰ جفت ارز فیوچرز ---
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

# --- تابع محاسبه RSI (بدون نیاز به کتابخانه اضافی) ---
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
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

# --- تابع گرفتن RSI از بایننس ---
def get_rsi(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=15m&limit=50"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        klines = response.json()
        closes = [float(k[4]) for k in klines]
        return calculate_rsi(closes)
    except:
        return None

# --- تابع اصلی بررسی و ارسال ---
def check_and_send_alerts():
    print(f"شروع بررسی {len(PAIRS)} ارز...")
    alerts_sent = 0
    
    for pair in PAIRS:
        symbol = pair.replace(".P", "")
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            change = float(data.get('priceChangePercent', 0.0))
            
            # شرط جدید: 2+ یا 2-
            if change >= 2.0 or change <= -2.0:
                print(f"سیگنال پیدا شد: {pair} با تغییرات {change:.2f}%")
                
                # دریافت RSI
                rsi = get_rsi(symbol)
                time.sleep(0.1) # مکث برای جلوگیری از بن شدن آی‌پی توسط بایننس
                
                # تشخیص وضعیت RSI
                if rsi is not None:
                    if rsi >= 70:
                        rsi_text, rsi_emoji = f"اشباع خرید ({rsi:.1f})", "🔴"
                    elif rsi <= 30:
                        rsi_text, rsi_emoji = f"اشباع فروش ({rsi:.1f})", "🟢"
                    else:
                        rsi_text, rsi_emoji = f"خنثی ({rsi:.1f})", "⚪"
                else:
                    rsi_text, rsi_emoji = "خطا در محاسبه", "⚠️"
                
                # تنظیمات پیام
                symbol_clean = pair.replace(".P", "").replace("USDT", "")
                emoji, action_word = ("🚀", "رشد") if change >= 2.0 else ("📉", "ریزش")
                
                message = (
                    f"{emoji} <b>فیوچرز {symbol_clean}</b>\n"
                    f"📊 {action_word}: <code>{change:.2f}%</code>\n"
                    f"{rsi_emoji} RSI: {rsi_text}"
                )
                
                # ارسال به تلگرام
                try:
                    bot.send_message(CHANNEL_ID, message, parse_mode="HTML")
                    alerts_sent += 1
                    print(f"✅ پیام {pair} به تلگرام ارسال شد.")
                except Exception as e:
                    print(f"❌ خطا در ارسال تلگرام برای {pair}: {e}")
                    
        except Exception as e:
            print(f"خطا در دریافت دیتای بایننس برای {pair}")
            
    if alerts_sent == 0:
        print("پایان بررسی: هیچ ارزی شرط 2 درصد را نداشت.")
    else:
        print(f"پایان بررسی: مجموعاً {alerts_sent} آلارم ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
