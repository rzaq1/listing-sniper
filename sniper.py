"""
Listing Sniper — PythonAnywhere Edition
يشتغل كـ Scheduled Task كل 15 دقيقة
يفحص: Bybit + KuCoin + OKX
يرسل Telegram لما يلاقي إدراج جديد خلال آخر 3 أيام
"""

import requests
import json
import re
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ===================== الإعدادات =====================
TELEGRAM_TOKEN  = "8754418638:AAGcTK-B6iNAjwY9EANg1IHl7bUTBpy7cso"
TELEGRAM_CHAT_ID = "1911377719"
RIYADH_TZ       = ZoneInfo("Asia/Riyadh")
MAX_AGE_DAYS     = 3

# ملف الذاكرة — يحفظ الإعلانات اللي شفناها
SEEN_FILE = "/home/rzaq1/seen_listings.json"

# ===================== الذاكرة =====================
def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        print(f"[seen] خطأ في الحفظ: {e}")

# ===================== أدوات =====================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

SYMBOL_BLACKLIST = {
    "PERPETUAL","FUTURES","USDT","USDC","USD","BTC","ETH","BNB",
    "SPOT","MARGIN","CONTRACT","TRADING","LISTING","NEW","FOR",
    "SWAP","TOKEN","COIN","LAUNCH","INNOVATION","ZONE","STANDARD",
    "PRE","MARKET","CONVERT","ADD","LIST","WILL","WITH","LEVERAGE",
    "THE","AND","OKX","BYBIT","BINANCE","KUCOIN","MEXC","GATE",
    "CRYPTO","DIGITAL","ASSET","LAYER","NETWORK","PAYMENT","SERVICES"
}

LISTING_KEYWORDS = [
    "will list","to list","lists ","listing","new listing","new spot",
    "spot trading","spot launch","to add","adds ","added","introducing",
    "launches","launchpad","new crypto","going live","to convert",
    "pre-market","innovation zone","gets listed","now listed",
    "will add","to launch","will launch","world premiere","adding"
]

PERPETUAL_KEYWORDS = ["perpetual","perp","futures","contract","innovation zone","swap"]

def is_listing(title):
    return any(kw in title.lower() for kw in LISTING_KEYWORDS)

def is_perp(title):
    return any(kw in title.lower() for kw in PERPETUAL_KEYWORDS)

def is_recent(ts):
    if not ts: return True
    try:
        ts_int = int(ts)
        if ts_int > 10**11: ts_int //= 1000
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(ts_int, tz=timezone.utc)
        return age.days < MAX_AGE_DAYS
    except: return True

def ts_to_riyadh(ts):
    try:
        ts_int = int(ts)
        if ts_int > 10**11: ts_int //= 1000
        return datetime.fromtimestamp(ts_int, tz=timezone.utc).astimezone(RIYADH_TZ)
    except: return None

def time_until(dt):
    if not dt: return ""
    try:
        diff = int((dt - datetime.now(RIYADH_TZ)).total_seconds())
        if diff < 0:
            h = abs(diff) // 3600
            return f"(بدأ قبل {h} ساعة)" if h > 0 else "(بدأ للتو!)"
        d = diff // 86400
        h = (diff % 86400) // 3600
        m = (diff % 3600) // 60
        if d > 0: return f"← بعد {d} يوم و{h} ساعة ⏳"
        if h > 0: return f"← بعد {h} ساعة و{m} دقيقة ⏳"
        return f"← بعد {m} دقيقة ⏳" if m > 0 else "← خلال أقل من دقيقة! 🔥"
    except: return ""

def extract_symbol(title):
    m = re.search(r'\(([A-Z0-9]{2,10})\)', title)
    if m and m.group(1).upper() not in SYMBOL_BLACKLIST:
        return m.group(1).upper()
    m = re.search(r'\b([A-Z]{2,10})(?:USDT|USDC)\b', title)
    if m and m.group(1).upper() not in SYMBOL_BLACKLIST:
        return m.group(1).upper()
    m = re.search(r'\b(?:will\s+list|to\s+list|lists|adding|adds|launch)\s+([A-Z]{2,10})\b', title, re.IGNORECASE)
    if m and m.group(1).upper() not in SYMBOL_BLACKLIST:
        return m.group(1).upper()
    m = re.search(r'\bfor\s+([A-Z]{2,10})\s+(?:crypto|token|spot)\b', title, re.IGNORECASE)
    if m and m.group(1).upper() not in SYMBOL_BLACKLIST:
        return m.group(1).upper()
    return "؟"

