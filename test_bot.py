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
KLINE_LIMIT = 100       # تعداد کندل برای محاسبه سطوح پیوت
ALERT_THRESHOLD = 0.01  # آلارم اگر قیمت به 1% سطح پیوت نزدیک شد
SPIKE_MIN_BODY_RATIO = 0.02  # حداقل نسبت بدنه به سایه برای اسپایک
SPIKE_MIN_SIZE_RATIO = 2.0   # حداقل نسبت اندازه بدنه اسپایک به کندل قبلی

# بازه ساعتی مجاز برای ارسال سیگنال (به وقت ایران)
ACTIVE_START_HOUR = 9
ACTIVE_END_HOUR = 23
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def is_within_active_hours():
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
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطای شبکه در ارسال تلگرام: {e}")
        return False

BAR_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m",
    "30": "30m", "60": "1H", "240": "4H", "D": "1Dutc"
}

def symbol_to_okx_instid(symbol):
    base = symbol[:-4]
    return f"{base}-USDT-SWAP"

def calculate_pivot_levels(closes, highs, lows):
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
    return {'Pivot': pivot, 'R1': R1, 'R2': R2, 'S1': S1, 'S2': S2}

def is_strong_spike_pattern(candles):
    """
    شناسایی الگوی سه کندل اسپایک قوی:
    - کندل اول: بدنه کوچک (دوجی یا بدنه کوتاه)
    - کندل دوم: بدنه بزرگ (اسپایک)
    - کندل سوم: تایید در جهت اسپایک
    """
    if len(candles) < 3:
        return False, None

    # استخراج کندل‌ها (هر کندل: [timestamp, open, high, low, close, volume])
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]
    o1, h1, l1, c1_close = float(c1[1]), float(c1[2]), float(c1[3]), float(c1[4])
    o2, h2, l2, c2_close = float(c2[1]), float(c2[2]), float(c2[3]), float(c2[4])
    o3, h3, l3, c3_close = float(c3[1]), float(c3[2]), float(c3[3]), float(c3[4])

    # محاسبه بدنه و سایه‌ها
    body1 = abs(c1_close - o1)
    body2 = abs(c2_close - o2)
    body3 = abs(c3_close - o3)
    shadow1_up = h1 - max(o1, c1_close)
    shadow1_down = min(o1, c1_close) - l1
    shadow2_up = h2 - max(o2, c2_close)
    shadow2_down = min(o2, c2_close) - l2

    # کندل اول: بدنه کوچک (دوجی یا بدنه کوتاه)
    avg_body1 = (body1 + shadow1_up + shadow1_down) / 3
    if avg_body1 == 0:
        return False, None
    body1_ratio = body1 / avg_body1
    if body1_ratio > 0.3:  # بدنه بزرگتر از 30% کل کندل نیست
        return False, None

    # کندل دوم: بدنه بزرگ (اسپایک)
    avg_body2 = (body2 + shadow2_up + shadow2_down) / 3
    if avg_body2 == 0:
        return False, None
    body2_ratio = body2 / avg_body2
    if body2_ratio < SPIKE_MIN_BODY_RATIO:  # بدنه بزرگتر از 2% کل کندل باشد
        return False, None
    if body2 / body1 < SPIKE_MIN_SIZE_RATIO:  # بدنه اسپایک حداقل 2 برابر بدنه کندل اول باشد
        return False, None

    # جهت اسپایک
    spike_direction = "UP" if c2_close > o2 else "DOWN"

    # کندل سوم: تایید در جهت اسپایک
    if spike_direction == "UP" and c3_close <= o3:
        return False, None
    if spike_direction == "DOWN" and c3_close >= o3:
        return False, None

    return True, spike_direction

def check_pivot_and_spike(symbol):
    try:
        inst_id = symbol_to_okx_instid(symbol)
        bar = BAR_MAP.get(INTERVAL, "5m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            print(f"⚠️ {symbol}: HTTP {response.status_code}")
            return symbol, None, None, None, None

        data = response.json()
        if data.get('code') != '0':
            print(f"⚠️ {symbol}: خطای OKX -> {data.get('msg')}")
            return symbol, None, None, None, None

        candles = data.get('data', [])
        if len(candles) < 3:
            return symbol, None, None, None, None

        # حذف کندل آخر اگر کامل نیست
        closed = candles[1:]
        closed.reverse()
        closes = [float(c[4]) for c in closed]
        highs = [float(c[2]) for c in closed]
        lows = [float(c[3]) for c in closed]
        current_price = closes[-1]

        levels = calculate_pivot_levels(closes, highs, lows)
        spike_detected, spike_direction = is_strong_spike_pattern(closed)

        return symbol, levels, current_price, spike_detected, spike_direction

    except Exception as e:
        print(f"❌ {symbol}: خطا -> {e}")
        return symbol, None, None, None, None

def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR} تا {ACTIVE_END_HOUR} به وقت ایران).")
        return

    alerts = []
    spike_alerts = []

    print(f"🔍 شروع اسکن {len(PAIRS)} نماد در تایم‌فریم {INTERVAL} دقیقه...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_pivot_and_spike, PAIRS)

        for symbol, levels, current_price, spike_detected, spike_direction in results:
            if levels is None or current_price is None:
                continue

            # چک آلارم سطوح پیوت
            for level_name, level_value in levels.items():
                distance = abs(current_price - level_value)
                threshold = level_value * ALERT_THRESHOLD
                if distance <= threshold:
                    alert_message = f"🚨 {symbol}: قیمت ({current_price:.4f}) به {level_name} ({level_value:.4f}) نزدیک است!"
                    alerts.append(alert_message)

            # چک الگوی اسپایک
            if spike_detected:
                spike_message = f"🔥 {symbol}: الگوی اسپایک {spike_direction} شناسایی شد!"
                spike_alerts.append(spike_message)

    # ارسال آلارم‌ها
    final_message_lines = []

    if alerts:
        final_message_lines.append("📊 <b>گزارش آلارم سطوح پیوت (SP2L)</b>\n")
        for alert in alerts:
            final_message_lines.append(f"• {html.escape(alert)}")
        final_message_lines.append("")

    if spike_alerts:
        final_message_lines.append("🔥 <b>الگوی اسپایک قوی</b>\n")
        for spike_alert in spike_alerts:
            final_message_lines.append(f"• {html.escape(spike_alert)}")

    if not final_message_lines:
        print("ℹ️ هیچ آلارمی یافت نشد.")
        return

    final_message = "\n".join(final_message_lines)
    print("----- پیام نهایی -----")
    print(final_message)

    sent = send_telegram_message(final_message)
    if sent:
        print("✅ پیام با موفقیت به تلگرام ارسال شد.")
    else:
        print("❌ ارسال پیام به تلگرام ناموفق بود.")

if __name__ == "__main__":
    main()
