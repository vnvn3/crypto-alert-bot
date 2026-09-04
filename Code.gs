// ==========================================================
// 🚨 Spike Bot — اسکنر اسپایک فیوچرز OKX
// اجرا هر ۱۰ دقیقه | Google Apps Script
// ==========================================================

// ---------- ⚙️ تنظیمات (اینجا را ویرایش کن) ----------
const BOT_TOKEN  = "8423104115:AAG9kZux_G2vg7W8O_5D27sYwH0AJGkxwqo";
const CHANNEL_ID ="20574556"; 

const CFG = {
  BAR: "5m",                  // تایم‌فریم کندل: 1m,3m,5m,15m,30m,1H
  MAX_SYMBOLS: 130,           // تعداد نماد (برای رعایت کوتای روزانه)
  MIN_VOL_USD: 3000000,       // حداقل حجم ۲۴ ساعته (۳ میلیون دلار)
  KLINE_LIMIT: 60,            // تعداد کندل دریافتی

  // --- شرایط اسپایک ---
  BODY_TO_RANGE: 0.55,        // بدنه ≥ ۵۵٪ رنج کندل
  RANGE_MULT: 2.2,            // رنج ≥ ۲.۲ برابر میانگین
  ATR_LOOKBACK: 14,           // تعداد کندل برای میانگین
  MIN_MOVE_PCT: 0.25,         // حداقل درصد حرکت
  FIRST_CANDLE_MAX: 0.45,     // کندل قبل باید آرام باشد

  DEDUP_MIN: 45,              // تا ۴۵ دقیقه سیگنال تکراری نفرست
  CHUNK: 30,                  // تعداد درخواست همزمان
  ACTIVE_START: 7,            // شروع ساعت فعال (ایران)
  ACTIVE_END: 23              // پایان ساعت فعال (ایران)
};

// ==========================================================
// 🚀 تابع اصلی — تریگر این را صدا می‌زند
// ==========================================================
function main() {
  if (!isActiveHour()) {
    Logger.log("⏸️ خارج از بازه فعال");
    return;
  }

  const t0 = new Date().getTime();
  const symbols = getSymbols();
  if (!symbols.length) {
    Logger.log("❌ لیست نمادها خالی است");
    return;
  }

  Logger.log("🔍 اسکن " + symbols.length + " نماد ...");

  const hits = [];

  // درخواست‌ها را دسته‌دسته و موازی می‌فرستیم (سرعت بالا)
  for (let i = 0; i < symbols.length; i += CFG.CHUNK) {
    const chunk = symbols.slice(i, i + CFG.CHUNK);

    const requests = chunk.map(function (inst) {
      return {
        url: "https://www.okx.com/api/v5/market/candles?instId=" + inst +
             "&bar=" + CFG.BAR + "&limit=" + CFG.KLINE_LIMIT,
        muteHttpExceptions: true
      };
    });

    let responses;
    try {
      responses = UrlFetchApp.fetchAll(requests);
    } catch (e) {
      Logger.log("⚠️ خطای دسته: " + e);
      continue;
    }

    for (let k = 0; k < responses.length; k++) {
      try {
        if (responses[k].getResponseCode() !== 200) continue;
        const data = JSON.parse(responses[k].getContentText());
        if (data.code !== "0" || !data.data) continue;

        // فقط کندل‌های بسته‌شده، از قدیم به جدید
        const candles = data.data
          .filter(function (c) { return c[c.length - 1] === "1"; })
          .reverse();

        if (candles.length < CFG.ATR_LOOKBACK + 3) continue;

        const spike = detectSpike(candles);
        if (!spike) continue;

        hits.push({
          name: chunk[k].replace("-USDT-SWAP", ""),
          price: parseFloat(candles[candles.length - 1][4]),
          emoji: spike.emoji,
          dir: spike.dir,
          movePct: spike.movePct,
          rangeMult: spike.rangeMult
        });
      } catch (e) { /* نماد مشکل‌دار را رد کن */ }
    }
  }

  // ---------- فیلتر ضد تکرار ----------
  const cache = CacheService.getScriptCache();
  const fresh = [];
  for (let i = 0; i < hits.length; i++) {
    const key = "d_" + hits[i].name + "_" + hits[i].dir;
    if (cache.get(key)) continue;
    cache.put(key, "1", CFG.DEDUP_MIN * 60);
    fresh.push(hits[i]);
  }

  const sec = ((new Date().getTime() - t0) / 1000).toFixed(1);
  Logger.log("⏱ " + sec + "s | یافت‌شده: " + hits.length + " | جدید: " + fresh.length);

  if (!fresh.length) return;

  // قوی‌ترین اسپایک‌ها اول
  fresh.sort(function (a, b) { return b.movePct - a.movePct; });

  sendTelegram(buildMessage(fresh, symbols.length));
}

