import requests
import os
import html
import concurrent.futures
from datetime import datetime, timezone, timedelta

# لیست نمادها (می‌توانید کوتاه‌تر کنید اگر 429 می‌گیرید)
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "TRXUSDT", "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "JUPUSDT", "ENAUSDT", "PEOPLEUSDT",
    "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "CHZUSDT", "XLMUSDT", "ALGOUSDT", "EOSUSDT", "NEOUSDT",
    "DASHUSDT", "ZECUSDT", "XECUSDT", "ETCUSDT", "GRTUSDT", "SUSHIUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT", "YFIUSDT",
    "DYDXUSDT", "GMXUSDT", "RUNEUSDT", "AVAILUSDT", "XAIUSDT", "BLURUSDT", "APEUSDT", "GMTUSDT", "JTOUSDT", "PYTHUSDT",
    "STRKUSDT", "MNTUSDT", "ORDIUSDT", "TONUSDT", "NOTUSDT", "BANANAUSDT", "ZKUSDT", "ETHFIUSDT", "KASUSDT",
    "TAOUSDT", "MEMEUSDT", "TURBOUSDT", "BOMEUSDT", "WUSDT", "REZUSDT", "LISTAUSDT", "ZROUSDT", "SCRUSDT", "XAUUSDT", "XAGUSDT"
]

# --- تنظیمات ---
INTERVAL = "5"          # ربع ساعت (۱۵ دقیقه) — اگر ۵ دقیقه می‌خواهید به "5" تغییر دهید
KLINE_LIMIT = 100
SPIKE_MIN_BODY_RATIO = 0.3
SPIKE_MIN_SIZE_RATIO = 2.0
MAX_WORKERS = 8          # برای جلوگیری از Rate Limit (429) کمتر شده
REQUEST_TIMEOUT = 6

# بازه زمانی ایران
ACTIVE_START_HOUR = 7
ACTIVE_END_HOUR = 23
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def is_within_active_hours():
    now_iran = datetime.now(IRAN_TZ)
    return ACTIVE_START_HOUR <= now_iran.hour < ACTIVE_END_HOUR

def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        print("🚨 BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطا در تلگرام: {e}")
        return False

BAR_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m",
    "30": "30m", "60": "1H", "240": "4H", "D": "1D"
}

def symbol_to_okx_instid(symbol):
    base = symbol[:-4]
    return f"{base}-USDT-SWAP"

def is_spike_pattern(candles):
    if len(candles) < 2:
        return False, None

    # کندل آخر
    last = candles[-1]
    o_l, h_l, l_l, c_l = map(float, last[1:5])
    body_l = abs(c_l - o_l)
    range_l = h_l - l_l
    
    # ✅ محافظت در برابر تقسیم بر صفر
    if range_l <= 0:
        return False, None

    # کندل قبلی
    prev = candles[-2]
    o_p, h_p, l_p, c_p = map(float, prev[1:5])
    body_p = abs(c_p - o_p)

    # اسپایک تک‌کندلی
    if (body_l / range_l) >= SPIKE_MIN_BODY_RATIO:
        if body_p == 0:
            # اگر کندل قبلی کاملاً صاف بود و کندل فعلی بدنه دارد، اسپایک محسوب می‌شود
            if body_l > 0:
                direction = "🟢 صعودی" if c_l > o_l else "🔴 نزولی"
                return True, direction
        else:
            if (body_l / body_p) >= SPIKE_MIN_SIZE_RATIO:
                direction = "🟢 صعودی" if c_l > o_l else "🔴 نزولی"
                return True, direction

    # الگوی ۳ کندلی
    if len(candles) >= 3:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        o1, h1, l1, c1_c = map(float, c1[1:5])
        o2, h2, l2, c2_c = map(float, c2[1:5])
        o3, h3, l3, c3_c = map(float, c3[1:5])

        body1 = abs(c1_c - o1)
        body2 = abs(c2_c - o2)
        range1 = h1 - l1
        range2 = h2 - l2

        # ✅ محافظت در برابر تقسیم بر صفر
        if range1 <= 0 or range2 <= 0:
            return False, None

        # کندل اول: بدنه کوچک
        if (body1 / range1) < 0.3:
            if (body2 / range2) >= SPIKE_MIN_BODY_RATIO:
                if body1 == 0:
                    if body2 > 0:
                        direction = "🟢 صعودی" if c2_c > o2 else "🔴 نزولی"
                        if (direction == "🟢 صعودی" and c3_c > o3) or (direction == "🔴 نزولی" and c3_c < o3):
                            return True, direction
                else:
                    if (body2 / body1) >= SPIKE_MIN_SIZE_RATIO:
                        direction = "🟢 صعودی" if c2_c > o2 else "🔴 نزولی"
                        if (direction == "🟢 صعودی" and c3_c > o3) or (direction == "🔴 نزولی" and c3_c < o3):
                            return True, direction

    return False, None

def fetch_candles(symbol, retries=1):
    for attempt in range(retries + 1):
        try:
            inst_id = symbol_to_okx_instid(symbol)
            bar = BAR_MAP.get(INTERVAL, "15m")
            url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == '0':
                    return data.get('data', [])
            print(f"⚠️ {symbol}: تلاش {attempt+1} - HTTP {resp.status_code}")
        except Exception as e:
            print(f"❌ {symbol}: خطا در تلاش {attempt+1} -> {e}")
    return None

def check_spike(symbol):
    candles = fetch_candles(symbol)
    if not candles or len(candles) < 2:
        return symbol, None, False, None

    # حذف کندل ناقص (index 0 در OKX ناقص است)
    valid = candles[1:]
    valid.reverse()
    current_price = float(valid[-1][4])

    spike_detected, spike_direction = is_spike_pattern(valid)
    return symbol, current_price, spike_detected, spike_direction

def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه ({ACTIVE_START_HOUR}-{ACTIVE_END_HOUR}) به وقت ایران.")
        return

    spike_alerts = []
    print(f"🔍 اسکن {len(PAIRS)} نماد در تایم‌فریم {INTERVAL} دقیقه...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_spike, PAIRS))

        for symbol, current_price, spike_detected, spike_direction in results:
            if spike_detected and current_price is not None:
                alert = f"<b>{symbol}</b>: اسپایک {spike_direction} در قیمت <code>{current_price:.4f} USDT</code>"
                spike_alerts.append(alert)
                print(f"✅ {symbol}: اسپایک {spike_direction}")

    if not spike_alerts:
        print("ℹ️ هیچ اسپایکی یافت نشد.")
        return

    msg = (
        "<b>🚨 سیگنال اسپایک در فیوچرز 🚨</b>\n"
        f"📊 تایم‌فریم: {INTERVAL} دقیقه | نماد: {len(PAIRS)}\n"
        "🔍 بدنه بزرگ + تایید جهت\n\n"
    ) + "\n".join([f"• {a}" for a in spike_alerts])

    print("\n----- پیام -----\n" + msg)
    if send_telegram_message(msg):
        print("✅ ارسال شد.")
    else:
        print("❌ ارسال نشد.")

if __name__ == "__main__":
    main()