def extract_coin_name(title, symbol):
    m = re.search(r'(?:list|adding|launch|introduce|listing)\s+([A-Za-z][a-zA-Z0-9\s]{1,30}?)\s*\(', title, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        if name.upper() not in SYMBOL_BLACKLIST and len(name) > 1:
            return name
    return ""

def extract_trading_dt(text):
    """استخرج وقت بدء التداول من النص"""
    if not text: return None
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,
              "sep":9,"oct":10,"nov":11,"dec":12,"january":1,"february":2,"march":3,
              "april":4,"june":6,"july":7,"august":8,"september":9,"october":10,
              "november":11,"december":12}

    # نمط: HH:MM UTC on YYYY-MM-DD
    m = re.search(
        r'(?:trading|launch|start|open|list|available)[^.]{0,80}?(\d{1,2}:\d{2})\s*(?:AM|PM)?\s*\(?(?:UTC|GMT)\+?0?\)?[^.]{0,50}?(202\d[-/]\d{2}[-/]\d{2})',
        text, re.IGNORECASE
    )
    if m:
        try:
            h, mn = map(int, m.group(1).split(":"))
            parts = m.group(2).replace("/","-").split("-")
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]), h, mn, tzinfo=timezone.utc)
        except: pass

    # نمط: May 3, 2026 at 10:00 UTC
    m = re.search(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(202\d)[^.]{0,50}?(\d{1,2}:\d{2})\s*(?:UTC|GMT)',
        text, re.IGNORECASE
    )
    if m:
        try:
            mon = months[m.group(1).lower()[:3]]
            h, mn = map(int, m.group(4).split(":"))
            return datetime(int(m.group(3)), mon, int(m.group(2)), h, mn, tzinfo=timezone.utc)
        except: pass

    # نمط: YYYY-MM-DD HH:MM UTC
    m = re.search(r'(202\d[-/]\d{2}[-/]\d{2})[\s,T]+(\d{1,2}):(\d{2})\s*(?:UTC|GMT)', text, re.IGNORECASE)
    if m:
        try:
            parts = m.group(1).replace("/","-").split("-")
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except: pass

    return None

def fetch_page_text(url):
    """اقرأ صفحة الإعلان لاستخراج وقت التداول"""
    try:
        r = requests.get(url, headers={**HEADERS, "Accept": "text/html"}, timeout=12)
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()[:6000]
    except: return ""

def check_coin_on_exchanges(symbol):
    """فحص العملة على المنصات الأخرى"""
    if symbol in ("؟", "غير محدد") or len(symbol) < 2:
        return {}
    results = {}
    checks = {
        "Binance": f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
        "KuCoin":  f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT",
        "Gate.io": f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={symbol}_USDT",
        "MEXC":    f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}USDT",
        "OKX":     f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT",
    }
    for name, url in checks.items():
        try:
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                results[name] = {"exists": False}
                continue
            data = r.json()
            price = None
            if name == "Binance": price = float(data.get("price") or 0)
            elif name == "KuCoin":
                d = data.get("data") or {}
                price = float(d.get("price") or 0)
            elif name == "Gate.io":
                price = float((data[0].get("last") if data else None) or 0)
            elif name == "MEXC": price = float(data.get("price") or 0)
            elif name == "OKX":
                d = (data.get("data") or [{}])[0]
                price = float(d.get("last") or 0)
            results[name] = {"exists": bool(price and price > 0), "price": price}
        except:
            results[name] = {"exists": False}

    # CoinGecko
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/search?query={symbol}", timeout=5)
        if r.status_code == 200:
            coins = r.json().get("coins", [])
            found = next((c for c in coins[:5] if c.get("symbol","").upper() == symbol), None)
            results["CoinGecko"] = {"exists": bool(found), "name": found.get("name","") if found else ""}
        else:
            results["CoinGecko"] = {"exists": False}
    except:
        results["CoinGecko"] = {"exists": False}

    return results

# ===================== Telegram =====================
def send_telegram(message):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10
        )
        if r.status_code != 200:
            print(f"[Telegram] خطأ: {r.text[:100]}")
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram Error] {e}")
        return False

