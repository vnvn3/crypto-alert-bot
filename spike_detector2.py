import requests
import os
import html
import time
import random
import threading
import concurrent.futures
from datetime import datetime, timezone, timedelta

# ==========================================================
# تنظیمات
# ==========================================================
INTERVAL = "5"                # تایم‌فریم: 1,3,5,15,30,60,240,D
KLINE_LIMIT = 100
TOP_N_SYMBOLS = 200           # چند نماد پرحجم اسکن شود (بر اساس حجم 24h)
MIN_VOL_USD_24H = 2_000_000   # حداقل حجم دلاری 24 ساعته (فیلتر نمادهای مرده)

SPIKE_MIN_BODY_RATIO = 0.55   # بدنه کندل اسپایک ≥ 55% رنج خودش
SPIKE_RANGE_MULTIPLIER = 2.2  # رنج اسپایک ≥ 2.2 برابر میانگین رنج اخیر
ATR_LOOKBACK = 14             # تعداد کندل برای میانگین رنج
MIN_MOVE_PCT = 0.25           # حداقل درصد حرکت بدنه اسپایک (فیلتر نویز)

MAX_WORKERS = 6               # ← کم شد تا 429 نگیریم
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RATE_LIMIT_PER_SEC = 15       # حداکثر درخواست در ثانیه به OKX
TELEGRAM_MAX_LEN = 4000

ACTIVE_START_HOUR = 7
ACTIVE_END_HOUR = 23
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

BAR_MAP = {"1": "1m", "3": "3m", "5": "5m", "15": "15m",
           "30": "30m", "60": "1H", "240": "4H", "D": "1Dutc"}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

# --- محدودکننده نرخ درخواست (Thread-safe) ---
_rate_lock = threading.Lock()
_last_times = []

