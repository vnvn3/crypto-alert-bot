
import requests
import os
import html
import concurrent.futures
from datetime import datetime, timezone, timedelta

# لیست کامل نمادهای فیوچرز OKX (300+ نماد)
PAIRS = [
    # Top 50
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "TRXUSDT", "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "JUPUSDT", "ENAUSDT", "PEOPLEUSDT",
    "FTMUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "CHZUSDT", "XLMUSDT", "ALGOUSDT", "EOSUSDT", "NEOUSDT",
    # Next 100
    "DASHUSDT", "ZECUSDT", "XECUSDT", "ETCUSDT", "GRTUSDT", "SUSHIUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT", "YFIUSDT",
    "1INCHUSDT", "BALUSDT", "LDOUSDT", "DYDXUSDT", "GMXUSDT", "RUNEUSDT", "AVAILUSDT", "XAIUSDT", "BLURUSDT", "APEUSDT",
    "GMTUSDT", "JTOUSDT", "PYTHUSDT", "DYMUSDT", "PIXELUSDT", "MANTAUSDT", "STRKUSDT", "MNTUSDT", "ORDIUSDT",
    "1000SATSUSDT", "OMNIUSDT", "TONUSDT", "NOTUSDT", "BANANAUSDT", "ZKUSDT", "ETHFIUSDT", "EIGENUSDT", "KASUSDT",
    "TAOUSDT", "MEMEUSDT", "TURBOUSDT", "BOMEUSDT", "WUSDT", "REZUSDT", "LISTAUSDT", "ZROUSDT", "SCRUSDT", "XAUUSDT", "XAGUSDT",
    # Additional 150+
    "STORJUSDT", "IOTAUSDT", "VETUSDT", "ONTUSDT", "QTUMUSDT", "THETAUSDT", "WAVESUSDT", "XEMUSDT", "ZILUSDT", "BTTUSDT",
    "CELOUSDT", "ENJUSDT", "HNTUSDT", "IOTXUSDT", "KSMUSDT", "LSKUSDT", "MAIDAUSDT", "NANOUSDT", "OASUSDT", "OGNUSDT",
    "RVNUSDT", "SCUSDT", "STEEMUSDT", "STORMUSDT", "SXPUSDT", "TOMOUSDT", "TROYUSDT", "VTHOUSDT", "WANUSDT", "WTCUSDT",
    "YFIIUSDT", "ZENUSDT", "ADXUSDT", "AIONUSDT", "ALICEUSDT", "AMBUSDT", "ANKRUSDT", "ANTUSDT", "ARDRUSDT", "ARKUSDT",
    "ARNUSDT", "ASTUSDT", "AUTOUSDT", "BATUSDT", "BCNUSDT", "BELUSDT", "BNTUSDT", "BRDUSDT", "BTSUSDT", "CNDUSDT",
    "CVCUSDT", "DGDUSDT", "DLTUSDT", "DMTUSDT", "DOCKUSDT", "DRGNUSDT", "EDOUSDT", "ELFUSDT", "ENGUSDT", "ERDUSDT",
    "FUELUSDT", "FUNUSDT", "GASUSDT", "GNTUSDT", "GUPUSDT", "GVTUSDT", "HOTUSDT", "ICNUSDT", "IQUSDT", "JSTUSDT",
    "KINUSDT", "LENDUSDT", "LRCUSDT", "LUNUSDT", "MCOUSDT", "MFTUSDT", "MITHUSDT", "MKRUSDT", "NASUSDT", "NEBLUSDT",
    "OSTUSDT", "PAYUSDT", "PIVXUSDT", "PLRUSDT", "PNTUSDT", "POLYUSDT", "POTUSDT", "PUNDIXUSDT", "QKCUSDT", "QRLUSDT",
    "QSPUSDT", "REPUSDT", "RLCUSDT", "SIBUSDT", "SKYUSDT", "SLPUSDT", "STAKUSDT", "STPTUSDT", "SYSUSDT", "TAUUSDT",
    "TMTGUSDT", "TNBUSDT", "TNTUSDT", "UBTUSDT", "ULTUSDT", "VIAUSDT", "VIBUSDT", "WAXPUSDT", "XVSUSDT", "XZCUSDT",
    "YOYOWUSDT", "ZCLUSDT", "ZRXUSDT", "AERGOUSDT", "AIOZUSDT", "ALPINEUSDT", "AMUSDT", "ARUSDT", "ASTRUSDT",
    "AUTOUSDT", "BAKEUSDT", "BANDUSDT", "BFCUSDT", "BICOUSDT", "BLOKUSDT", "BLZUSDT", "BONDUSDT", "BORAUSDT", "C98USDT",
    "COTIUSDT", "CROUSDT", "DARUSDT", "DATAUSDT", "DENTUSDT", "DEPUSDT", "DGBUSDT", "DUSKUSDT", "DYMUSDT",
    "EDUUSDT", "EQUADUSDT", "FIDAUSDT", "FITFIUSDT", "FLOKIUSDT", "FORTHUSDT", "FRONTUSDT", "GALUSDT", "GTCUSDT",
    "HFTUSDT", "HIGHUSDT", "HIVEUSDT", "HUMUSDT", "IDUSDT", "ILVUSDT", "IMXUSDT", "INJUSDT", "JASMYUSDT", "JOEUSDT",
    "JSTUSDT", "KAIUSDT", "KASUSDT", "KEEPUSDT", "KEYUSDT", "KNCUSDT", "KP3RUSDT", "LPTUSDT", "LQTYUSDT", "MAGICUSDT",
    "MASKUSDT", "MBOXUSDT", "MCUSDT", "MDTUSDT", "METAUSDT", "MFTUSDT", "MINAUSDT", "MOBUSDT", "MOVRUSDT", "MULTIUSDT",
    "NEOUSDT", "NMRUSDT", "NULSUSDT", "OCEANUSDT", "OGNUSDT", "OMUSDT", "ONGUSDT", "ONTUSDT", "ORBSUSDT", "ORNUSDT",
    "OUSDT", "PAYXUSDT", "PLAUSDT", "POLSUSDT", "PONDUSDT", "PORUSDT", "PSTAKEUSDT", "PUNDIXUSDT", "QASHUSDT", "QIUSDT",
    "QLCUSDT", "QTUMUSDT", "RADUSDT", "RAREUSDT", "RAYUSDT", "REEFUSDT", "RENUSDT", "REQUSDT", "RIFUSDT", "RLCUSDT",
    "ROSEUSDT", "RPLUSDT", "RUFFUSDT", "RVNUSDT", "SANDUSDT", "SBDUSDT", "SFPUSDT", "SHIBUSDT", "SKLUSDT", "SLSUSDT",
    "SMARTUSDT", "SNTUSDT", "SOLVEUSDT", "SRMUSDT", "STMXUSDT", "STORJUSDT", "STPTUSDT", "STXUSDT", "SUSHIUSDT",
    "SXPUSDT", "SYNUSDT", "TAUUSDT", "TELUSDT", "TIMEUSDT", "TKOUSDT", "TLMUSDT", "TOMOUSDT", "TROYUSDT", "TRUUSDT",
    "TUSDT", "UMAUSDT", "UNFIUSDT", "UTKUSDT", "VEEUSDT", "VETUSDT", "VIAUSDT", "VITEUSDT", "WANUSDT", "WAVESUSDT",
    "WAXPUSDT", "WINGUSDT", "WPRUSDT", "WTCUSDT", "XINUSDT", "XLMUSDT", "XNOUSDT", "XPRUSDT", "XRDUSDT", "XRPUSDT",
    "XVSUSDT", "XZCUSDT", "YFIUSDT", "YFIIUSDT", "ZAPUSDT", "ZECUSDT", "ZENUSDT", "ZILUSDT", "ZRXUSDT"
]