def build_message(listing, exchanges):
    symbol   = listing.get("symbol", "؟")
    name     = listing.get("coin_name", "")
    source   = listing["source"]
    title    = listing["title"]
    url      = listing["url"]
    perp     = listing.get("is_perp", False)
    pub_dt   = listing.get("pub_dt")
    trade_dt = listing.get("trading_dt")

    type_emoji = "🔮" if perp else "💎"
    type_label = "Perpetual" if perp else "Spot"

    # سطر العملة
    if name and name != symbol:
        coin_line = f"🪙 <b>{name} ({symbol})</b>\n"
    elif symbol != "؟":
        coin_line = f"🪙 <b>{symbol}</b>\n"
    else:
        coin_line = f"📝 {title[:70]}\n"

    # وقت الإعلان
    if pub_dt:
        pub_line = f"⏱ <b>نشر الإعلان:</b> {pub_dt.strftime('%Y-%m-%d %H:%M')} (الرياض)\n"
    else:
        pub_line = f"⏱ <b>اكتُشف:</b> {datetime.now(RIYADH_TZ).strftime('%Y-%m-%d %H:%M')} (الرياض)\n"

    # وقت بدء التداول
    if trade_dt:
        countdown = time_until(trade_dt)
        trade_line = f"🟢 <b>بدء التداول:</b> {trade_dt.strftime('%Y-%m-%d %H:%M')} (الرياض) {countdown}\n"
    else:
        trade_line = f"🟢 <b>بدء التداول:</b> افتح الرابط\n"

    # فحص المنصات
    ex_lines = ""
    cex_count = 0
    cg_exists = False
    if exchanges and symbol != "؟":
        ex_lines = "\n🔍 <b>موجودة مسبقاً؟</b>\n"
        for ex_name, ex_data in exchanges.items():
            if ex_name == "CoinGecko":
                cg_exists = ex_data.get("exists", False)
                continue
            if ex_data.get("exists"):
                cex_count += 1
                p = ex_data.get("price", 0)
                ex_lines += f"   ✅ {ex_name} → ${p:.6f}\n"
            else:
                ex_lines += f"   ❌ {ex_name}\n"
        ex_lines += f"   📊 CoinGecko → {'✅ موجودة' if cg_exists else '❌ غير موجودة'}\n"

    # تنبيه استراتيجي
    if not cg_exists and cex_count == 0:
        strategy = "\n🎯 <b>إدراج جديد كلياً</b> ← استراتيجية الـ 30 ثانية!\n"
    elif cex_count > 0:
        strategy = f"\n⚠️ <b>موجودة على {cex_count} منصة</b> — السعر مرتفع مسبقاً\n"
    else:
        strategy = "\nℹ️ موجودة في DEX — تحقق من السعر\n"

    return (
        f"🚨 <b>إدراج جديد!</b> {type_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{coin_line}"
        f"📌 <b>المنصة:</b> {source} — {type_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pub_line}"
        f"{trade_line}"
        f"━━━━━━━━━━━━━━━━━━━━━"
        f"{ex_lines}"
        f"{strategy}"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 {url}"
    )

# ===================== Bybit =====================
def fetch_bybit():
    results = []
    try:
        for cat in ["new_crypto", "spot"]:
            r = requests.get(
                "https://api.bybit.com/v5/announcements/index",
                params={"locale":"en-US","type":cat,"page":1,"limit":30},
                headers=HEADERS, timeout=10
            )
            if r.status_code != 200: continue
            for item in r.json().get("result",{}).get("list",[]):
                title = item.get("title","")
                if not is_listing(title): continue
                ts = item.get("dateTimestamp") or item.get("publishTime",0)
                if not is_recent(ts): continue
                pub_dt = ts_to_riyadh(ts)
                desc = item.get("description","")
                url = item.get("url","https://announcements.bybit.com/")

                # استخرج وقت التداول من الوصف أو الصفحة
                trade_utc = extract_trading_dt(desc)
                if not trade_utc:
                    trade_utc = extract_trading_dt(fetch_page_text(url))
                trade_dt = trade_utc.astimezone(RIYADH_TZ) if trade_utc else None

                tags = item.get("tags",[])
                is_spot_tag = any("spot" in str(t).lower() for t in tags)
                is_perp_tag = any(("perp" in str(t).lower() or "futures" in str(t).lower() or "derivatives" in str(t).lower()) for t in tags)
                listing_perp = is_perp_tag or (is_perp(title) and not is_spot_tag)

                sym = extract_symbol(title)
                results.append({
                    "source":"Bybit","title":title,"url":url,
                    "symbol":sym,"coin_name":extract_coin_name(title,sym),
                    "is_perp":listing_perp,"pub_dt":pub_dt,"trading_dt":trade_dt
                })
        print(f"  Bybit: {len(results)}")
    except Exception as e:
        print(f"  Bybit خطأ: {e}")
    return results

# ===================== KuCoin =====================
def fetch_kucoin():
    results = []
    try:
        r = requests.get(
            "https://api.kucoin.com/api/v3/announcements",
            params={"pageSize":30,"currentPage":1,"annType":"new-listings","lang":"en_US"},
            headers=HEADERS, timeout=10
        )
        if r.status_code != 200:
            print(f"  KuCoin: HTTP {r.status_code}")
            return results
        for item in r.json().get("data",{}).get("items",[]):
            title = item.get("annTitle","")
            if not is_listing(title): continue
            ts = item.get("cTime",0)
            if not is_recent(ts): continue
            pub_dt = ts_to_riyadh(ts)
            url = item.get("annUrl","https://www.kucoin.com/announcement")
            desc = item.get("annDesc","")
            trade_utc = extract_trading_dt(desc)
            if not trade_utc:
                trade_utc = extract_trading_dt(fetch_page_text(url))
            trade_dt = trade_utc.astimezone(RIYADH_TZ) if trade_utc else None
            sym = extract_symbol(title)
            results.append({
                "source":"KuCoin","title":title,"url":url,
                "symbol":sym,"coin_name":extract_coin_name(title,sym),
                "is_perp":is_perp(title),"pub_dt":pub_dt,"trading_dt":trade_dt
            })
        print(f"  KuCoin: {len(results)}")
    except Exception as e:
        print(f"  KuCoin خطأ: {e}")
    return results

