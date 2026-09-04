import requests
import os
import html
import concurrent.futures
from datetime import datetime, timezone, timedelta

# ---------- لیست نمادها (می‌توانید کمتر کنید اگر 429 بگیرید) ----------
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "BCHUSDT",
    "UNIUSDT", "ATOMUSDT", "TRXUSDT", "MATICUSDT", "SHIBUSDT", "SUIUSDT",
    "FETUSDT", "PEPEUSDT", "WLDUSDT", "WIFUSDT", "JUPUSDT", "ENAUSDT"
]

# ---------- تنظیمات ----------
INTERVAL = "5"
KLINE_LIMIT = 100
RSI_PERIOD = 14              # دوره RSI استاندارد
LOOKBACK_CANDLES = 40         # تعداد کندل برای بررسی دایورجنس
MAX_WORKERS = 6
REQUEST_TIMEOUT = 5

ACTIVE_START_HOUR = 7
ACTIVE_END_HOUR = 23
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# ---------- توابع پایه ----------
def is_within_active_hours() -> bool:
    return ACTIVE_START_HOUR <= datetime.now(IRAN_TZ).hour < ACTIVE_END_HOUR

def send_telegram_message(msg: str) -> bool:
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        print("🚨 BOT_TOKEN یا CHANNEL_ID تنظیم نشده!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ خطای تلگرام: {e}")
        return False

BAR_MAP = {"1":"1m","3":"3m","5":"5m","15":"15m","30":"30m","60":"1H","240":"4H","D":"1D"}

def symbol_to_okx_instid(sym: str) -> str:
    return f"{sym[:-4]}-USDT-SWAP"

# ---------- دریافت داده ----------
def fetch_candles(sym: str) -> list:
    for a in range(2):
        try:
            inst = symbol_to_okx_instid(sym)
            bar = BAR_MAP.get(INTERVAL, "5m")
            url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={bar}&limit={KLINE_LIMIT}"
            resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "0":
                    return data.get("data", [])
            if resp.status_code == 429:
                print(f"⚠️ {sym}: Rate Limit 429")
        except Exception as e:
            print(f"❌ {sym}: خطا -> {e}")
    return None

# ---------- محاسبه RSI ----------
def calculate_rsi(prices: list, period: int = 14) -> list:
    """
    محاسبه RSI با روش SMA (ساده و سریع)
    محافظت شده در برابر تقسیم بر صفر
    """
    if len(prices) < period + 1:
        return []
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi_vals = []
    # اولین مقدار RSI
    if avg_loss == 0:
        rsi_vals.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_vals.append(100.0 - (100.0 / (1.0 + rs)))
    
    # ادامه محاسبه
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi_vals.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_vals.append(100.0 - (100.0 / (1.0 + rs)))
    
    return rsi_vals

