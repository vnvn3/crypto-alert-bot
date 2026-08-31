import requests
import os
import html
import concurrent.futures

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
    "NOTUSDT", "BANANAUSDT", "1000SATSUSDT", "OMNIUSDT", "REZUSDT", "LISTAUSDT", "ZROUSDT", "1000RATSUSDT", "1000CATSUSDT", "SCRUSDT"
]

# جفت‌ارزهای فارکس و طلا (از Yahoo Finance گرفته می‌شن، نه Bybit)
# کلید = نماد Yahoo Finance | مقدار = نامی که در پیام تلگرام نشون داده می‌شه
FOREX_PAIRS = {
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "XAUUSD=X": "XAUUSD",
    "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD",
    "USDCHF=X": "USDCHF",
    "USDCAD=X": "USDCAD",
    "NZDUSD=X": "NZDUSD",
}

# --- تنظیمات قابل تغییر ---
INTERVAL = "5"          # تایم‌فریم کریپتو (Bybit): 1, 3, 5, 15, 30, 60, 240, D
YAHOO_INTERVAL = "15m"   # تایم‌فریم فارکس (Yahoo): 5m, 15m, 30m, 60m
YAHOO_RANGE = "5d"       # بازه داده تاریخی فارکس
RSI_PERIOD = 14
OVERBOUGHT = 70
OVERSOLD = 30
KLINE_LIMIT = RSI_PERIOD + 50  # داده کافی برای محاسبه دقیق‌تر RSI


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


def calculate_rsi(closes, period=14):
    """محاسبه RSI با روش Wilder's smoothing (همون چیزی که TradingView استفاده می‌کنه)"""
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


# نگاشت تایم‌فریم به فرمت OKX
BAR_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m",
    "30": "30m", "60": "1H", "240": "4H", "D": "1Dutc"
}


def symbol_to_okx_instid(symbol):
    """تبدیل نماد Bybit مثل BTCUSDT به فرمت OKX مثل BTC-USDT-SWAP"""
    base = symbol[:-4]  # حذف USDT از انتها
    return f"{base}-USDT-SWAP"


def check_rsi(symbol):
    """برای یک نماد، RSI رو از OKX می‌گیره و برمی‌گردونه (Bybit برای IP آمریکا/GitHub Actions مسدوده)"""
    try:
        inst_id = symbol_to_okx_instid(symbol)
        bar = BAR_MAP.get(INTERVAL, "5m")
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={KLINE_LIMIT}"
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            print(f"⚠️ {symbol}: HTTP {response.status_code} -> {response.text[:120]}")
            return symbol, None

        data = response.json()
        if data.get('code') != '0':
            print(f"⚠️ {symbol}: خطای OKX -> {data.get('msg')}")
            return symbol, None

        candles = data.get('data', [])
        if len(candles) < RSI_PERIOD + 2:
            return symbol, None

        # اولین آیتم جدیدترینه و ممکنه هنوز کامل نشده باشه، کنارش می‌ذاریم
        closed = candles[1:]
        closed.reverse()  # قدیم -> جدید
        closes = [float(c[4]) for c in closed]  # ایندکس 4 = close

        rsi = calculate_rsi(closes, RSI_PERIOD)
        return symbol, rsi

    except Exception as e:
        print(f"❌ {symbol}: خطا -> {e}")
        return symbol, None


def check_rsi_forex(yahoo_symbol, display_name):
    """برای یک جفت‌ارز فارکس/طلا، RSI رو از Yahoo Finance می‌گیره و برمی‌گردونه"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval={YAHOO_INTERVAL}&range={YAHOO_RANGE}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=8)
        data = response.json()

        result = data.get('chart', {}).get('result')
        if not result:
            print(f"⚠️ {display_name}: داده‌ای برنگشت")
            return display_name, None

        quote = result[0]['indicators']['quote'][0]
        closes = [c for c in quote['close'] if c is not None]

        if len(closes) < RSI_PERIOD + 1:
            return display_name, None

        rsi = calculate_rsi(closes, RSI_PERIOD)
        return display_name, rsi

    except Exception as e:
        print(f"❌ {display_name}: خطا -> {e}")
        return display_name, None


def main():
    overbought_list = []
    oversold_list = []

    print(f"🔍 شروع اسکن {len(PAIRS)} نماد کریپتو در تایم‌فریم {INTERVAL} دقیقه...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_rsi, PAIRS)

        for symbol, rsi in results:
            if rsi is None:
                continue
            print(f"{symbol}: RSI = {rsi}")
            if rsi >= OVERBOUGHT:
                overbought_list.append((symbol, rsi))
            elif rsi <= OVERSOLD:
                oversold_list.append((symbol, rsi))

    print(f"🔍 شروع اسکن {len(FOREX_PAIRS)} جفت‌ارز فارکس/طلا در تایم‌فریم {YAHOO_INTERVAL}...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        forex_results = executor.map(
            lambda item: check_rsi_forex(item[0], item[1]), FOREX_PAIRS.items()
        )

        for display_name, rsi in forex_results:
            if rsi is None:
                continue
            print(f"{display_name}: RSI = {rsi}")
            if rsi >= OVERBOUGHT:
                overbought_list.append((display_name, rsi))
            elif rsi <= OVERSOLD:
                oversold_list.append((display_name, rsi))

    # مرتب‌سازی
    overbought_list.sort(key=lambda x: x[1], reverse=True)
    oversold_list.sort(key=lambda x: x[1])

    message_lines = [f"📊 <b>گزارش RSI (تایم‌فریم {INTERVAL} دقیقه)</b>\n"]

    if overbought_list:
        message_lines.append("🔴 <b>اشباع خرید (Overbought):</b>")
        for symbol, rsi in overbought_list:
            message_lines.append(f"• {html.escape(symbol)} — RSI: {rsi}")
        message_lines.append("")

    if oversold_list:
        message_lines.append("🟢 <b>اشباع فروش (Oversold):</b>")
        for symbol, rsi in oversold_list:
            message_lines.append(f"• {html.escape(symbol)} — RSI: {rsi}")
        message_lines.append("")

    if not overbought_list and not oversold_list:
        message_lines.append("در حال حاضر هیچ نمادی در محدوده اشباع خرید یا فروش نیست.")

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
