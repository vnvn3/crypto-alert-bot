import requests
import time

PAIRS = [
    "BTCUSDT.P",
    "ETHUSDT.P",
    "BNBUSDT.P",
    "SOLUSDT.P",
    "XRPUSDT.P",
    "DOGEUSDT.P",
    "ADAUSDT.P",
    "TRXUSDT.P",
    "AVAXUSDT.P",
    "LINKUSDT.P",
    "DOTUSDT.P",
    "MATICUSDT.P",
    "LTCUSDT.P",
    "BCHUSDT.P",
    "UNIUSDT.P",
    "ATOMUSDT.P",
    "ETCUSDT.P",
    "FILUSDT.P",
    "APTUSDT.P",
    "ARBUSDT.P",
    "OPUSDT.P",
    "SUIUSDT.P",
    "SEIUSDT.P",
    "INJUSDT.P",
    "TIAUSDT.P",
    "NEARUSDT.P",
    "AAVEUSDT.P",
    "MKRUSDT.P",
    "ALGOUSDT.P",
    "XLMUSDT.P",
    "HBARUSDT.P",
    "VETUSDT.P",
    "ICPUSDT.P",
    "FETUSDT.P",
    "RENDERUSDT.P",
    "WLDUSDT.P",
    "PEPEUSDT.P",
    "SHIBUSDT.P",
    "1000BONKUSDT.P",
    "1000FLOKIUSDT.P",
]



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
            
            # --- سطح بندی پامپ و دامپ ---
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
                
            # محاسبه RSI فقط برای ارزهای سینگنال‌دار
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
            message = (
                f"{emoji} <b>فیوچرز {symbol_clean}</b>\n"
                f"📊 {action_word}: <code>{change:.2f}%</code>\n"
                f"{rsi_emoji} RSI: {rsi_text}"
            )
            
        except Exception as e:
            print(f"خطا در دریافت دیتای بایننس برای {pair}: {e}")
            continue # اگر بایننس جواب نداد، این ارز را رد کن

        # --- ارسال به تلگرام (جداسازی شد تا ارورهای تلگرام پنهان نماند) ---
        try:
            send_telegram_message(message)
            alerts_sent += 1
            print(f"✅ پیام {pair} ارسال شد.")
            time.sleep(1)
        except Exception as e:
            print(f"❌ خطای تلگرام در ارسال {pair}: {e}")

    if alerts_sent == 0:
        print("پایان بررسی: هیچ ارزی شرط ۲ درصدی را نداشت.")
    else:
        print(f"پایان بررسی: مجموعاً {alerts_sent} آلارم ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
    
    # --- قابلیت Heartbeat (ضربان قلب) ---
    # این پیام هر بار اجرا ارسال می‌شود تا مطمئن شوید ربات زنده است
    try:
        send_telegram_message("🔄 اسکن انجام شد. بازار در حال حاضر آرام است و سیگنال جدیدی (بالای 2%) یافت نشد.")
    except Exception as e:
        print(f"خطا در ارسال پیام ضربان قلب! مشکل از توکن یا آیدی کانال است: {e}")
