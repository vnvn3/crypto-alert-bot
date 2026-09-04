import requests
import os
import html
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta

# ==========================================================
# لیست نمادها (گسترش‌یافته - همه معتبر روی فیوچرز OKX)
# ==========================================================
PAIRS = [
    # اصلی‌ها
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
    "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT",
    "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "TRXUSDT",
    "POLUSDT", "ICPUSDT", "TONUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "XLMUSDT", "ETCUSDT", "MKRUSDT", "TAOUSDT", "RENDERUSDT", "FETUSDT", "STXUSDT",
    "IMXUSDT", "KASUSDT", "MNTUSDT", "ONDOUSDT", "EIGENUSDT",
    # میم‌کوین‌ها
    "SHIBUSDT", "PEPEUSDT", "BONKUSDT", "FLOKIUSDT", "WIFUSDT", "MEMEUSDT",
    "TURBOUSDT", "BOMEUSDT", "NEIROUSDT", "NOTUSDT", "DOGSUSDT", "CATIUSDT",
    "HMSTRUSDT", "POPCATUSDT", "MEWUSDT", "PNUTUSDT", "ACTUSDT", "GOATUSDT",
    "MOODENGUSDT", "PENGUUSDT", "BANANAUSDT", "LUNCUSDT", "SATSUSDT", "RATSUSDT",
    # دیفای و لایه ۲
    "LDOUSDT", "DYDXUSDT", "GMXUSDT", "RUNEUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT",
    "YFIUSDT", "SUSHIUSDT", "1INCHUSDT", "BALUSDT", "ZRXUSDT", "KNCUSDT", "WOOUSDT",
    "PERPUSDT", "ENAUSDT", "ETHFIUSDT", "JUPUSDT", "ZKUSDT", "ZROUSDT", "STRKUSDT",
    "MANTAUSDT", "BLURUSDT", "AEVOUSDT", "REZUSDT", "LISTAUSDT", "OMNIUSDT",
    # آلت‌کوین‌های قدیمی
    "EOSUSDT", "NEOUSDT", "DASHUSDT", "ZECUSDT", "XTZUSDT", "ALGOUSDT", "IOTAUSDT",
    "ONTUSDT", "QTUMUSDT", "ZILUSDT", "ICXUSDT", "THETAUSDT", "ENJUSDT", "EGLDUSDT",
    "KSMUSDT", "FLOWUSDT", "KAVAUSDT", "ROSEUSDT", "ONEUSDT", "CELOUSDT", "IOSTUSDT",
    "MINAUSDT", "ASTRUSDT", "CFXUSDT", "ARUSDT", "GRTUSDT", "LUNAUSDT",
    # گیمینگ و متاورس
    "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "CHZUSDT", "APEUSDT", "GMTUSDT",
    "MAGICUSDT", "YGGUSDT", "PIXELUSDT", "XAIUSDT", "BIGTIMEUSDT", "AGLDUSDT",
    # سایر
    "WLDUSDT", "JTOUSDT", "PYTHUSDT", "DYMUSDT", "ORDIUSDT", "PEOPLEUSDT",
    "TRBUSDT", "UMAUSDT", "BANDUSDT", "RSRUSDT", "NMRUSDT", "STORJUSDT", "LPTUSDT",
    "ENSUSDT", "API3USDT", "ACHUSDT", "SSVUSDT", "IDUSDT", "ARKMUSDT", "CYBERUSDT",
    "COREUSDT", "ETHWUSDT", "WUSDT", "SCRUSDT", "GLMRUSDT",
]

# ==========================================================
# تنظیمات
# ==========================================================
INTERVAL = "5"                # تایم‌فریم ۵ دقیقه
KLINE_LIMIT = 200             # کندل بیشتر برای پیدا کردن سوئینگ‌ها و OB
PROXIMITY_PCT = 0.003         # نزدیکی = 0.3% فاصله تا سطح
SWING_LEFT = 3                # تعداد کندل چپ برای تایید سوئینگ
SWING_RIGHT = 3               # تعداد کندل راست برای تایید سوئینگ
MAX_SWING_AGE = 150           # سوئینگ‌های قدیمی‌تر از این تعداد کندل نادیده گرفته شوند
OB_IMPULSE_MULTIPLIER = 2.0   # بدنه کندل ایمپالس حداقل 2 برابر میانگین بدنه‌ها
OB_LOOKBACK = 100             # چند کندل آخر برای جستجوی Order Block
MIN_SWING_DISTANCE_PCT = 0.005  # سوئینگ حداقل 0.5% با قیمت فعلی در گذشته فاصله داشته باشد

ACTIVE_START_HOUR = 7
ACTIVE_END_HOUR = 23
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

MAX_WORKERS = 8
REQUEST_TIMEOUT = 10
TELEGRAM_MAX_LEN = 4000

BAR_MAP = {"1": "1m", "3": "3m", "5": "5m", "15": "15m",
           "30": "30m", "60": "1H", "240": "4H", "D": "1Dutc"}

