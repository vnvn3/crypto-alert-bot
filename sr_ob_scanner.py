import requests
import os
import html
import json
import time
import random
import threading
import concurrent.futures
from datetime import datetime, timezone, timedelta

# ==========================================================
# تنظیمات اصلی
# ==========================================================
INTERVAL = "5"                  # تایم‌فریم ۵ دقیقه
KLINE_LIMIT = 200               # کندل بیشتر برای سوئینگ و OB
TOP_N_SYMBOLS = 200             # تعداد نماد پرحجم
MIN_VOL_USD_24H = 3_000_000     # حداقل حجم ۲۴ ساعته (فیلتر نماد مرده)

# --- حساسیت سطوح ---
PROXIMITY_PCT = 0.0030          # 0.30% فاصله = «نزدیک سطح»
OB_PROXIMITY_PCT = 0.0045       # نزدیکی به مرکز زون Order Block

# --- سوئینگ ---
SWING_LEFT = 3
SWING_RIGHT = 3
MAX_SWING_AGE = 150             # سوئینگ قدیمی‌تر از این نادیده گرفته شود
MIN_SWING_DEPTH_PCT = 0.006     # عمق حرکت بعد از سوئینگ حداقل 0.6%
MIN_SWING_TOUCHES_GAP = 5       # حداقل فاصله کندلی بین سوئینگ و الان

# --- Order Block ---
OB_IMPULSE_MULTIPLIER = 2.0     # بدنه ایمپالس ≥ ۲ برابر میانگین بدنه
OB_LOOKBACK = 120               # محدوده جستجوی OB
OB_MAX_AGE = 120                # OB قدیمی‌تر از این نادیده گرفته شود
OB_MIN_AGE = 3                  # OB تازه‌تر از این نادیده گرفته شود
MAX_OB_PER_SIDE = 2             # حداکثر OB گزارش‌شده در هر جهت

# --- فیلتر کیفیت ---
MIN_ATR_PCT = 0.05              # حداقل نوسان میانگین (٪) تا نماد کم‌جان رد شود
MAX_SIGNALS_PER_SYMBOL = 3      # حداکثر سیگنال گزارش‌شده برای هر نماد

# --- ضد تکرار ---
ENABLE_DEDUP = True
STATE_FILE = "sr_ob_state.json"
DEDUP_COOLDOWN_MIN = 90         # تا این مدت سیگنال مشابه دوباره ارسال نشود

# --- شبکه ---
MAX_WORKERS = 6
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RATE_LIMIT_PER_SEC = 15
TELEGRAM_MAX_LEN = 4000

# --- ساعت فعال ---
ACTIVE_START_HOUR = 7
ACTIVE_END_HOUR = 23
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

BAR_MAP = {"1": "1m", "3": "3m", "5": "5m", "15": "15m",
           "30": "30m", "60": "1H", "240": "4H", "D": "1Dutc"}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

_rate_lock = threading.Lock()
_req_times = []


# ==========================================================
# ابزارهای پایه
# ==========================================================
def rate_limit():
    """حداکثر RATE_LIMIT_PER_SEC درخواست در ثانیه — جلوگیری از HTTP 429."""
    with _rate_lock:
        now = time.time()
        _req_times[:] = [t for t in _req_times if now - t < 1.0]
        if len(_req_times) >= RATE_LIMIT_PER_SEC:
            wait = 1.0 - (now - _req_times[0])
            if wait > 0:
                time.sleep(wait)
        _req_times.append(time.time())


def safe_div(a, b, default=0.0):
    try:
        if not b:
            return default
        return a / b
    except (TypeError, ZeroDivisionError):
        return default


def pct_diff(a, b):
    """اختلاف نسبی امن بین دو قیمت."""
    if b <= 0:
        return 999.0
    return abs(a - b) / b


def is_within_active_hours():
    return ACTIVE_START_HOUR <= datetime.now(IRAN_TZ).hour < ACTIVE_END_HOUR