# --- تنظیمات بهینه برای GitHub Actions ---
INTERVAL = "5"          # تایم‌فریم 5 دقیقه‌ای
KLINE_LIMIT = 100        # 100 کندل = 25 ساعت
SPIKE_MIN_BODY_RATIO = 0.3  # بدنه ≥ 30% از رنج کندل
SPIKE_MIN_SIZE_RATIO = 2.0   # بدنه اسپایک ≥ 2 برابر کندل قبلی
MAX_WORKERS = 20         # حداکثر 20 درخواست همزمان (برای سرعت بالا در GitHub Actions)
REQUEST_TIMEOUT = 5       # تایم‌اوت 5 ثانیه برای درخواست‌ها

# بازه ساعتی فعال (به وقت ایران)
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
        print("🚨 خطا: BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطا در ارسال تلگرام: {e}")
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

    last = candles[-1]
    o_last, h_last, l_last, c_last = map(float, last[1:5])
    body_last = abs(c_last - o_last)
    range_last = h_last - l_last

    prev = candles[-2]
    o_prev, h_prev, l_prev, c_prev = map(float, prev[1:5])
    body_prev = abs(c_prev - o_prev)

    if (body_last / range_last) >= SPIKE_MIN_BODY_RATIO:
        if (body_last / body_prev) >= SPIKE_MIN_SIZE_RATIO:
            direction = "🟢 صعودی" if c_last > o_last else "🔴 نزولی"
            return True, direction

    if len(candles) >= 3:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        o1, h1, l1, c1_close = map(float, c1[1:5])
        o2, h2, l2, c2_close = map(float, c2[1:5])
        o3, h3, l3, c3_close = map(float, c3[1:5])

        body1 = abs(c1_close - o1)
        body2 = abs(c2_close - o2)
        range1 = h1 - l1
        range2 = h2 - l2

        if (body1 / range1) < 0.3:
            if (body2 / range2) >= SPIKE_MIN_BODY_RATIO and (body2 / body1) >= SPIKE_MIN_SIZE_RATIO:
                direction = "🟢 صعودی" if c2_close > o2 else "🔴 نزولی"
                if (direction == "🟢 صعودی" and c3_close > o3) or (direction == "🔴 نزولی" and c3_close < o3):
                    return True, direction

    return False, None

