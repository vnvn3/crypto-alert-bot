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
# تنظیمات
# ==========================================================
INTERVAL = "5"
KLINE_LIMIT = 200
TOP_N_SYMBOLS = 200
MIN_VOL_USD_24H = 3_000_000

# --- کف/سقف و سوئینگ ---
PROXIMITY_PCT = 0.0025
SWING_LEFT = 3
SWING_RIGHT = 3
MAX_SWING_AGE = 150
MIN_SWING_DEPTH_PCT = 0.006
MIN_SWING_GAP = 5

# ==========================================================
# >>> تنظیمات Order Block (بازنویسی‌شده) <<<
# ==========================================================
OB_IMPULSE_MULTIPLIER = 2.0   # بدنه ایمپالس ≥ ۲ برابر میانگین
OB_LOOKBACK = 120             # محدوده جستجوی OB
OB_MAX_AGE = 80               # OB قدیمی‌تر از این کاملاً نادیده گرفته شود
OB_MIN_AGE = 2

# --- «خیلی نزدیک» یعنی چقدر؟ ---
OB_NEAR_PCT_MIN = 0.0010      # حداقل آستانه: 0.10%
OB_NEAR_PCT_MAX = 0.0035      # حداکثر آستانه: 0.35%
OB_NEAR_ATR_MULT = 0.45       # آستانه پویا = 0.45 × ATR (بین دو مقدار بالا clamp می‌شود)

# --- فقط لمس تازه گزارش شود ---
OB_FRESH_LOOKBACK = 4         # اگر در N کندل اخیر هم نزدیک بوده → تکراری است
OB_REQUIRE_FRESH = True       # False کنید تا هر بار داخل زون بودن هم گزارش شود
OB_ONLY_NEAREST = True        # فقط نزدیک‌ترین OB هر جهت گزارش شود

# --- فیلتر کیفیت ---
MIN_ATR_PCT = 0.05
MAX_SIGNALS_PER_SYMBOL = 3

# --- ضد تکرار ---
ENABLE_DEDUP = True
STATE_FILE = "sr_ob_state.json"
DEDUP_COOLDOWN_MIN = 60

# --- شبکه ---
MAX_WORKERS = 6
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RATE_LIMIT_PER_SEC = 15
TELEGRAM_MAX_LEN = 4000

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
# ابزارها
# ==========================================================
def rate_limit():
    with _rate_lock:
        now = time.time()
        _req_times[:] = [t for t in _req_times if now - t < 1.0]
        if len(_req_times) >= RATE_LIMIT_PER_SEC:
            w = 1.0 - (now - _req_times[0])
            if w > 0:
                time.sleep(w)
        _req_times.append(time.time())


def safe_div(a, b, default=0.0):
    try:
        if not b:
            return default
        return a / b
    except (TypeError, ZeroDivisionError):
        return default


def pct_diff(a, b):
    if b <= 0:
        return 999.0
    return abs(a - b) / b


def is_within_active_hours():
    return ACTIVE_START_HOUR <= datetime.now(IRAN_TZ).hour < ACTIVE_END_HOUR