# ==========================================================
# تلگرام
# ==========================================================
def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        print("🚨 BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15)
        if r.status_code != 200:
            print(f"❌ تلگرام {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"❌ خطای شبکه تلگرام: {e}")
        return False


def send_long_message(text):
    ok, chunk = True, ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > TELEGRAM_MAX_LEN:
            ok &= send_telegram_message(chunk)
            chunk = ""
            time.sleep(1)
        chunk += line + "\n"
    if chunk.strip():
        ok &= send_telegram_message(chunk)
    return ok


# ==========================================================
# ضد تکرار (اختیاری - نیاز به cache در Actions)
# ==========================================================
def load_state():
    if not ENABLE_DEDUP:
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    if not ENABLE_DEDUP:
        return
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"⚠️ ذخیره state ناموفق: {e}")


def is_duplicate(state, key, now_ts):
    if not ENABLE_DEDUP:
        return False
    last = state.get(key)
    if last is None:
        return False
    return (now_ts - last) < DEDUP_COOLDOWN_MIN * 60


# ==========================================================
# دریافت لیست نمادهای معتبر و پرحجم از OKX
# ==========================================================
def get_top_symbols():
    try:
        rate_limit()
        r = session.get("https://www.okx.com/api/v5/market/tickers?instType=SWAP",
                        timeout=15)
        data = r.json()
        if data.get("code") != "0":
            print(f"⚠️ خطا در tickers: {data.get('msg')}")
            return []
        rows = []
        for t in data.get("data", []):
            inst = t.get("instId", "")
            if not inst.endswith("-USDT-SWAP"):
                continue
            try:
                last = float(t.get("last") or 0)
                vol_usd = float(t.get("volCcy24h") or 0) * last
            except ValueError:
                continue
            if vol_usd < MIN_VOL_USD_24H or last <= 0:
                continue
            rows.append((inst, vol_usd))
        rows.sort(key=lambda x: x[1], reverse=True)
        sel = [i for i, _ in rows[:TOP_N_SYMBOLS]]
        print(f"📋 {len(sel)} نماد معتبر دریافت شد.")
        return sel
    except Exception as e:
        print(f"❌ get_top_symbols: {e}")
        return []


def fetch_candles(inst_id):
    bar = BAR_MAP.get(INTERVAL, "5m")
    url = (f"https://www.okx.com/api/v5/market/candles"
           f"?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}")
    for attempt in range(MAX_RETRIES):
        try:
            rate_limit()
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                time.sleep((2 ** attempt) + random.uniform(0.3, 1.0))
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
# ۱) سوئینگ‌های چرخشی (کف/سقف قبلی) — بهینه‌شده
# ==========================================================
def find_swings(highs, lows):
    """
    فرکتال ساده: کندلی که سقف/کف آن در پنجره چپ+راست یکتا و اکسترمم باشد.
    خروجی: (لیست سوئینگ‌های، لیست سوئینگ‌لو) به‌صورت (index, price)
    """
    sh, sl = [], []
    n = len(highs)
    if n < SWING_LEFT + SWING_RIGHT + 2:
        return sh, sl

    for i in range(SWING_LEFT, n - SWING_RIGHT):
        lo_i = i - SWING_LEFT
        hi_i = i + SWING_RIGHT + 1

        h = highs[i]
        if h > 0:
            is_high = True
            for j in range(lo_i, hi_i):
                if j != i and highs[j] >= h:
                    is_high = False
                    break
            if is_high:
                sh.append((i, h))

        l = lows[i]
        if l > 0:
            is_low = True
            for j in range(lo_i, hi_i):
                if j != i and lows[j] <= l:
                    is_low = False
                    break
            if is_low:
                sl.append((i, l))
    return sh, sl


# ==========================================================
# ۲) Order Block های مصرف‌نشده — بهینه‌شده O(n)
# ==========================================================
def find_order_blocks(opens, highs, lows, closes):
    """
    Bullish OB : آخرین کندل نزولی قبل از ایمپالس صعودی که سقفش شکسته شده
    Bearish OB : آخرین کندل صعودی قبل از ایمپالس نزولی که کفش شکسته شده
    Mitigation با suffix-min/suffix-max در O(n) چک می‌شود (به‌جای O(n²)).
    """
    n = len(closes)
    if n < 30:
        return []

    bodies = [abs(closes[i] - opens[i]) for i in range(n)]
    window = bodies[-60:] if n >= 60 else bodies
    avg_body = safe_div(sum(window), len(window))
    if avg_body <= 0:
        return []

    # suffix_min_low[i] = کمترین low از i تا انتها
    suffix_min_low = [0.0] * (n + 1)
    suffix_max_high = [0.0] * (n + 1)
    suffix_min_low[n] = float("inf")
    suffix_max_high[n] = float("-inf")
    for i in range(n - 1, -1, -1):
        suffix_min_low[i] = min(lows[i], suffix_min_low[i + 1])
        suffix_max_high[i] = max(highs[i], suffix_max_high[i + 1])

    bulls, bears = [], []
    start = max(1, n - OB_LOOKBACK)

    for i in range(start, n - 2):
        body_imp = bodies[i + 1]
        if body_imp < avg_body * OB_IMPULSE_MULTIPLIER:
            continue

        z_low, z_high = lows[i], highs[i]
        if z_high <= z_low or z_low <= 0:
            continue

        # --- Bullish OB ---
        if closes[i] < opens[i] and closes[i + 1] > opens[i + 1] \
                and closes[i + 1] > highs[i]:
            # اگر بعداً قیمت زیر کف زون رفته باشد، OB باطل است
            if suffix_min_low[i + 2] >= z_low:
                bulls.append((z_low, z_high, i))

        # --- Bearish OB ---
        if closes[i] > opens[i] and closes[i + 1] < opens[i + 1] \
                and closes[i + 1] < lows[i]:
            if suffix_max_high[i + 2] <= z_high:
                bears.append((z_low, z_high, i))

    # فقط جدیدترین OB ها را نگه دار
    bulls = bulls[-MAX_OB_PER_SIDE:]
    bears = bears[-MAX_OB_PER_SIDE:]

    out = [("BULLISH", *b) for b in bulls] + [("BEARISH", *b) for b in bears]
    return out


# ==========================================================
# بررسی یک نماد
# ==========================================================
def check_symbol(inst_id):
    try:
        candles = fetch_candles(inst_id)
        if not candles:
            return inst_id, None

        closed = [c for c in candles if c and c[-1] == "1"]
        closed.reverse()  # قدیمی → جدید
        if len(closed) < 60:
            return inst_id, None

        try:
            opens = [float(c[1]) for c in closed]
            highs = [float(c[2]) for c in closed]
            lows = [float(c[3]) for c in closed]
            closes = [float(c[4]) for c in closed]
        except ValueError:
            return inst_id, None

        n = len(closes)
        price = closes[-1]
        if price <= 0:
            return inst_id, None

        # --- فیلتر نوسان: نمادهای بی‌جان رد شوند ---
        atr = safe_div(sum(highs[-14:][k] - lows[-14:][k] for k in range(14)), 14)
        atr_pct = safe_div(atr, price) * 100
        if atr_pct < MIN_ATR_PCT:
            return inst_id, None

        signals = []

        # ---------- ۱) سقف / کف محدوده ----------
        range_high = max(highs[:-1])
        range_low = min(lows[:-1])

        if range_high > 0 and pct_diff(price, range_high) <= PROXIMITY_PCT:
            signals.append(("⛰", f"نزدیک <b>سقف محدوده</b> ({range_high:.6g})", 3))
        if range_low > 0 and pct_diff(price, range_low) <= PROXIMITY_PCT:
            signals.append(("🕳", f"نزدیک <b>کف محدوده</b> ({range_low:.6g})", 3))

        # ---------- ۲) سوئینگ قبلی ----------
        sh, sl = find_swings(highs, lows)

        # نزدیک‌ترین سوئینگ‌های معتبر (از جدید به قدیم)
        for idx, lvl in reversed(sh):
            age = n - 1 - idx
            if age > MAX_SWING_AGE or age < MIN_SWING_TOUCHES_GAP:
                continue
            if pct_diff(price, lvl) > PROXIMITY_PCT:
                continue
            depth = safe_div(lvl - min(lows[idx + 1:]), lvl)
            if depth >= MIN_SWING_DEPTH_PCT:
                signals.append(("🔴", f"رسیدن به <b>سقف قبلی</b> ({lvl:.6g}) — {age} کندل پیش", 2))
                break

        for idx, lvl in reversed(sl):
            age = n - 1 - idx
            if age > MAX_SWING_AGE or age < MIN_SWING_TOUCHES_GAP:
                continue
            if pct_diff(price, lvl) > PROXIMITY_PCT:
                continue
            depth = safe_div(max(highs[idx + 1:]) - lvl, lvl)
            if depth >= MIN_SWING_DEPTH_PCT:
                signals.append(("🟢", f"رسیدن به <b>کف قبلی</b> ({lvl:.6g}) — {age} کندل پیش", 2))
                break

        # ---------- ۳) Order Block ----------
        for ob_type, z_low, z_high, idx in find_order_blocks(opens, highs, lows, closes):
            age = n - 1 - idx
            if age < OB_MIN_AGE or age > OB_MAX_AGE:
                continue
            z_mid = (z_low + z_high) / 2
            if z_mid <= 0:
                continue
            in_zone = z_low <= price <= z_high
            near_zone = pct_diff(price, z_mid) <= OB_PROXIMITY_PCT
            if not (in_zone or near_zone):
                continue
            emoji = "🟩" if ob_type == "BULLISH" else "🟥"
            tag = "داخل زون" if in_zone else "نزدیک زون"
            label = "حمایتی" if ob_type == "BULLISH" else "مقاومتی"
            signals.append((emoji,
                            f"<b>Order Block {label}</b> ({tag}) "
                            f"[{z_low:.6g} – {z_high:.6g}] — {age} کندل پیش",
                            1 if in_zone else 2))

        if not signals:
            return inst_id, None

        # اولویت‌بندی: اهمیت بیشتر (عدد کمتر) اول
        signals.sort(key=lambda x: x[2])
        signals = signals[:MAX_SIGNALS_PER_SYMBOL]

        return inst_id, {"price": price, "atr_pct": atr_pct, "signals": signals}

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

    print(f"🔍 اسکن {len(symbols)} نماد | تایم {INTERVAL}m | کف/سقف + Order Block ...")

    state = load_state()
    now_ts = time.time()
    found = []
    errors = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(check_symbol, s): s for s in symbols}
        for fut in concurrent.futures.as_completed(futures):
            try:
                inst_id, res = fut.result()
            except Exception as e:
                errors += 1
                print(f"❌ thread: {e}")
                continue
            if not res:
                continue

            name = inst_id.replace("-USDT-SWAP", "")

            # فیلتر ضد تکرار روی هر سیگنال
            fresh = []
            for emoji, text, prio in res["signals"]:
                key = f"{name}|{text[:40]}"
                if is_duplicate(state, key, now_ts):
                    continue
                state[key] = now_ts
                fresh.append((emoji, text, prio))

            if fresh:
                best_prio = min(p for _, _, p in fresh)
                found.append((best_prio, name, res["price"], res["atr_pct"], fresh))
                print(f"✅ {name}: {len(fresh)} سیگنال")

    # پاکسازی state قدیمی
    cutoff = now_ts - DEDUP_COOLDOWN_MIN * 60 * 3
    state = {k: v for k, v in state.items() if v > cutoff}
    save_state(state)

    print(f"⏱ زمان اسکن: {time.time() - t0:.1f}s | خطا: {errors}")

    if not found:
        print("ℹ️ هیچ سیگنال جدیدی یافت نشد.")
        return

    found.sort(key=lambda x: x[0])  # مهم‌ترین‌ها اول

    now_iran = datetime.now(IRAN_TZ).strftime("%H:%M")
    lines = [
        f"🎯 <b>اسکنر کف/سقف و Order Block</b>",
        f"⏱ تایم {INTERVAL}m | 🕐 {now_iran} | 🔍 {len(symbols)} نماد | ✅ {len(found)} نتیجه",
        "",
    ]
    for _, name, price, atr_pct, sigs in found:
        lines.append(f"💠 <b>{html.escape(name)}</b> | <code>{price:.6g}</code> "
                     f"| نوسان: {atr_pct:.2f}%")
        for emoji, text, _ in sigs:
            lines.append(f"   {emoji} {text}")
        lines.append("")

    msg = "\n".join(lines)
    print("\n----- پیام نهایی -----\n" + msg)

    if send_long_message(msg):
        print("✅ ارسال شد.")
    else:
        print("❌ ارسال ناموفق.")


if __name__ == "__main__":
    main()