// ==========================================================
// 📋 گرفتن لیست نمادهای پرحجم (با کش ۱ ساعته)
// ==========================================================
function getSymbols() {
  const cache = CacheService.getScriptCache();
  const cached = cache.get("symbols");
  if (cached) {
    try { return JSON.parse(cached); } catch (e) {}
  }

  try {
    const res = UrlFetchApp.fetch(
      "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
      { muteHttpExceptions: true }
    );
    if (res.getResponseCode() !== 200) return [];

    const data = JSON.parse(res.getContentText());
    if (data.code !== "0") return [];

    const rows = [];
    for (let i = 0; i < data.data.length; i++) {
      const t = data.data[i];
      if (t.instId.indexOf("-USDT-SWAP") === -1) continue;
      const last = parseFloat(t.last) || 0;
      const vol = (parseFloat(t.volCcy24h) || 0) * last;
      if (last <= 0 || vol < CFG.MIN_VOL_USD) continue;
      rows.push([t.instId, vol]);
    }

    rows.sort(function (a, b) { return b[1] - a[1]; });

    const list = rows.slice(0, CFG.MAX_SYMBOLS).map(function (r) { return r[0]; });
    cache.put("symbols", JSON.stringify(list), 3600);
    return list;
  } catch (e) {
    Logger.log("❌ getSymbols: " + e);
    return [];
  }
}

// ==========================================================
// 🔥 الگوریتم تشخیص اسپایک
// ==========================================================
function detectSpike(c) {
  const n = c.length;

  const o1 = +c[n-3][1], cl1 = +c[n-3][4];
  const o2 = +c[n-2][1], h2 = +c[n-2][2], l2 = +c[n-2][3], cl2 = +c[n-2][4];
  const o3 = +c[n-1][1], cl3 = +c[n-1][4];

  const body1 = Math.abs(cl1 - o1);
  const body2 = Math.abs(cl2 - o2);
  const range2 = h2 - l2;

  // محافظ تقسیم بر صفر
  if (!(range2 > 0) || !(body2 > 0) || !(o2 > 0)) return null;

  // میانگین رنج کندل‌های قبل
  let sum = 0, cnt = 0;
  for (let i = n - 3 - CFG.ATR_LOOKBACK; i < n - 3; i++) {
    if (i < 0) continue;
    sum += (+c[i][2]) - (+c[i][3]);
    cnt++;
  }
  if (!cnt) return null;
  const avgRange = sum / cnt;
  if (!(avgRange > 0)) return null;

  // شرط ۱: بدنه قدرتمند نسبت به رنج خودش
  if (body2 / range2 < CFG.BODY_TO_RANGE) return null;

  // شرط ۲: رنج بزرگ نسبت به کندل‌های اخیر
  const rangeMult = range2 / avgRange;
  if (rangeMult < CFG.RANGE_MULT) return null;

  // شرط ۳: حرکت واقعی به درصد
  const movePct = (body2 / o2) * 100;
  if (movePct < CFG.MIN_MOVE_PCT) return null;

  // شرط ۴: کندل قبل از اسپایک آرام باشد
  if (body1 > body2 * CFG.FIRST_CANDLE_MAX) return null;

  // شرط ۵: کندل بعدی تایید کند
  const up = cl2 > o2;
  if (up && cl3 <= o3) return null;
  if (!up && cl3 >= o3) return null;

  return {
    dir: up ? "UP" : "DOWN",
    emoji: up ? "🟢 صعودی" : "🔴 نزولی",
    movePct: movePct,
    rangeMult: rangeMult
  };
}