# استفاده از Session برای سرعت بیشتر (اتصال TCP مجدد استفاده می‌شود)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


# ==========================================================
# توابع کمکی
# ==========================================================
def is_within_active_hours():
    now_iran = datetime.now(IRAN_TZ)
    return ACTIVE_START_HOUR <= now_iran.hour < ACTIVE_END_HOUR


def symbol_to_okx_instid(symbol):
    return f"{symbol[:-4]}-USDT-SWAP"


def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        print("🚨 BOT_TOKEN یا CHANNEL_ID تنظیم نشده است!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            print(f"❌ تلگرام: {r.status_code} - {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"❌ خطای شبکه تلگرام: {e}")
        return False


def send_long_message(full_text):
    lines = full_text.split("\n")
    chunk = ""
    ok = True
    for line in lines:
        if len(chunk) + len(line) + 1 > TELEGRAM_MAX_LEN:
            if not send_telegram_message(chunk):
                ok = False
            chunk = ""
            time.sleep(1)
        chunk += line + "\n"
    if chunk.strip():
        if not send_telegram_message(chunk):
            ok = False
    return ok


# ==========================================================
# ۱) پیدا کردن سوئینگ‌های چرخشی (کف و سقف قبلی)
# ==========================================================
def find_swing_points(highs, lows):
    """
    سوئینگ‌ها با روش فرکتال: کندلی که از N کندل چپ و راستش
    بالاتر (سوئینگ‌های) یا پایین‌تر (سوئینگ‌لو) باشد.
    """
    swing_highs, swing_lows = [], []
    n = len(highs)
    for i in range(SWING_LEFT, n - SWING_RIGHT):
        window_h = highs[i - SWING_LEFT: i + SWING_RIGHT + 1]
        window_l = lows[i - SWING_LEFT: i + SWING_RIGHT + 1]
        if highs[i] == max(window_h) and window_h.count(highs[i]) == 1:
            swing_highs.append((i, highs[i]))
        if lows[i] == min(window_l) and window_l.count(lows[i]) == 1:
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


# ==========================================================
# ۲) پیدا کردن Order Block های مصرف‌نشده
# ==========================================================
def find_order_blocks(candles):
    """
    Order Block صعودی (Bullish OB):
      آخرین کندل نزولی قبل از یک حرکت صعودی قوی
      (کندل بعدی بدنه بزرگ دارد و سقف کندل OB را می‌شکند)
      → زون: از Low تا High آن کندل نزولی

    Order Block نزولی (Bearish OB):
      آخرین کندل صعودی قبل از یک حرکت نزولی قوی
      → زون: از Low تا High آن کندل صعودی

    فقط OB هایی برگردانده می‌شوند که هنوز mitigate (مصرف) نشده‌اند.
    """
    n = len(candles)
    if n < 20:
        return []

    opens = [float(c[1]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    closes = [float(c[4]) for c in candles]

    bodies = [abs(closes[i] - opens[i]) for i in range(n)]
    avg_body = sum(bodies[-50:]) / min(50, n)
    if avg_body <= 0:
        return []

    order_blocks = []
    start = max(1, n - OB_LOOKBACK)

    for i in range(start, n - 2):
        # --- Bullish OB: کندل i نزولی + کندل i+1 صعودی قوی که سقف i را می‌شکند
        if closes[i] < opens[i]:
            if (closes[i + 1] > opens[i + 1] and
                    bodies[i + 1] >= avg_body * OB_IMPULSE_MULTIPLIER and
                    closes[i + 1] > highs[i]):
                zone_low, zone_high = lows[i], highs[i]
                # چک mitigation: اگر بعداً قیمت زیر کف زون رفته، OB باطل است
                mitigated = any(lows[j] < zone_low for j in range(i + 2, n))
                if not mitigated:
                    order_blocks.append(("BULLISH", zone_low, zone_high, i))

        # --- Bearish OB: کندل i صعودی + کندل i+1 نزولی قوی که کف i را می‌شکند
        if closes[i] > opens[i]:
            if (closes[i + 1] < opens[i + 1] and
                    bodies[i + 1] >= avg_body * OB_IMPULSE_MULTIPLIER and
                    closes[i + 1] < lows[i]):
                zone_low, zone_high = lows[i], highs[i]
                # چک mitigation: اگر بعداً قیمت بالای سقف زون رفته، OB باطل است
                mitigated = any(highs[j] > zone_high for j in range(i + 2, n))
                if not mitigated:
                    order_blocks.append(("BEARISH", zone_low, zone_high, i))

    return order_blocks


# ==========================================================
# بررسی هر نماد
# ==========================================================
def check_symbol(symbol):
    signals = []
    try:
        inst_id = symbol_to_okx_instid(symbol)
        bar = BAR_MAP.get(INTERVAL, "5m")
        url = (f"https://www.okx.com/api/v5/market/candles"
               f"?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}")

        r = session.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            print(f"⚠️ {symbol}: HTTP {r.status_code}")
            return symbol, None
        data = r.json()
        if data.get('code') != '0':
            print(f"⚠️ {symbol}: {data.get('msg')}")
            return symbol, None

        candles = data.get('data', [])
        closed = [c for c in candles if c[-1] == "1"]
        closed.reverse()  # قدیمی → جدید
        if len(closed) < 50:
            return symbol, None

        highs = [float(c[2]) for c in closed]
        lows = [float(c[3]) for c in closed]
        closes = [float(c[4]) for c in closed]
        price = closes[-1]
        n = len(closed)

        # ---------- ۱) سقف و کف محدوده (Range High/Low) ----------
        range_high = max(highs[:-1])
        range_low = min(lows[:-1])

        if abs(price - range_high) / range_high <= PROXIMITY_PCT:
            signals.append(f"⛰ نزدیک <b>سقف محدوده</b> ({range_high:.6g})")
        if abs(price - range_low) / range_low <= PROXIMITY_PCT:
            signals.append(f"🕳 نزدیک <b>کف محدوده</b> ({range_low:.6g})")

        # ---------- ۲) سوئینگ‌های قبلی ----------
        swing_highs, swing_lows = find_swing_points(highs, lows)

        for idx, sh in swing_highs:
            age = n - 1 - idx
            if age > MAX_SWING_AGE or age < SWING_RIGHT + 2:
                continue
            # سوئینگی معتبر است که قیمت بعد از آن حداقل کمی دور شده باشد
            if abs(price - sh) / sh <= PROXIMITY_PCT:
                min_after = min(lows[idx + 1:])
                if (sh - min_after) / sh >= MIN_SWING_DISTANCE_PCT:
                    signals.append(f"🔴 رسیدن به <b>سقف قبلی</b> ({sh:.6g}) - {age} کندل پیش")
                    break  # فقط نزدیک‌ترین سوئینگ‌های کافی است

        for idx, sl in swing_lows:
            age = n - 1 - idx
            if age > MAX_SWING_AGE or age < SWING_RIGHT + 2:
                continue
            if abs(price - sl) / sl <= PROXIMITY_PCT:
                max_after = max(highs[idx + 1:])
                if (max_after - sl) / sl >= MIN_SWING_DISTANCE_PCT:
                    signals.append(f"🟢 رسیدن به <b>کف قبلی</b> ({sl:.6g}) - {age} کندل پیش")
                    break

        # ---------- ۳) Order Block ها ----------
        obs = find_order_blocks(closed)
        for ob_type, z_low, z_high, idx in obs:
            age = n - 1 - idx
            if age < 3:  # OB خیلی تازه را نادیده بگیر
                continue
            zone_mid = (z_low + z_high) / 2
            # قیمت داخل زون یا خیلی نزدیک به آن
            in_zone = z_low <= price <= z_high
            near_zone = abs(price - zone_mid) / zone_mid <= PROXIMITY_PCT * 2
            if in_zone or near_zone:
                emoji = "🟩" if ob_type == "BULLISH" else "🟥"
                signals.append(
                    f"{emoji} رسیدن به <b>Order Block {ob_type}</b> "
                    f"[{z_low:.6g} - {z_high:.6g}] - {age} کندل پیش"
                )

        if signals:
            return symbol, (price, signals)
        return symbol, None

    except Exception as e:
        print(f"❌ {symbol}: خطا -> {e}")
        return symbol, None


# ==========================================================
# تابع اصلی
# ==========================================================
def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR}-{ACTIVE_END_HOUR} ایران).")
        return

    start_time = time.time()
    print(f"🔍 اسکن {len(PAIRS)} نماد | تایم {INTERVAL}m | کف/سقف + Order Block ...")

    results_with_signal = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for symbol, result in executor.map(check_symbol, PAIRS):
            if result:
                results_with_signal.append((symbol, result))

    elapsed = time.time() - start_time
    print(f"⏱ زمان اسکن: {elapsed:.1f} ثانیه")

    if not results_with_signal:
        print("ℹ️ هیچ سیگنالی یافت نشد.")
        return

    now_iran = datetime.now(IRAN_TZ).strftime("%H:%M")
    lines = [f"🎯 <b>اسکنر کف/سقف و Order Block | تایم {INTERVAL}m | {now_iran}</b>", ""]

    for symbol, (price, signals) in results_with_signal:
        lines.append(f"💠 <b>{html.escape(symbol)}</b> | قیمت: {price:.6g}")
        for s in signals:
            lines.append(f"   • {s}")
        lines.append("")

    final_message = "\n".join(lines)
    print("----- پیام نهایی -----")
    print(final_message)

    if send_long_message(final_message):
        print("✅ ارسال شد.")
    else:
        print("❌ ارسال ناموفق.")


if __name__ == "__main__":
    main()
