import requests
import os
import html
import concurrent.futures
from datetime import datetime, timezone, timedelta

PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "TRXUSDT", "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "JUPUSDT", "NEIROUSDT", "ENAUSDT", "PEOPLEUSDT",
    "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "CHZUSDT", "XLMUSDT", "ALGOUSDT", "EOSUSDT", "NEOUSDT",
    "DASHUSDT", "ZECUSDT", "XECUSDT", "ETCUSDT", "GRTUSDT", "SUSHIUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT", "YFIUSDT",
    "1INCHUSDT", "BALUSDT", "LDOUSDT", "DYDXUSDT", "GMXUSDT", "RUNEUSDT", "AVAILUSDT", "ALTUSDT", "XAIUSDT", "BLURUSDT",
    "APEUSDT", "GMTUSDT", "JTOUSDT", "PYTHUSDT", "DYMUSDT", "PIXELUSDT", "MANTAUSDT", "STRKUSDT", "MNTUSDT", "ORDIUSDT",
    "1000SHIBUSDT", "1000PEPEUSDT", "1000XECUSDT", "1000LUNCUSDT", "LUNAUSDT", "ASTRUSDT", "FLOWUSDT", "XTZUSDT", "KAVAUSDT",
    "ROSEUSDT", "RNDRUSDT", "OCEANUSDT", "AGIXUSDT", "ARUSDT", "MINAUSDT", "IMXUSDT", "CFXUSDT", "STXUSDT",
    "KASUSDT", "TAOUSDT", "MEMEUSDT", "TURBOUSDT", "BOMEUSDT", "WUSDT", "ZKUSDT", "ETHFIUSDT", "EIGENUSDT", "TONUSDT",
    "NOTUSDT", "BANANAUSDT", "1000SATSUSDT", "OMNIUSDT", "REZUSDT", "LISTAUSDT", "ZROUSDT", "1000RATSUSDT", "1000CATSUSDT", "SCRUSDT",
    "XAUUSDT", "XAGUSDT"
]

# --- تنظیمات قابل تغییر ---
INTERVAL = "5"          # تایم‌فریم: 1, 3, 5, 15, 30, 60, 240, D
KLINE_LIMIT = 100        # تعداد کندل برای محاسبه سطوح پیوت
ALERT_THRESHOLD = 0.01  # آلارم اگر قیمت به 1% سطح پیوت نزدیک شد

# بازه ساعتی مجاز برای ارسال سیگنال (به وقت ایران)
ACTIVE_START_HOUR = 7   # 9 صبح
ACTIVE_END_HOUR = 23     # 23 شب
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def is_within_active_hours():
    """چک می‌کنه که الان بین ساعت ۹ صبح تا ۲۳ شب به وقت ایران هست یا نه"""
    now_iran = datetime.now(IRAN_TZ)
    return ACTIVE_START_HOUR <= now_iran.hour < ACTIVE_END_HOUR

def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")

    if not token or not chat_id:
        print("🚨 خطای بحرانی: BOT_TOKEN یا CHANNEL_ID تنظیم نشده است!")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطای تلگرام: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطای شبکه در ارسال تلگرام: {e}")
        return False

# نگاشت تایم‌فریم به فرمت OKX
BAR_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m",
    "30": "30m", "60": "1H", "240": "4H", "D": "1Dutc"
}

def symbol_to_okx_instid(symbol):
    """تبدیل نماد Bybit مثل BTCUSDT به فرمت OKX مثل BTC-USDT-SWAP"""
    base = symbol[:-4]  # حذف USDT از انتها
    return f"{base}-USDT-SWAP"

def calculate_pivot_levels(closes, highs, lows):
    """محاسبه سطوح پیوت (Pivot, R1, R2, S1, S2)"""
    if len(closes) < 1 or len(highs) < 1 or len(lows) < 1:
        return None

    high = max(highs)
    low = min(lows)
    close = closes[-1]

    pivot = (high + low + close) / 3
    R1 = 2 * pivot - low
    S1 = 2 * pivot - high
    R2 = pivot + (high - low)
    S2 = pivot - (high - low)

    return {
        'Pivot': pivot,
        'R1': R1,
        'R2': R2,
        'S1': S1,
        'S2': S2,
    }

def check_pivot_levels(symbol):
    """برای یک نماد، سطوح پیوت رو از OKX می‌گیره و برمی‌گردونه"""
    try:
        inst_id = symbol_to_okx_instid(symbol)
        bar = BAR_MAP.get(INTERVAL, "5m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}"
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            print(f"⚠️ {symbol}: HTTP {response.status_code} -> {response.text[:120]}")
            return symbol, None, None, None

        data = response.json()
        if data.get('code') != '0':
            print(f"⚠️ {symbol}: خطای OKX -> {data.get('msg')}")
            return symbol, None, None, None

        candles = data.get('data', [])
        if len(candles) < 10:
            return symbol, None, None, None

        # اولین آیتم جدیدترینه و ممکنه هنوز کامل نشده باشه، کنارش می‌ذاریم
        closed = candles[1:]
        closed.reverse()  # قدیم -> جدید
        closes = [float(c[4]) for c in closed]  # ایندکس 4 = close
        highs = [float(c[2]) for c in closed]   # ایندکس 2 = high
        lows = [float(c[3]) for c in closed]     # ایندکس 3 = low

        levels = calculate_pivot_levels(closes, highs, lows)
        current_price = closes[-1]

        return symbol, levels, current_price, None

    except Exception as e:
        print(f"❌ {symbol}: خطا -> {e}")
        return symbol, None, None, None

def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR} تا {ACTIVE_END_HOUR} به وقت ایران). برنامه متوقف می‌شود.")
        return

    alerts = []

    print(f"🔍 شروع اسکن {len(PAIRS)} نماد در تایم‌فریم {INTERVAL} دقیقه...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_pivot_levels, PAIRS)

        for symbol, levels, current_price, _ in results:
            if levels is None or current_price is None:
                continue

            alert_triggered = False
            for level_name, level_value in levels.items():
                distance = abs(current_price - level_value)
                threshold = level_value * ALERT_THRESHOLD

                if distance <= threshold:
                    alert_message = f"🚨 {symbol}: قیمت ({current_price:.4f}) به {level_name} ({level_value:.4f}) نزدیک است!"
                    alerts.append(alert_message)
                    alert_triggered = True

            if alert_triggered:
                print(f"✅ {symbol}: آلارم فعال شد!")

    if not alerts:
        print("ℹ️ هیچ آلارمی یافت نشد. پیامی ارسال نمی‌شود.")
        return

    message_lines = ["📊 <b>گزارش آلارم سطوح پیوت (SP2L)</b>\n"]
    for alert in alerts:
        message_lines.append(f"• {html.escape(alert)}")

    final_message = "\n".join(message_lines)
    print("----- پیام نهایی -----")
    print(final_message)

    sent = send_telegram_message(final_message)
    if sent:
        print("✅ پیام با موفقیت به تلگرام ارسال شد.")
    else:
        print("❌ ارسال پیام به تلگرام ناموفق بود.")

if __name__ == "__main__":
    main()