# ---------- تشخیص دایورجنس ----------
def check_divergence(candles: list, period: int = RSI_PERIOD) -> tuple:
    """
    بررسی دایورجنس صعودی و نزولی RSI در دو نیمه اخیر
    برمی‌گرداند: (پیدا شد؟, نوع دایورجنس, قیمت فعلی, RSI فعلی)
    """
    if not candles or len(candles) < LOOKBACK_CANDLES + period:
        return False, None, None, None
    
    # استخراج قیمت‌های بسته شدن (بدون کندل ناقص)
    # کندل اول (index 0) در OKX ناقص است → از index 1 شروع می‌کنیم
    valid_candles = candles[1:]
    valid_candles.reverse()  # قدیم به جدید
    
    # فقط آخرین LOOKBACK_CANDLES کندل معتبر
    recent = valid_candles[:LOOKBACK_CANDLES]
    closes = [float(c[4]) for c in recent]
    
    if len(closes) < period + 15:
        return False, None, None, None
    
    rsi_vals = calculate_rsi(closes, period)
    if not rsi_vals or len(rsi_vals) < 10:
        return False, None, None, None
    
    # RSI در index i مربوط به closes[i + period] است
    # بنابراین برای مقایسه دقیق، از closes[period:] و rsi_vals استفاده می‌کنیم
    valid_closes = closes[period:]
    valid_rsi = rsi_vals
    
    # تقسیم به دو نیمه: قدیمی و جدید
    split = len(valid_closes) // 2
    if split < 3:
        return False, None, None, None
    
    older_prices = valid_closes[:split]
    newer_prices = valid_closes[split:]
    older_rsi = valid_rsi[:split]
    newer_rsi = valid_rsi[split:]
    
    current_price = closes[-1]
    current_rsi = valid_rsi[-1] if valid_rsi else 50
    
    # --- دایورجنس صعودی (Bullish) ---
    # قیمت: کف جدید < کف قدیم
    # RSI: کف جدید > کف قدیم
    old_min_p = min(older_prices)
    new_min_p = min(newer_prices)
    old_min_idx = older_prices.index(old_min_p)
    new_min_idx = newer_prices.index(new_min_p)
    old_min_rsi = older_rsi[old_min_idx]
    new_min_rsi = newer_rsi[new_min_idx]
    
    if new_min_p < old_min_p and new_min_rsi > old_min_rsi:
        return True, "📈 Bullish Divergence", current_price, current_rsi
    
    # --- دایورجنس نزولی (Bearish) ---
    # قیمت: سقف جدید > سقف قدیم
    # RSI: سقف جدید < سقف قدیم
    old_max_p = max(older_prices)
    new_max_p = max(newer_prices)
    old_max_idx = older_prices.index(old_max_p)
    new_max_idx = newer_prices.index(new_max_p)
    old_max_rsi = older_rsi[old_max_idx]
    new_max_rsi = newer_rsi[new_max_idx]
    
    if new_max_p > old_max_p and new_max_rsi < old_max_rsi:
        return True, "📉 Bearish Divergence", current_price, current_rsi
    
    return False, None, current_price, current_rsi

# ---------- پردازش هر نماد ----------
def check_symbol(sym: str) -> tuple:
    candles = fetch_candles(sym)
    if not candles or len(candles) < LOOKBACK_CANDLES + RSI_PERIOD:
        return sym, None, False, None, None
    
    diverged, div_type, price, rsi_now = check_divergence(candles)
    return sym, price, diverged, div_type, rsi_now

# ---------- اصلی ----------
def main():
    if not is_within_active_hours():
        print(f"⏸️ خارج از بازه فعال ({ACTIVE_START_HOUR}-{ACTIVE_END_HOUR} به وقت ایران).")
        return
    
    alerts = []
    print(f"🔍 اسکن دایورجنس RSI ({RSI_PERIOD}) در تایم‌فریم {INTERVAL} دقیقه...")
    print(f"🔍 تعداد نماد: {len(PAIRS)} | کارگر: {MAX_WORKERS}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_symbol, PAIRS))
        
        for sym, price, diverged, div_type, rsi_now in results:
            if not diverged or price is None:
                continue
            
            msg_line = (
                f"<b>{sym}</b>: {div_type} شناسایی شد!\n"
                f"💰 قیمت فعلی: <code>{price:.4f}</code>\n"
                f"📊 RSI فعلی: <code>{rsi_now:.2f}</code>"
            )
            alerts.append(msg_line)
            print(f"✅ {sym}: {div_type} | قیمت: {price:.4f} | RSI: {rsi_now:.2f}")
    
    if not alerts:
        print("ℹ️ هیچ دایورجنسی یافت نشد.")
        return
    
    header = (
        "<b>🎯 سیگنال دایورجنس RSI (۵ دقیقه) 🎯</b>\n"
        f"📊 تایم‌فریم: {INTERVAL}m | دوره RSI: {RSI_PERIOD} | نمادها: {len(PAIRS)}\n"
        "🔍 مقایسه کف/سقف قیمت با RSI در دو نیمه اخیر\n\n"
    )
    body = "\n\n".join([f"• {a}" for a in alerts])
    final_message = f"{header}{body}"
    
    print("\n===== پیام نهایی =====")
    print(final_message)
    
    if send_telegram_message(final_message):
        print("✅ پیام با موفقیت به تلگرام ارسال شد.")
    else:
        print("❌ ارسال پیام به تلگرام ناموفق بود.")

if __name__ == "__main__":
    main()