def fetch_candles(symbol, retries=1):
    for attempt in range(retries + 1):
        try:
            inst_id = symbol_to_okx_instid(symbol)
            bar = BAR_MAP.get(INTERVAL, "15m")
            url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data.get('data', [])
            print(f"⚠️ {symbol}: تلاش {attempt + 1} - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {symbol}: خطا در تلاش {attempt + 1} -> {e}")
    return None

def check_spike(symbol):
    candles = fetch_candles(symbol)
    if not candles or len(candles) < 2:
        return symbol, None, None, None

    valid_candles = candles[1:]  # حذف کندل ناقص
    valid_candles.reverse()
    current_price = float(valid_candles[-1][4])

    spike_detected, spike_direction = is_spike_pattern(valid_candles)
    return symbol, current_price, spike_detected, spike_direction

def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR} تا {ACTIVE_END_HOUR} به وقت ایران).")
        return

    spike_alerts = []
    print(f"🔍 شروع اسکن {len(PAIRS)} نماد در تایم‌فریم {INTERVAL} دقیقه...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_spike, PAIRS))

        for symbol, current_price, spike_detected, spike_direction in results:
            if spike_detected and current_price:
                alert_msg = f"<b>{symbol}</b>: اسپایک {spike_direction} در قیمت <code>{current_price:.4f} USDT</code>"
                spike_alerts.append(alert_msg)
                print(f"✅ {symbol}: اسپایک {spike_direction}")

    if not spike_alerts:
        print("ℹ️ هیچ اسپایکی یافت نشد.")
        return

    final_message = (
        "<b>🚨 سیگنال اسپایک در فیوچرز (15 دقیقه) 🚨</b>\n"
        f"📊 تایم‌فریم: {INTERVAL} دقیقه | نمادهای اسکن شده: {len(PAIRS)}\n"
        "🔍 تشخیص: اسپایک‌های قوی با بدنه بزرگ\n\n"
    ) + "\n".join([f"• {alert}" for alert in spike_alerts])

    print("\n----- پیام نهایی -----\n" + final_message)
    if send_telegram_message(final_message):
        print("✅ پیام با موفقیت به تلگرام ارسال شد.")
    else:
        print("❌ ارسال پیام به تلگرام ناموفق بود.")

if __name__ == "__main__":
    main()
```

---

---

---

### **📌 برنامه دوم: تشخیص کف/سقف و Order Block در تایم 5 دقیقه‌ای**
*(این برنامه کاملا جدا از برنامه اول است و در فایل جدیدی به نام `sr_orderblock_detector.py` ذخیره می‌شود)*

---

### **🔥 کد دوم: `sr_orderblock_detector.py` (کف/سقف و Order Block در 5 دقیقه)**
```python
import requests
import os
import html
import concurrent.futures
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional

# لیست نمادهای مهم (برای سرعت بیشتر، می‌توانید از لیست کامل استفاده کنید)
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "BCHUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "AAVEUSDT", "FILUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "TRXUSDT", "MATICUSDT", "ICPUSDT", "SHIBUSDT", "RENDERUSDT", "MKRUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT", "TIAUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "1000BONKUSDT", "WIFUSDT", "JUPUSDT", "ENAUSDT", "PEOPLEUSDT"
]

