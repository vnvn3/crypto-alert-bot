import requests
import time
import os
import html

PAIRS = [
    "BTCUSDT.P", "ETHUSDT.P", "BNBUSDT.P", "SOLUSDT.P", "XRPUSDT.P",
    "DOGEUSDT.P", "ADAUSDT.P", "TRXUSDT.P", "AVAXUSDT.P", "LINKUSDT.P",
    "DOTUSDT.P", "MATICUSDT.P", "LTCUSDT.P", "BCHUSDT.P", "UNIUSDT.P",
    "ATOMUSDT.P", "ETCUSDT.P", "FILUSDT.P", "APTUSDT.P", "ARBUSDT.P",
    "OPUSDT.P", "SUIUSDT.P", "SEIUSDT.P", "INJUSDT.P", "TIAUSDT.P",
    "NEARUSDT.P", "AAVEUSDT.P", "MKRUSDT.P", "ALGOUSDT.P", "XLMUSDT.P",
    "HBARUSDT.P", "VETUSDT.P", "ICPUSDT.P", "FETUSDT.P", "RENDERUSDT.P",
    "WLDUSDT.P", "PEPEUSDT.P", "SHIBUSDT.P", "1000BONKUSDT.P", "1000FLOKIUSDT.P",
]
# --- تابع ارسال به تلگرام ---
def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    
    if not token or not chat_id:
        raise Exception("توکن تلگرام یا CHAT_ID تنظیم نشده است!")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status() # اگر ارور بود اینجا متوقف میشه
    return response.json()

# --- تابع محاسبه RSI ---
def get_rsi(symbol, period=14):
    try:
        # دریافت کندل‌های 1 ساعته برای محاسبه دقیق‌تر
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1h&limit={period + 1}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        klines = response.json()
        
        closes = [float(k[4]) for k in klines]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    except Exception as e:
        print(f"خطا در محاسبه RSI برای {symbol}: {e}")
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
            
            if change >= 7.0:
                emoji, action_word = "🚀🚀🚀", "پامپ شدید"
            elif change >= 4.0:
                emoji, action_word = "🚀🚀", "پامپ"
            elif change >= 2.0:
                emoji, action_word = "🚀", "رشد"
            elif change <= -7.0:
                emoji, action_word = "💀💀💀", "دامپ شدید"
            elif change <= -4.0:
                emoji, action_word = "💀💀", "دامپ"
            elif change <= -2.0:
                emoji, action_word = "📉", "ریزش"
            else:
                continue
                
            print(f"سیگنال پیدا شد: {pair} با تغییرات {change:.2f}%")
            rsi = get_rsi(symbol)
            time.sleep(0.2)
            
            if rsi is not None:
                if rsi >= 70:
                    rsi_text, rsi_emoji = f"اشباع خرید ({rsi:.1f})", "🔴"
                elif rsi <= 30:
                    rsi_text, rsi_emoji = f"اشباع فروش ({rsi:.1f})", "🟢"
                else:
                    rsi_text, rsi_emoji = f"خنثی ({rsi:.1f})", "⚪"
            else:
                rsi_text, rsi_emoji = "خطا در محاسبه", "⚠️"
            
            symbol_clean = pair.replace(".P", "").replace("USDT", "")
            # استفاده از html.escape برای جلوگیری از خطاهای پارس تلگرام
            safe_symbol = html.escape(symbol_clean)
            
            message = (
                f"{emoji} <b>فیوچرز {safe_symbol}</b>\n"
                f"📊 {action_word}: <code>{change:.2f}%</code>\n"
                f"{rsi_emoji} RSI: {rsi_text}"
            )
            
        except Exception as e:
            print(f"خطا در دریافت دیتای بایننس برای {pair}: {e}")
            continue

        try:
            send_telegram_message(message)
            alerts_sent += 1
            print(f"✅ پیام {pair} ارسال شد.")
            time.sleep(1) # تلگرام محدودیت ارسال دارد
        except Exception as e:
            print(f"❌ خطای تلگرام در ارسال {pair}: {e}")

    if alerts_sent == 0:
        print("پایان بررسی: هیچ ارزی شرط ۲ درصدی را نداشت.")
    else:
        print(f"پایان بررسی: مجموعاً {alerts_sent} آلارم ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
    
    try:
        send_telegram_message("🔄 اسکن انجام شد. بازار در حال حاضر آرام است و سیگنال جدیدی (بالای 2%) یافت نشد.")
    except Exception as e:
        print(f"خطا در ارسال پیام ضربان قلب! مشکل از توکن یا آیدی کانال است: {e}")
