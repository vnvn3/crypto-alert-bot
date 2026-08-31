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

# --- تنظیمات قابل تغییر ---
INTERVAL = "5"          # تایم‌فریم: 1, 3, 5, 15, 30, 60, 240, D
RSI_PERIOD = 14
OVERBOUGHT = 70
OVERSOLD = 38
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


def check_rsi(symbol):
    """برای یک نماد، RSI رو از Bybit می‌گیره و برمی‌گردونه"""
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={INTERVAL}&limit={KLINE_LIMIT}"
        response = requests.get(url, timeout=8)
        data = response.json()

        if data.get('retCode') != 0:
            print(f"⚠️ {symbol}: خطای API -> {data.get('retMsg')}")
            return symbol, None

        klines = data['result']['list']
        if len(klines) < RSI_PERIOD + 1:
            return symbol, None

        # داده‌های Bybit از جدید به قدیم هستن، برعکسش می‌کنیم تا قدیم به جدید بشه
        klines.reverse()
        closes = [float(k[4]) for k in klines]  # ایندکس 4 = close price

        rsi = calculate_rsi(closes, RSI_PERIOD)
        return symbol, rsi

    except Exception as e:
        print(f"❌ {symbol}: خطا -> {e}")
        return symbol, None


def main():
    overbought_list = []
    oversold_list = []

    print(f"🔍 شروع اسکن {len(PAIRS)} نماد در تایم‌فریم {INTERVAL} دقیقه...")

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