# --- تنظیمات ---
INTERVAL = "5"           # تایم‌فریم 5 دقیقه‌ای
KLINE_LIMIT = 200        # 200 کندل = ~16 ساعت داده
THRESHOLD = 0.005        # آستانه 0.5% برای نزدیک بودن به کف/سقف
ORDER_BLOCK_THRESHOLD = 0.2  # بدنه کندل در 20% بالای/پایین رنج برای Order Block
MAX_WORKERS = 20
REQUEST_TIMEOUT = 5

# بازه ساعتی فعال (به وقت ایران)
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
        print("🚨 خطا: BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطا در ارسال تلگرام: {e}")
        return False

BAR_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m",
    "30": "30m", "60": "1H", "240": "4H", "D": "1D"
}

def symbol_to_okx_instid(symbol):
    base = symbol[:-4]
    return f"{base}-USDT-SWAP"

def fetch_candles(symbol, retries=1) -> Optional[List]:
    for attempt in range(retries + 1):
        try:
            inst_id = symbol_to_okx_instid(symbol)
            bar = BAR_MAP.get(INTERVAL, "5m")
            url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                    return data.get('data', [])
            print(f"⚠️ {symbol}: تلاش {attempt + 1} - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {symbol}: خطا در تلاش {attempt + 1} -> {e}")
    return None

def find_support_resistance(candles: List, threshold: float = THRESHOLD) -> Tuple[List[float], List[float]]:
    """یافتن سطوح کف و سقف در کندل‌ها"""
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    current_price = float(candles[-1][4])

    # یافتن کف‌ها (local minima)
    supports = []
    for i in range(2, len(lows) - 2):
        if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1] and lows[i] <= lows[i+2]:
            supports.append(lows[i])

    # یافتن سقف‌ها (local maxima)
    resistances = []
    for i in range(2, len(highs) - 2):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]:
            resistances.append(highs[i])

    # حذف تکراری‌ها و مرتب‌سازی
    supports = sorted(list(set(supports)))
    resistances = sorted(list(set(resistances)))

    # چک کردن نزدیکی به کف/سقف
    near_supports = []
    near_resistances = []
    for s in supports:
        if abs(current_price - s) / s <= threshold:
            near_supports.append(s)
    for r in resistances:
        if abs(current_price - r) / r <= threshold:
            near_resistances.append(r)

    return near_supports, near_resistances