def send_telegram_message(message):
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        print("🚨 BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id, "text": message,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=15)
        if r.status_code != 200:
            print(f"❌ تلگرام {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"❌ خطای تلگرام: {e}")
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


def load_state():
    if not ENABLE_DEDUP:
        return {}
    try:
        with open(STATE_FILE) as f:
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
    return last is not None and (now_ts - last) < DEDUP_COOLDOWN_MIN * 60


# ==========================================================
# دریافت داده
# ==========================================================
def get_top_symbols():
    try:
        rate_limit()
        r = session.get("https://www.okx.com/api/v5/market/tickers?instType=SWAP",
                        timeout=15)
        data = r.json()
        if data.get("code") != "0":
            return []
        rows = []
        for t in data.get("data", []):
            inst = t.get("instId", "")
            if not inst.endswith("-USDT-SWAP"):
                continue
            try:
                last = float(t.get("last") or 0)
                vol = float(t.get("volCcy24h") or 0) * last
            except ValueError:
                continue
            if vol < MIN_VOL_USD_24H or last <= 0:
                continue
            rows.append((inst, vol))
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
            d = r.json()
            if d.get("code") != "0":
                return None
            return d.get("data", [])
        except requests.exceptions.RequestException:
            time.sleep(1 + attempt)
    return None


# ==========================================================
# سوئینگ‌ها
# ==========================================================
def find_swings(highs, lows):
    sh, sl = [], []
    n = len(highs)
    if n < SWING_LEFT + SWING_RIGHT + 2:
        return sh, sl
    for i in range(SWING_LEFT, n - SWING_RIGHT):
        a, b = i - SWING_LEFT, i + SWING_RIGHT + 1
        h = highs[i]
        if h > 0 and all(highs[j] < h for j in range(a, b) if j != i):
            sh.append((i, h))
        l = lows[i]
        if l > 0 and all(lows[j] > l for j in range(a, b) if j != i):
            sl.append((i, l))
    return sh, sl


# ==========================================================
# Order Block ها (کشف زون‌های معتبر)
# ==========================================================
def find_order_blocks(opens, highs, lows, closes):
    n = len(closes)
    if n < 30:
        return []

    bodies = [abs(closes[i] - opens[i]) for i in range(n)]
    win = bodies[-60:] if n >= 60 else bodies
    avg_body = safe_div(sum(win), len(win))
    if avg_body <= 0:
        return []

    # suffix min/max برای چک mitigation در O(n)
    smin = [float("inf")] * (n + 1)
    smax = [float("-inf")] * (n + 1)
    for i in range(n - 1, -1, -1):
        smin[i] = min(lows[i], smin[i + 1])
        smax[i] = max(highs[i], smax[i + 1])

    obs = []
    start = max(1, n - OB_LOOKBACK)
    for i in range(start, n - 2):
        if bodies[i + 1] < avg_body * OB_IMPULSE_MULTIPLIER:
            continue
        z_low, z_high = lows[i], highs[i]
        if z_high <= z_low or z_low <= 0:
            continue

        # Bullish OB
        if closes[i] < opens[i] and closes[i + 1] > opens[i + 1] and closes[i + 1] > highs[i]:
            if smin[i + 2] >= z_low:          # هنوز شکسته نشده
                obs.append(("BULLISH", z_low, z_high, i))

        # Bearish OB
        if closes[i] > opens[i] and closes[i + 1] < opens[i + 1] and closes[i + 1] < lows[i]:
            if smax[i + 2] <= z_high:
                obs.append(("BEARISH", z_low, z_high, i))
    return obs


# ==========================================================
# >>> ارزیابی نزدیکی به OB — بخش اصلی بازنویسی‌شده <<<
# ==========================================================
def evaluate_ob(ob, price, highs, lows, n, near_thr):
    """
    فقط دو حالت را قبول می‌کند:
      A) قیمت داخل زون است (رسیده)  → state = "inside"
      B) قیمت خیلی نزدیک زون است و از سمت درست نزدیک می‌شود → state = "approach"

    خروجی: dict یا None
    """
    ob_type, z_low, z_high, idx = ob
    age = n - 1 - idx
    if age < OB_MIN_AGE or age > OB_MAX_AGE:
        return None
    if z_low <= 0 or z_high <= z_low or price <= 0:
        return None

    inside = z_low <= price <= z_high

    if ob_type == "BULLISH":
        # زون حمایتی: قیمت باید بالای زون باشد و به سمت پایین بیاید
        if inside:
            state, dist = "inside", 0.0
        elif price > z_high:
            dist = (price - z_high) / price
            if dist > near_thr:
                return None                 # هنوز خیلی دور است
            state = "approach"
        else:
            return None                     # قیمت زیر زون → باطل شده
    else:  # BEARISH
        if inside:
            state, dist = "inside", 0.0
        elif price < z_low:
            dist = (z_low - price) / price
            if dist > near_thr:
                return None
            state = "approach"
        else:
            return None                     # قیمت بالای زون → باطل شده

    # ---- چک «لمس تازه»: در کندل‌های اخیر نباید قبلاً نزدیک/داخل بوده باشد ----
    if OB_REQUIRE_FRESH and n > OB_FRESH_LOOKBACK + 1:
        pad_low = z_low * (1 - near_thr)
        pad_high = z_high * (1 + near_thr)
        for k in range(n - 1 - OB_FRESH_LOOKBACK, n - 1):
            if k < 0:
                continue
            # اگر کندل قبلی هم با زون همپوشانی داشته → این لمس تازه نیست
            if lows[k] <= pad_high and highs[k] >= pad_low:
                return None

    return {"type": ob_type, "low": z_low, "high": z_high,
            "age": age, "state": state, "dist": dist}


# ==========================================================
# بررسی یک نماد
# ==========================================================
def check_symbol(inst_id):
    try:
        candles = fetch_candles(inst_id)
        if not candles:
            return inst_id, None
        closed = [c for c in candles if c and c[-1] == "1"]
        closed.reverse()
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

        atr = safe_div(sum(highs[-14:][k] - lows[-14:][k] for k in range(14)), 14)
        atr_pct = safe_div(atr, price) * 100
        if atr_pct < MIN_ATR_PCT:
            return inst_id, None

        # آستانه نزدیکی پویا بر اساس نوسان نماد
        near_thr = (atr_pct / 100) * OB_NEAR_ATR_MULT
        near_thr = max(OB_NEAR_PCT_MIN, min(OB_NEAR_PCT_MAX, near_thr))

        signals = []

        # ---------- سقف/کف محدوده ----------
        rh, rl = max(highs[:-1]), min(lows[:-1])
        if rh > 0 and pct_diff(price, rh) <= PROXIMITY_PCT:
            signals.append(("⛰", f"نزدیک <b>سقف محدوده</b> ({rh:.6g})", 3))
        if rl > 0 and pct_diff(price, rl) <= PROXIMITY_PCT:
            signals.append(("🕳", f"نزدیک <b>کف محدوده</b> ({rl:.6g})", 3))

        # ---------- سوئینگ قبلی ----------
        sh, sl = find_swings(highs, lows)
        for idx, lvl in reversed(sh):
            age = n - 1 - idx
            if age > MAX_SWING_AGE or age < MIN_SWING_GAP:
                continue
            if pct_diff(price, lvl) > PROXIMITY_PCT:
                continue
            if safe_div(lvl - min(lows[idx + 1:]), lvl) >= MIN_SWING_DEPTH_PCT:
                signals.append(("🔴", f"رسیدن به <b>سقف قبلی</b> ({lvl:.6g})", 2))
                break
        for idx, lvl in reversed(sl):
            age = n - 1 - idx
            if age > MAX_SWING_AGE or age < MIN_SWING_GAP:
                continue
            if pct_diff(price, lvl) > PROXIMITY_PCT:
                continue
            if safe_div(max(highs[idx + 1:]) - lvl, lvl) >= MIN_SWING_DEPTH_PCT:
                signals.append(("🟢", f"رسیدن به <b>کف قبلی</b> ({lvl:.6g})", 2))
                break

        # ---------- Order Block ----------
        hits = []
        for ob in find_order_blocks(opens, highs, lows, closes):
            ev = evaluate_ob(ob, price, highs, lows, n, near_thr)
            if ev:
                hits.append(ev)

        if hits and OB_ONLY_NEAREST:
            best = {}
            for h in hits:
                cur = best.get(h["type"])
                if cur is None or h["dist"] < cur["dist"]:
                    best[h["type"]] = h
            hits = list(best.values())

        for h in hits:
            bullish = h["type"] == "BULLISH"
            emoji = "🟩" if bullish else "🟥"
            label = "حمایتی" if bullish else "مقاومتی"
            if h["state"] == "inside":
                status = "✅ <b>رسید (داخل زون)</b>"
                prio = 1
            else:
                status = f"⏳ <b>در آستانه</b> (فاصله {h['dist'] * 100:.2f}%)"
                prio = 1 if h["dist"] <= near_thr / 2 else 2
            signals.append((emoji,
                            f"OB {label} — {status}\n"
                            f"      زون: <code>{h['low']:.6g} – {h['high']:.6g}</code>",
                            prio))

        if not signals:
            return inst_id, None

        signals.sort(key=lambda x: x[2])
        return inst_id, {"price": price, "atr_pct": atr_pct,
                         "signals": signals[:MAX_SIGNALS_PER_SYMBOL]}

    except Exception as e:
        print(f"❌ {inst_id}: {type(e).__name__} -> {e}")
        return inst_id, None


# ==========================================================
# main
# ==========================================================
def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR}-{ACTIVE_END_HOUR}).")
        return

    t0 = time.time()
    symbols = get_top_symbols()
    if not symbols:
        print("❌ لیست نمادها خالی است.")
        return

    print(f"🔍 اسکن {len(symbols)} نماد | تایم {INTERVAL}m ...")
    state = load_state()
    now_ts = time.time()
    found, errors = [], 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(check_symbol, s): s for s in symbols}
        for fut in concurrent.futures.as_completed(futs):
            try:
                inst_id, res = fut.result()
            except Exception as e:
                errors += 1
                print(f"❌ thread: {e}")
                continue
            if not res:
                continue
            name = inst_id.replace("-USDT-SWAP", "")
            fresh = []
            for emoji, text, prio in res["signals"]:
                key = f"{name}|{text[:45]}"
                if is_duplicate(state, key, now_ts):
                    continue
                state[key] = now_ts
                fresh.append((emoji, text, prio))
            if fresh:
                found.append((min(p for _, _, p in fresh), name,
                              res["price"], res["atr_pct"], fresh))
                print(f"✅ {name}: {len(fresh)} سیگنال")

    cutoff = now_ts - DEDUP_COOLDOWN_MIN * 180
    save_state({k: v for k, v in state.items() if v > cutoff})
    print(f"⏱ {time.time() - t0:.1f}s | خطا: {errors}")

    if not found:
        print("ℹ️ هیچ سیگنال جدیدی یافت نشد.")
        return

    found.sort(key=lambda x: x[0])
    now_iran = datetime.now(IRAN_TZ).strftime("%H:%M")
    lines = [f"🎯 <b>اسکنر Order Block و سطوح</b>",
             f"⏱ {INTERVAL}m | 🕐 {now_iran} | 🔍 {len(symbols)} نماد | ✅ {len(found)}",
             ""]
    for _, name, price, atr_pct, sigs in found:
        lines.append(f"💠 <b>{html.escape(name)}</b> | <code>{price:.6g}</code> "
                     f"| نوسان {atr_pct:.2f}%")
        for emoji, text, _ in sigs:
            lines.append(f"   {emoji} {text}")
        lines.append("")

    msg = "\n".join(lines)
    print("\n----- پیام نهایی -----\n" + msg)
    print("✅ ارسال شد." if send_long_message(msg) else "❌ ارسال ناموفق.")


if __name__ == "__main__":
    main()