# ===================== OKX =====================
def fetch_okx():
    results = []
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/support/announcements",
            params={"annType":"announcements-new-listings"},
            headers=HEADERS, timeout=10
        )
        if r.status_code != 200:
            print(f"  OKX: HTTP {r.status_code}")
            return results
        details = r.json().get("data",[{}])[0].get("details",[])
        for item in details[:30]:
            title = item.get("title","")
            if not is_listing(title): continue
            ts = item.get("pTime") or item.get("businessPTime",0)
            if not is_recent(ts): continue
            pub_dt = ts_to_riyadh(ts)
            url = item.get("url","https://www.okx.com/help-center/")
            trade_utc = extract_trading_dt(fetch_page_text(url))
            trade_dt = trade_utc.astimezone(RIYADH_TZ) if trade_utc else None
            sym = extract_symbol(title)
            results.append({
                "source":"OKX","title":title,"url":url,
                "symbol":sym,"coin_name":extract_coin_name(title,sym),
                "is_perp":is_perp(title),"pub_dt":pub_dt,"trading_dt":trade_dt
            })
        print(f"  OKX: {len(results)}")
    except Exception as e:
        print(f"  OKX خطأ: {e}")
    return results

# ===================== Binance =====================
def fetch_binance():
    results = []
    try:
        r = requests.get(
            "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
            params={"type":1,"catalogId":48,"pageNo":1,"pageSize":30},
            headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"},
            timeout=10
        )
        if r.status_code != 200:
            print(f"  Binance: HTTP {r.status_code}")
            return results
        data = r.json().get("data",{})
        catalogs = data.get("catalogs",[])
        articles = catalogs[0].get("articles",[]) if catalogs else data.get("articles",[])
        print(f"  Binance raw articles: {len(articles)}")
        for item in articles:
            title = item.get("title","")
            if not is_listing(title): continue
            ts = item.get("releaseDate",0)
            if not is_recent(ts): continue
            pub_dt = ts_to_riyadh(ts)
            code = item.get("code","")
            url = f"https://www.binance.com/en/support/announcement/{code}"
            trade_utc = extract_trading_dt(fetch_page_text(url))
            trade_dt = trade_utc.astimezone(RIYADH_TZ) if trade_utc else None
            sym = extract_symbol(title)
            results.append({
                "source":"Binance","title":title,"url":url,
                "symbol":sym,"coin_name":extract_coin_name(title,sym),
                "is_perp":is_perp(title),"pub_dt":pub_dt,"trading_dt":trade_dt
            })
        print(f"  Binance: {len(results)}")
    except Exception as e:
        print(f"  Binance خطأ: {e}")
    return results

# ===================== الحلقة الرئيسية =====================
def main():
    now = datetime.now(RIYADH_TZ).strftime("%H:%M:%S")
    print(f"\n[{now}] بدأ الفحص...")

    seen = load_seen()
    all_listings = []

    for fetcher in [fetch_bybit, fetch_kucoin, fetch_okx, fetch_binance]:
        try:
            all_listings.extend(fetcher())
        except Exception as e:
            print(f"  خطأ في {fetcher.__name__}: {e}")

    print(f"  إجمالي الإعلانات: {len(all_listings)}")
    new_count = 0

    for listing in all_listings:
        # مفتاح فريد
        key = f"{listing['source']}:{listing['title']}"
        if key in seen:
            continue

        seen.add(key)
        new_count += 1

        # فحص المنصات
        sym = listing.get("symbol","؟")
        exchanges = check_coin_on_exchanges(sym) if sym != "؟" else {}

        msg = build_message(listing, exchanges)
        send_telegram(msg)
        print(f"  ✅ جديد: {listing['source']} — {listing['title'][:50]}")

    # حفظ الذاكرة (احتفظ بآخر 500 فقط)
    seen_list = list(seen)
    if len(seen_list) > 500:
        seen_list = seen_list[-500:]
    save_seen(set(seen_list))

    if new_count == 0:
        print(f"  لا جديد — الكل محفوظ مسبقاً")
    else:
        print(f"  تم إرسال {new_count} تنبيه")

if __name__ == "__main__":
    main()