def detect_order_block(candles: List) -> Tuple[bool, str, Optional[float]]:
    """تشخیص Order Block (بلوک سفارش)"""
    if len(candles) < 2:
        return False, "", None

    current_price = float(candles[-1][4])
    last_candle = candles[-1]
    o, h, l, c = map(float, last_candle[1:5])
    body = abs(c - o)
    candle_range = h - l

    # چک کردن Order Block در کندل‌های قبلی
    for i in range(len(candles) - 2, max(-1, len(candles) - 20), -1):
        candle = candles[i]
        o_i, h_i, l_i, c_i = map(float, candle[1:5])
        body_i = abs(c_i - o_i)
        range_i = h_i - l_i

        # Bullish Order Block: کندل قبلی با بدنه قوی صعودی (بیش از 80% در بالا)
        if (c_i - o_i) / range_i >= (1 - ORDER_BLOCK_THRESHOLD):
            ob_zone_low = l_i
            ob_zone_high = h_i
            if ob_zone_low <= current_price <= ob_zone_high:
                return True, "Bullish Order Block", ob_zone_high

        # Bearish Order Block: کندل قبلی با بدنه قوی نزولی (بیش از 80% در پایین)
        if (o_i - c_i) / range_i >= (1 - ORDER_BLOCK_THRESHOLD):
            ob_zone_low = l_i
            ob_zone_high = h_i
            if ob_zone_low <= current_price <= ob_zone_high:
                return True, "Bearish Order Block", ob_zone_low

    return False, "", None

def check_sr_orderblock(symbol: str) -> Tuple[str, Optional[float], List[float], List[float], bool, str, Optional[float]]:
    """بررسی کف/سقف و Order Block برای یک نماد"""
    candles = fetch_candles(symbol)
    if not candles or len(candles) < 20:
        return symbol, None, [], [], False, "", None

    # حذف کندل ناقص
    valid_candles = candles[1:]
    valid_candles.reverse()
    current_price = float(valid_candles[-1][4])

    # یافتن کف و سقف
    supports, resistances = find_support_resistance(valid_candles)

    # تشخیص Order Block
    ob_detected, ob_type, ob_price = detect_order_block(valid_candles)

    return symbol, current_price, supports, resistances, ob_detected, ob_type, ob_price

def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR} تا {ACTIVE_END_HOUR} به وقت ایران).")
        return

    alerts = []
    print(f"🔍 شروع اسکن {len(PAIRS)} نماد در تایم‌فریم {INTERVAL} دقیقه...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_sr_orderblock, PAIRS))

        for (symbol, current_price, supports, resistances, ob_detected, ob_type, ob_price) in results:
            if not current_price:
                continue

            # چک کف و سقف
            if supports or resistances:
                sr_alerts = []
                for s in supports:
                    sr_alerts.append(f"کف در <code>{s:.4f}</code>")
                for r in resistances:
                    sr_alerts.append(f"سقف در <code>{r:.4f}</code>")
                if sr_alerts:
                    alert_msg = f"<b>{symbol}</b> (قیمت: <code>{current_price:.4f}</code>): نزدیک به " + " | ".join(sr_alerts)
                    alerts.append(alert_msg)
                    print(f"✅ {symbol}: نزدیک به کف/سقف")

            # چک Order Block
            if ob_detected:
                ob_alert = f"<b>{symbol}</b> (قیمت: <code>{current_price:.4f}</code>): {ob_type} در <code>{ob_price:.4f}</code>"
                alerts.append(ob_alert)
                print(f"✅ {symbol}: {ob_type} شناسایی شد")

    if not alerts:
        print("ℹ️ هیچ سیگنالی یافت نشد.")
        return

    final_message = (
        "<b>🎯 سیگنال کف/سقف و Order Block (5 دقیقه) 🎯</b>\n"
        f"📊 تایم‌فریم: {INTERVAL} دقیقه | نمادهای اسکن شده: {len(PAIRS)}\n"
        f"🔍 آستانه نزدیک بودن: {THRESHOLD*100:.1f}% | Order Block: بدنه ≥ {int((1-ORDER_BLOCK_THRESHOLD)*100)}% رنج\n\n"
    ) + "\n".join([f"• {alert}" for alert in alerts])

    print("\n----- پیام نهایی -----\n" + final_message)
    if send_telegram_message(final_message):
        print("✅ پیام با موفقیت به تلگرام ارسال شد.")
    else:
        print("❌ ارسال پیام به تلگرام ناموفق بود.")

if __name__ == "__main__":
    main()
