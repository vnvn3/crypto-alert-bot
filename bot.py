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

# --- تابع محاسبه دقیق تغییرات ۵ دقیقه و RSI ---
def get_5m_data_and_rsi(symbol, period=14):
    try:
        # دریافت ۱۵ کندل ۵ دقیقه ای
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit=15"
        response = requests.get(url, timeout=10)
        
        # اگر بایننس آی‌پی را مسدود کرده باشد اینجا ارور می‌دهد
        if response.status_code == 451 or response.status_code == 403:
            raise Exception(f"Block/IP Banned - Status: {response.status_code}")
            
        response.raise_for_status()
        klines = response.json()
        
        # محاسبه تغییرات: مقایسه قیمت فعلی با بسته شدن کندل ۵ دقیقه قبلی
        prev_candle_close = float(klines[-2][4])
        current_price = float(klines[-1][4])
        
        change_5m = ((current_price - prev_candle_close) / prev_candle_close) * 100 if prev_candle_close != 0 else 0.0
        
        # محاسبه RSI روی تایم ۵ دقیقه
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
        # فقط پرینت می‌گیرد تا برنامه متوقف نشود
        print(f"❌ خطا API برای {symbol}: {e}")
        return None, None

# --- تابع اصلی بررسی و ارسال ---
def check_and_send_alerts():
    print(f"شروع بررسی {len(PAIRS)} ارز در تایم فریم ۵ دقیقه...")
    alerts_sent = 0
    api_errors = 0  # شمارنده خطاهای بایننس
    
    for pair in PAIRS:
        symbol = pair.replace(".P", "")
        symbol_clean = pair.replace(".P", "").replace("USDT", "")
        safe_symbol = html.escape(symbol_clean)
        
        change_5m, rsi = get_5m_data_and_rsi(symbol)
        
        # اگر دیتا نگیریم، بشماریم و بگذریم
        if change_5m is None or rsi is None:
            api_errors += 1
            time.sleep(0.5) # اگر ارور بود صبر بیشتری کن تا ایمیل بند نشیم
            continue
            
        time.sleep(0.2) 
        message_sent_for_pair = False

        # برای دیباگ در گیت‌هاب (وقتی لاگ‌ها را چک می‌کنید قیمت بیت‌کوین را می‌بینید)
        if symbol == "BTCUSDT":
            print(f"🔍 BTC Debug -> Change: {change_5m:.2f}% | RSI: {rsi:.1f}")

        # ==========================================
        # شرط اول: پامپ و دامپ در ۵ دقیقه
        # (توجه: در تایم 5 دقیقه اعداد بزرگ مثل 2 درصد خیلی نادرند، اینجا حساس تر کردم)
        # ==========================================
        if change_5m >= 1.5:
            emoji, action_word = "🚀🚀🚀", "پامپ شدید 5m"
        elif change_5m >= 0.8:
            emoji, action_word = "🚀🚀", "پامپ 5m"
        elif change_5m >= 0.4:
            emoji, action_word = "🚀", "رشد کوتاه 5m"
        elif change_5m <= -1.5:
            emoji, action_word = "💀💀💀", "دامپ شدید 5m"
        elif change_5m <= -0.8:
            emoji, action_word = "💀💀", "دامپ 5m"
        elif change_5m <= -0.4:
            emoji, action_word = "📉", "ریزش کوتاه 5m"
        else:
            emoji, action_word = None, None

        if action_word:
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
        # شرط دوم: رسیدن RSI به اشباع (حتی بدون پامپ شدید)
        # ==========================================
        if not message_sent_for_pair:
            if rsi >= 75: # کمی حساس‌تر کردم
                rsi_message = (
                    f"🔴 <b>اشباع خرید RSI در 5m</b>\n"
                    f"🪙 فیوچرز {safe_symbol}\n"
                    f"📊 مقدار: <code>{rsi:.1f}</code>\n"
                    f"📉 تغییرات: <code>{change_5m:.2f}%</code>"
                )
                try:
                    send_telegram_message(rsi_message)
                    alerts_sent += 1
                    print(f"✅ سیگنال اشباع خرید RSI برای {pair} ارسال شد.")
                    time.sleep(1)
                except Exception as e:
                    print(f"❌ خطای تلگرام در ارسال RSI {pair}: {e}")
                    
            elif rsi <= 25: # کمی حساس‌تر کردم
                rsi_message = (
                    f"🟢 <b>اشباع فروش RSI در 5m</b>\n"
                    f"🪙 فیوچرز {safe_symbol}\n"
                    f"📊 مقدار: <code>{rsi:.1f}</code>\n"
                    f"📈 تغییرات: <code>{change_5m:.2f}%</code>"
                )
                try:
                    send_telegram_message(rsi_message)
                    alerts_sent += 1
                    print(f"✅ سیگنال اشباع فروش RSI برای {pair} ارسال شد.")
                    time.sleep(1)
                except Exception as e:
                    print(f"❌ خطای تلگرام در ارسال RSI {pair}: {e}")

    # ================= گزارش نهایی =================
    if api_errors == len(PAIRS):
        print("🚨 خطای قطعی: بایننس تمام درخواست‌ها را رد کرد (احتمالا IP گیت‌هاب بلاک شده است).")
    
    if alerts_sent == 0:
        print("پایان بررسی: سیگنال خاصی یافت نشد.")
    else:
        print(f"پایان بررسی: مجموعاً {alerts_sent} آلارم ارسال شد.")

if __name__ == "__main__":
    check_and_send_alerts()
    
    # پیام ضربان قلب هوشمند
    try:
        # اگر خطای API زیاد بود به کاربر اخبار بده
        # (برای خواندن متغیر از تابع اصلی، آن را گلوبال می‌کردیم اما برای سادگی پیام ثابت می‌گذاریم)
        send_telegram_message("🔄 اسکن ۵ دقیقه‌ای انجام شد.\n\n⚠️ <i>نکته: اگر می‌دانید بازار پامپ دارد ولی سیگنال نمی‌آید، لطفاً لاگ‌های (Logs) گیت‌هاب را چک کنید. اگر نوشته بود (Block/IP Banned)، یعنی بایننس آی‌پی گیت‌هاب را مسدود کرده است.</i>")
    except Exception as e:
        print(f"خطا در ارسال پیام ضربان قلب! مشکل از توکن یا آیدی کانال است: {e}")