// ==========================================================
// 💬 ساخت پیام
// ==========================================================
function buildMessage(hits, total) {
  const now = new Date(new Date().getTime() + 12600000); // UTC+3:30
  const hh = ("0" + now.getUTCHours()).slice(-2);
  const mm = ("0" + now.getUTCMinutes()).slice(-2);

  let msg = "🚨 <b>اسپایک فیوچرز | تایم " + CFG.BAR + "</b>\n";
  msg += "🕐 " + hh + ":" + mm + " | اسکن " + total + " نماد | ✅ " + hits.length + " سیگنال\n\n";

  for (let i = 0; i < hits.length; i++) {
    const h = hits[i];
    msg += "• <b>" + h.name + "</b> " + h.emoji + "\n";
    msg += "   قدرت: <code>" + h.movePct.toFixed(2) + "%</code>";
    msg += " | رنج: <code>" + h.rangeMult.toFixed(1) + "x</code>\n";
    msg += "   قیمت: <code>" + fmtPrice(h.price) + "</code>\n";
  }
  return msg;
}

function fmtPrice(p) {
  if (p >= 1000) return p.toFixed(1);
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}

// ==========================================================
// 📤 ارسال به تلگرام (با تکه‌تکه کردن پیام بلند)
// ==========================================================
function sendTelegram(text) {
  const chunks = splitText(text, 3800);
  for (let i = 0; i < chunks.length; i++) {
    try {
      UrlFetchApp.fetch(
        "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
        {
          method: "post",
          muteHttpExceptions: true,
          payload: {
            chat_id: CHANNEL_ID,
            text: chunks[i],
            parse_mode: "HTML",
            disable_web_page_preview: "true"
          }
        }
      );
    } catch (e) {
      Logger.log("❌ تلگرام: " + e);
    }
    if (chunks.length > 1) Utilities.sleep(800);
  }
}

function splitText(text, max) {
  if (text.length <= max) return [text];
  const out = [];
  const lines = text.split("\n");
  let buf = "";
  for (let i = 0; i < lines.length; i++) {
    if (buf.length + lines[i].length + 1 > max) { out.push(buf); buf = ""; }
    buf += lines[i] + "\n";
  }
  if (buf.replace(/\s/g, "").length) out.push(buf);
  return out;
}

// ==========================================================
// ⏰ ساعت فعال (به وقت ایران)
// ==========================================================
function isActiveHour() {
  const h = new Date(new Date().getTime() + 12600000).getUTCHours();
  return h >= CFG.ACTIVE_START && h < CFG.ACTIVE_END;
}

// ==========================================================
// 🧪 تست دستی — این را اجرا کن تا مطمئن شوی کار می‌کند
// ==========================================================
function testNow() {
  sendTelegram("✅ ربات وصل شد و آماده است!");
  Logger.log("پیام تست ارسال شد.");
}

// ==========================================================
// 🔧 نصب خودکار تریگر ۱۰ دقیقه‌ای
// ==========================================================
function setupTrigger() {
  // حذف تریگرهای قبلی
  const old = ScriptApp.getProjectTriggers();
  for (let i = 0; i < old.length; i++) {
    if (old[i].getHandlerFunction() === "main") {
      ScriptApp.deleteTrigger(old[i]);
    }
  }
  // ساخت تریگر جدید
  ScriptApp.newTrigger("main").timeBased().everyMinutes(10).create();
  Logger.log("✅ تریگر ۱۰ دقیقه‌ای نصب شد.");
}
