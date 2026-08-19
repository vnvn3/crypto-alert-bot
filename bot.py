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
    response.raise_for_status()
    return response.json()

# --- تابع دریافت دیتای ۵ دقیقه، محاسبه تغییرات و RSI ---
def get_5m_data_and_rsi(symbol, period=14):
    try:
        # دریافت ۱۵ کندل ۵ دقیقه ای (14 تا برای RSI و 1 کندل فعلی برای قیمت)
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit=15"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        klines = response.json()
        
        # محاسبه تغییرات قیمت در کندل جاری (5 دقیقه اخیر)
        current_candle = klines[-1]
        open_price = float(current_candle[1])
        current_price = float(current_candle[4])
        
        # جلوگیری از تقسیم بر صفر
        change_5m = ((current_price - open_price) / open_price) * 100 if open_price != 0 else 0.0
        
        # محاسبه RSI روی همین ۵ دقیقه
        closes = [float(k[4]) for k in klines]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
        return change_5m, rsi

    except Exception as e:
        print(f"خطا در دریافت دیتای ۵ مینقه برای {symbol}: {e}")
        return None, None

# --- تابع اصلی بررسی و ارسال ---
def check_and_send_alerts():
    print(f"شروع بررسی {len(PAIRS)} ارز در تایم ۵ دقیقه...")
    alerts_sent = 0
    
    for pair in PAIRS:
        symbol = pair.replace(".P", "")
        symbol_clean = pair.replace(".P", "").replace("USDT", "")
        safe_symbol = html.escape(symbol_clean)
        
        # گرفتن دیتا با یک درخواست
        change_5m, rsi = get_5m_data_and_rsi(symbol)
        
        if change_5m is None or rsi is None:
            continue
            
        time.sleep(0.2) # احترام به لیمیت بایننس
        message_sent_for_pair = False

        # ==========================================
        # شرط اول: پامپ و دامپ در ۵ دقیقه
        # (اعداد را میتوانید بر اساس استراتژی خود تغییر دهید)
        # ==========================================
        if change_5m >= 3.0:
            emoji, action_word = "🚀🚀🚀", "پامپ شدید 5m"
        elif change_5m >= 1.5:
            emoji, action_word = "🚀🚀", "پامپ 5m"
        elif change_5m >= 0.8:
            emoji, action_word = "🚀", "رشد 5m"
        elif change_5m <= -3.0:
            emoji, action_word = "💀💀💀", "دامپ شدید 5m"
        elif change_5m <= -1.5:
            emoji, action_word = "💀💀", "دامپ 5m"
        elif change_5m <= -0.8:
            emoji, action_word = "📉", "ریزش 5m"
        else:
            emoji, action_word = None, None

        if action_word:
            # وضعیت RSI را هم در پیام پامپ نشان بدهیم
            if rsi >= 70:
                rsi_text = f"🔴 اشباع خرید ({rsi:.1f})"
            elif rsi <= 30:
                rsi_text = f"🟢 اشباع فروش ({rsi:.1f})"
            else:
                rsi_text = f"⚪ خنثی ({rsi:.1f})"

            message = (
                f"{emoji} <b>فیوچرز {safe_symbol}</b>\n"
                f"⚡ {action_word}: <code>{change_5m:.2f}%</code>\n"
                f"📊 RSI: {rsi_text}"
            )
            
            try:
                send_telegram_message(message)
                alerts_sent += 1
                print(f"✅ پامپ/دامپ {pair} ارسال شد.")
                message_sent_for_pair = True
                time.sleep(1)
            except Exception as e:
                print(f"❌ خطای تلگرام در ارسال پامپ {pair}: {e}")

        # ==========================================
        # شرط دوم: رسیدن RSI به اشباع (حتی اگر پامپ نشده بود)
        # ==========================================
        if not message_sent_for_pair:
            if rsi >= 70:
                rsi_message = (
                    f"🔴 <b>اشباع خرید RSI در 5m</b>\n"
                    f"🪙 فیوچرز {safe_symbol}\n"
                    f"📊 مقدار: <code>{rsi:.1f}</code>\n"
                    f"📉 تغییرات ۵ مینه: <code>{change_5m:.2f}%</code>"
                )
                try:
                    send_telegram_message(rsi_message)
                    alerts_sent += 1
                    print(f"✅ سیگنال اشباع خرید RSI برای {pair} ارسال شد.")
                    time.sleep(1)
                except Exception as e:
                    print(f"❌ خطای تلگرام در ارسال RSI {pair}: {e}")
                    
            elif rsi <= 30:
                rsi_message = (
                    f"🟢 <b>اشباع فروش RSI در 5m</b>\n"
                    f"🪙 فیوچرز {safe_symbol}\n"
                    f"📊 مقدار: <code>{rsi:.1f}</code>\n"
                    f"📈 تغییرات ۵ مینه: <code>{change_5m:.2f}%</code>"
                )
                try:
                    send_telegram_message(rsi_message)
                    alerts_sent += 1
                    print(f"✅ سیگنال اشباع فروش RSI برای {pair} ارسال شد.")
                    time.sleep(1)
                except Exception as e:
                    print(f"❌ خطای تلگرام در ارسال RSI {pair}: {e}")

    if alerts_sent == 0:
        print("پایان بررسی: هیچ ارزی در ۵ دقیقه اخیر پامپ/دامپ نداشته و RSI در اشباع نیست.")
    else:
        print(f"پایان بررسی: مجموعاً {alerts_sent} آلارم ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
    
    # پیام ضربان قلب
    try:
        send_telegram_message("🔄 اسکن ۵ دقیقه‌ای انجام شد. شرایط خاصی (پامپ/دامپ یا اشباع RSI) یافت نشد.")
    except Exception as e:
        print(f"خطا در ارسال پیام ضربان قلب! مشکل از توکن یا آیدی کانال است: {e}")