def rate_limit():
    """اجازه نمی‌دهد بیش از RATE_LIMIT_PER_SEC درخواست در ثانیه ارسال شود."""
    with _rate_lock:
        now = time.time()
        _last_times[:] = [t for t in _last_times if now - t < 1.0]
        if len(_last_times) >= RATE_LIMIT_PER_SEC:
            sleep_for = 1.0 - (now - _last_times[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
        _last_times.append(time.time())


# ==========================================================
# ابزارها
# ==========================================================
def is_within_active_hours():
    return ACTIVE_START_HOUR <= datetime.now(IRAN_TZ).hour < ACTIVE_END_HOUR


def safe_div(a, b, default=0.0):
    """تقسیم امن — دیگر هرگز ZeroDivisionError نمی‌گیریم."""
    try:
        if b == 0 or b is None:
            return default
        return a / b
    except (TypeError, ZeroDivisionError):
        return default


def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        print("🚨 BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": message,
                                     "parse_mode": "HTML"}, timeout=15)
        if r.status_code != 200:
            print(f"❌ تلگرام {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"❌ خطای شبکه تلگرام: {e}")
        return False


def send_long_message(text):
    lines, chunk, ok = text.split("\n"), "", True
    for line in lines:
        if len(chunk) + len(line) + 1 > TELEGRAM_MAX_LEN:
            ok &= send_telegram_message(chunk)
            chunk = ""
            time.sleep(1)
        chunk += line + "\n"
    if chunk.strip():
        ok &= send_telegram_message(chunk)
    return ok


# ==========================================================
# گرفتن خودکار لیست نمادهای معتبر و پرحجم از OKX
# ==========================================================
def get_top_symbols():
    """
    لیست نمادها را مستقیم از OKX می‌گیرد:
    فقط قراردادهای دائمی USDT، مرتب‌شده بر اساس حجم دلاری 24 ساعته.
    این کار مشکل نمادهای نامعتبر / تکراری / مرده را کامل حل می‌کند.
    """
    try:
        url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
        r = session.get(url, timeout=15)
        data = r.json()
        if data.get("code") != "0":
            print(f"⚠️ خطا در دریافت لیست نمادها: {data.get('msg')}")
            return []

        rows = []
        for t in data.get("data", []):
            inst = t.get("instId", "")
            if not inst.endswith("-USDT-SWAP"):
                continue
            try:
                last = float(t.get("last") or 0)
                vol_ccy = float(t.get("volCcy24h") or 0)   # حجم برحسب ارز پایه
                vol_usd = vol_ccy * last
            except ValueError:
                continue
            if vol_usd < MIN_VOL_USD_24H:
                continue
            rows.append((inst, vol_usd))

        rows.sort(key=lambda x: x[1], reverse=True)
        selected = [inst for inst, _ in rows[:TOP_N_SYMBOLS]]
        print(f"📋 {len(selected)} نماد معتبر و پرحجم از OKX دریافت شد.")
        return selected
    except Exception as e:
        print(f"❌ خطا در get_top_symbols: {e}")
        return []


# ==========================================================
# دریافت کندل با retry و backoff برای 429
# ==========================================================
def fetch_candles(inst_id):
    bar = BAR_MAP.get(INTERVAL, "5m")
    url = (f"https://www.okx.com/api/v5/market/candles"
           f"?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}")

    for attempt in range(MAX_RETRIES):
        try:
            rate_limit()
            r = session.get(url, timeout=REQUEST_TIMEOUT)

            if r.status_code == 429:
                # backoff نمایی + jitter تا فشار روی API کم شود
                wait = (2 ** attempt) + random.uniform(0.3, 1.0)
                time.sleep(wait)
                continue

            if r.status_code != 200:
                return None

            data = r.json()
            if data.get("code") != "0":
                return None
            return data.get("data", [])

        except requests.exceptions.RequestException:
            time.sleep(1 + attempt)
    return None


# ==========================================================
# تشخیص اسپایک (کاملاً ضد تقسیم بر صفر)
# ==========================================================
def is_spike_pattern(candles):
    """
    candles: قدیمی → جدید، هر کندل [ts, o, h, l, c, ...]
    خروجی: (bool, direction, move_pct)
    """
    if len(candles) < ATR_LOOKBACK + 3:
        return False, None, 0.0

    try:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        o1, cl1 = float(c1[1]), float(c1[4])
        o2, h2, l2, cl2 = float(c2[1]), float(c2[2]), float(c2[3]), float(c2[4])
        o3, cl3 = float(c3[1]), float(c3[4])
    except (ValueError, IndexError):
        return False, None, 0.0

    body1 = abs(cl1 - o1)
    body2 = abs(cl2 - o2)
    range2 = h2 - l2

    # ---- محافظ‌های اصلی ----
    if range2 <= 0 or body2 <= 0 or o2 <= 0:
        return False, None, 0.0

    # میانگین رنج کندل‌های قبل از الگو
    prev = candles[-(ATR_LOOKBACK + 3):-3]
    if not prev:
        return False, None, 0.0
    avg_range = sum(float(c[2]) - float(c[3]) for c in prev) / len(prev)
    if avg_range <= 0:
        return False, None, 0.0

    # 1) بدنه قدرتمند نسبت به رنج خودش
    if safe_div(body2, range2) < SPIKE_MIN_BODY_RATIO:
        return False, None, 0.0

    # 2) رنج بزرگ نسبت به کندل‌های اخیر
    if safe_div(range2, avg_range) < SPIKE_RANGE_MULTIPLIER:
        return False, None, 0.0

    # 3) حرکت واقعی به درصد (فیلتر نویز نمادهای کم‌نوسان)
    move_pct = safe_div(body2, o2) * 100
    if move_pct < MIN_MOVE_PCT:
        return False, None, 0.0

    # 4) کندل قبل آرام باشد — بدون تقسیم! (ضرب به‌جای تقسیم)
    if body1 > body2 * 0.45:
        return False, None, 0.0

    # جهت + تایید کندل سوم
    if cl2 > o2:
        if cl3 <= o3:
            return False, None, 0.0
        direction = "🟢 صعودی"
    else:
        if cl3 >= o3:
            return False, None, 0.0
        direction = "🔴 نزولی"

    return True, direction, move_pct


# ==========================================================
# بررسی یک نماد
# ==========================================================
def check_spike(inst_id):
    try:
        candles = fetch_candles(inst_id)
        if not candles:
            return inst_id, None

        # فقط کندل‌های بسته‌شده (فیلد آخر confirm == "1")
        closed = [c for c in candles if c and c[-1] == "1"]
        closed.reverse()  # قدیمی → جدید

        if len(closed) < ATR_LOOKBACK + 3:
            return inst_id, None

        price = float(closed[-1][4])
        detected, direction, move_pct = is_spike_pattern(closed)

        if detected:
            return inst_id, (price, direction, move_pct)
        return inst_id, None

    except Exception as e:
        print(f"❌ {inst_id}: {type(e).__name__} -> {e}")
        return inst_id, None


# ==========================================================
# main
# ==========================================================
def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR}-{ACTIVE_END_HOUR} ایران).")
        return

    t0 = time.time()
    symbols = get_top_symbols()
    if not symbols:
        print("❌ لیست نمادها خالی است.")
        return

    print(f"🔍 اسکن {len(symbols)} نماد | تایم {INTERVAL}m ...")

    alerts = []
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(check_spike, s): s for s in symbols}
        for fut in concurrent.futures.as_completed(futures):
            try:
                inst_id, result = fut.result()
            except Exception as e:
                failed += 1
                print(f"❌ خطای thread: {e}")
                continue
            if result:
                price, direction, move_pct = result
                name = inst_id.replace("-USDT-SWAP", "")
                alerts.append((move_pct, name, price, direction))
                print(f"✅ {name}: اسپایک {direction} ({move_pct:.2f}%)")

    elapsed = time.time() - t0
    print(f"⏱ زمان اسکن: {elapsed:.1f} ثانیه | ناموفق: {failed}")

    if not alerts:
        print("ℹ️ هیچ اسپایکی یافت نشد.")
        return

    # مرتب‌سازی: قوی‌ترین اسپایک‌ها اول
    alerts.sort(reverse=True)

    now_iran = datetime.now(IRAN_TZ).strftime("%H:%M")
    lines = [
        f"🚨 <b>سیگنال اسپایک فیوچرز | تایم {INTERVAL} دقیقه</b>",
        f"🕐 ساعت {now_iran} | اسکن {len(symbols)} نماد | یافت‌شده: {len(alerts)}",
        "",
    ]
    for move_pct, name, price, direction in alerts:
        lines.append(
            f"• <b>{html.escape(name)}</b> {direction} | "
            f"قدرت: <code>{move_pct:.2f}%</code> | "
            f"قیمت: <code>{price:.6g}</code>"
        )

    msg = "\n".join(lines)
    print("\n----- پیام نهایی -----\n" + msg)

    if send_long_message(msg):
        print("✅ ارسال شد.")
    else:
        print("❌ ارسال ناموفق.")


if __name__ == "__main__":
    main()
