# Backend/Automation/realtime_data.py  v3.0
# Jarvis AI — Live Data Engine
# All previous fixes kept + advanced_jobs integrated
from __future__ import annotations
import json, re, datetime, time, ssl
from pathlib import Path
from typing  import Optional
from dotenv  import dotenv_values

_env         = dotenv_values(".env")
WEATHER_KEY  = _env.get("OpenWeatherKey","").strip()
NEWS_KEY     = _env.get("NewsAPIKey","").strip()
DEFAULT_CITY = _env.get("City","Bhopal").strip()
USERNAME     = _env.get("Username","User")

DATA_DIR  = Path("Data")
CACHE_DIR = DATA_DIR / "realtime_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_TTL = {"weather":1800,"news":3600,"jobs":7200,"stock":300,"crypto":300,"sports":600}

try:
    from .notifier import notify
except ImportError:
    def notify(t,m): pass

import urllib.request, urllib.parse

_SSL = ssl.create_default_context()
try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL.check_hostname = False
    _SSL.verify_mode    = ssl.CERT_NONE


def _cache_get(key:str) -> Optional[str]:
    f = CACHE_DIR / f"{re.sub(r'[^a-z0-9_]','_',key.lower())}.json"
    if not f.exists(): return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        ttl  = CACHE_TTL.get(key.split("_")[0],3600)
        if time.time()-data.get("ts",0)<ttl: return data.get("value")
    except Exception: pass
    return None

def _cache_set(key:str,value:str):
    try:
        f = CACHE_DIR / f"{re.sub(r'[^a-z0-9_]','_',key.lower())}.json"
        f.write_text(json.dumps({"ts":time.time(),"value":value},ensure_ascii=False),encoding="utf-8")
    except Exception: pass

def _fetch_text(url:str,timeout:int=12) -> Optional[str]:
    try:
        req = urllib.request.Request(url,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis/3.0",
            "Accept":"text/html,application/json,*/*"})
        with urllib.request.urlopen(req,timeout=timeout,context=_SSL) as r:
            return r.read().decode("utf-8",errors="replace")
    except Exception as e:
        print(f"  [Fetch] {url[:60]}: {e}")
        return None

def _fetch_json(url:str,timeout:int=12) -> Optional[dict]:
    t = _fetch_text(url,timeout)
    if not t: return None
    try: return json.loads(t)
    except Exception: return None


# ── WEATHER ────────────────────────────────────────────────────────────────────
def GetWeather(city:str="") -> str:
    city = (city.strip() or DEFAULT_CITY).strip()
    cached = _cache_get(f"weather_{city.lower()}")
    if cached: return cached
    try:
        url  = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        data = _fetch_json(url)
        if data and "current_condition" in data:
            cc   = data["current_condition"][0]
            desc = cc["weatherDesc"][0]["value"]
            temp = cc.get("temp_C","?")
            feel = cc.get("FeelsLikeC","?")
            hum  = cc.get("humidity","?")
            wind = cc.get("windspeedKmph","?")
            result = (f"Weather in {city}:\n"
                      f"  Condition : {desc}\n"
                      f"  Temp      : {temp}°C (feels like {feel}°C)\n"
                      f"  Humidity  : {hum}%\n"
                      f"  Wind      : {wind} km/h")
            _cache_set(f"weather_{city.lower()}",result)
            return result
    except Exception: pass
    if WEATHER_KEY:
        url  = (f"https://api.openweathermap.org/data/2.5/weather"
                f"?q={urllib.parse.quote(city)}&appid={WEATHER_KEY}&units=metric")
        data = _fetch_json(url)
        if data and data.get("cod")==200:
            w    = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            hum  = data["main"]["humidity"]
            wind = data["wind"]["speed"]
            result = (f"Weather in {city}:\n  {w}, {temp}°C, Humidity {hum}%, Wind {wind}m/s")
            _cache_set(f"weather_{city.lower()}",result)
            return result
    return f"Could not get weather for '{city}'. Check internet."


# ── NEWS ───────────────────────────────────────────────────────────────────────
_NEWS_Q = {
    "general":"India+news+today","technology":"technology+tech+India+today",
    "sports":"sports+cricket+India+today","business":"business+economy+India+today",
    "health":"health+medical+India+today","science":"science+research+India+today",
    "entertainment":"bollywood+entertainment+India+today",
}

def GetNews(category:str="general",count:int=6) -> str:
    cat    = category.lower().strip()
    cat    = cat if cat in _NEWS_Q else "general"
    cached = _cache_get(f"news_{cat}")
    if cached: return cached
    headlines = []
    if NEWS_KEY:
        api_cat = cat if cat in ("technology","sports","business","health","science","entertainment") else "general"
        data = _fetch_json(f"https://newsapi.org/v2/top-headlines?country=in&category={api_cat}&pageSize={count}&apiKey={NEWS_KEY}")
        if data and data.get("status")=="ok":
            for a in data.get("articles",[])[:count]:
                if a.get("title") and a["title"]!="[Removed]":
                    headlines.append(f"  • {a['title']}")
    if not headlines:
        q   = urllib.parse.quote(_NEWS_Q[cat])
        txt = _fetch_text(f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en")
        if txt:
            titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",txt)
            if not titles: titles = re.findall(r"<title>([^<]{10,200})</title>",txt)
            for t in titles[1:count+1]:
                t = re.sub(r"\s*-\s*(Google News|Times of India|NDTV|Hindustan Times).*","",t)
                if t.strip(): headlines.append(f"  • {t.strip()}")
    if not headlines: return f"Could not fetch {cat} news. Check internet."
    now    = datetime.datetime.now().strftime("%d %b %Y  %I:%M %p")
    result = f"Top {cat.title()} News — {now}:\n" + "\n".join(headlines[:count])
    _cache_set(f"news_{cat}",result)
    return result


# ── STOCK ──────────────────────────────────────────────────────────────────────
def GetStock(symbol:str) -> str:
    sym    = symbol.strip().upper()
    cached = _cache_get(f"stock_{sym}")
    if cached: return cached
    for suffix in [".NS",".BO",""]:
        ticker = f"{sym}{suffix}" if suffix else sym
        data   = _fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?interval=1d&range=1d",
                             headers={"User-Agent":"Mozilla/5.0"})
        if not data: continue
        try:
            meta   = data["chart"]["result"][0]["meta"]
            price  = meta.get("regularMarketPrice",0)
            prev   = meta.get("chartPreviousClose",0)
            change = price - prev
            pct    = (change/prev*100) if prev else 0
            cur    = meta.get("currency","INR")
            name   = meta.get("longName",sym) or sym
            arrow  = "▲" if change>=0 else "▼"
            result = (f"{name} ({sym}):\n"
                      f"  Price  : {cur} {price:,.2f}\n"
                      f"  Change : {arrow} {abs(change):,.2f} ({pct:+.2f}%)\n"
                      f"  Prev   : {cur} {prev:,.2f}")
            _cache_set(f"stock_{sym}",result)
            return result
        except Exception: continue
    return f"Could not get stock for '{sym}'."


def _fetch_json(url, headers=None, timeout=12):
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception: return None


# ── CRYPTO ─────────────────────────────────────────────────────────────────────
_CRYPTO = {"BTC":"bitcoin","ETH":"ethereum","DOGE":"dogecoin","BNB":"binancecoin",
           "ADA":"cardano","SOL":"solana","XRP":"ripple","MATIC":"matic-network"}

def GetCrypto(symbol:str) -> str:
    sym     = symbol.strip().upper()
    coin_id = _CRYPTO.get(sym,sym.lower())
    cached  = _cache_get(f"crypto_{sym}")
    if cached: return cached
    data = _fetch_json(f"https://api.coingecko.com/api/v3/simple/price?ids={urllib.parse.quote(coin_id)}&vs_currencies=usd,inr&include_24hr_change=true")
    if not data or coin_id not in data:
        return f"Could not get price for '{sym}'."
    d     = data[coin_id]
    usd   = d.get("usd",0); inr = d.get("inr",0); chg = d.get("usd_24h_change",0)
    arrow = "▲" if chg>=0 else "▼"
    result= (f"{sym} Crypto:\n  USD: ${usd:,.2f}\n  INR: ₹{inr:,.2f}\n  24h: {arrow} {abs(chg):.2f}%")
    _cache_set(f"crypto_{sym}",result)
    return result


# ── SPORTS ─────────────────────────────────────────────────────────────────────
def GetSports(query:str="cricket") -> str:
    q_clean = query.strip() or "cricket"
    cached  = _cache_get(f"sports_{re.sub(r'[^a-z0-9]','_',q_clean.lower())[:20]}")
    if cached: return cached
    sport_q = {"ipl":"IPL+2025+match+score+result","cricket":"India+cricket+score+today",
               "football":"ISL+football+India+score","fifa":"FIFA+football+today"}
    matched = next((v for k,v in sport_q.items() if k in q_clean.lower()),None)
    search  = matched or urllib.parse.quote(f"{q_clean} score result 2025")
    txt     = _fetch_text(f"https://news.google.com/rss/search?q={search}&hl=en-IN&gl=IN&ceid=IN:en")
    results = []
    if txt:
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",txt)
        if not titles: titles = re.findall(r"<title>([^<]{10,200})</title>",txt)
        for t in titles[1:5]:
            t = re.sub(r"\s*-\s*(Google News|ESPN|Cricbuzz).*","",t).strip()
            if t: results.append(f"  • {t}")
    if not results: return f"No sports results for '{q_clean}'."
    now    = datetime.datetime.now().strftime("%d %b %Y  %I:%M %p")
    result = f"{q_clean.title()} Sports — {now}:\n"+"\n".join(results)
    _cache_set(f"sports_{re.sub(r'[^a-z0-9]','_',q_clean.lower())[:20]}",result)
    return result


# ── TRANSLATE ──────────────────────────────────────────────────────────────────
_LANGS = {"hindi":"hi","marathi":"mr","tamil":"ta","telugu":"te","kannada":"kn",
          "bengali":"bn","gujarati":"gu","punjabi":"pa","urdu":"ur","french":"fr",
          "german":"de","spanish":"es","japanese":"ja","chinese":"zh","arabic":"ar",
          "russian":"ru","portuguese":"pt","korean":"ko","italian":"it","odia":"or"}

def TranslateText(text:str,target_lang:str) -> str:
    code = _LANGS.get(target_lang.lower().strip(),target_lang.lower().strip())
    try:
        from deep_translator import GoogleTranslator
        r = GoogleTranslator(source="auto",target=code).translate(text)
        if r: return f"Translation to {target_lang.title()}:\n  {r}"
    except ImportError: pass
    except Exception as e: print(f"  [Translate] {e}")
    try:
        url = (f"https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl=auto&tl={code}&dt=t&q={urllib.parse.quote(text)}")
        txt = _fetch_text(url)
        if txt:
            data = json.loads(txt)
            r    = "".join(p[0] for p in data[0] if p[0])
            if r: return f"Translation to {target_lang.title()}:\n  {r}"
    except Exception: pass
    return f"Translation failed. Install: pip install deep-translator"


# ── JOBS (routes to advanced_jobs) ────────────────────────────────────────────
def GetJobs(job_type:str="government",count:int=6) -> str:
    try:
        from Backend.Automation.advanced_jobs import handle_advanced_jobs
        return handle_advanced_jobs(f"jobs {job_type}")
    except ImportError:
        # Fallback RSS
        q   = urllib.parse.quote(f"{job_type} jobs India 2025 recruitment")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
        txt = _fetch_text(url)
        if not txt: return f"Could not fetch {job_type} jobs."
        titles  = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>",txt)
        results = [f"  {i}. {t}" for i,t in enumerate(titles[1:count+1],1)]
        return f"{job_type.title()} Jobs:\n" + "\n".join(results) if results else f"No {job_type} jobs found."


# ── COMMAND ROUTER ─────────────────────────────────────────────────────────────
def handle_realtime_command(command:str) -> str:
    cmd = command.strip()
    lc  = cmd.lower()

    if lc.startswith("weather"):
        return GetWeather(re.sub(r"^weather\s*","",cmd,flags=re.I).strip())
    if lc.startswith("news"):
        return GetNews(re.sub(r"^news\s*","",cmd,flags=re.I).strip())
    if lc.startswith("stock"):
        return GetStock(re.sub(r"^stock\s*","",cmd,flags=re.I).strip())
    if lc.startswith("crypto"):
        return GetCrypto(re.sub(r"^crypto\s*","",cmd,flags=re.I).strip())
    if lc.startswith("sports"):
        return GetSports(re.sub(r"^sports\s*","",cmd,flags=re.I).strip())
    if lc.startswith("translate"):
        m = re.search(r"translate\s+(.+?)\s+to\s+(.+)",cmd,re.I)
        if m: return TranslateText(m.group(1),m.group(2))
        return "Format: translate <text> to <language>"

    # Route all job-related to advanced_jobs
    if any(w in lc for w in ("jobs","job","vacancy","recruitment","psu","gate","upsc",
                              "ssc","railway","bank","defence","fresher","intern",
                              "data analyst","software","python","ml","ai")):
        try:
            from Backend.Automation.advanced_jobs import handle_advanced_jobs
            return handle_advanced_jobs(cmd)
        except ImportError:
            return GetJobs(cmd)

    return f"Unknown command: {cmd}"


if __name__ == "__main__":
    import os, sys
    _s = os.path.dirname(os.path.abspath(__file__))
    _r = os.path.join(_s,"..","..")
    os.chdir(_r); sys.path.insert(0,_r)

    tests = [
        "weather Bhopal","news technology","stock TCS","crypto BTC",
        "sports IPL","translate hello to hindi",
        "jobs upsc","jobs data analyst","jobs gate psu","jobs ssc",
    ]
    print("\n=== REALTIME DATA v3.0 ===\n")
    for t in tests:
        print(f"{'='*50}\nCommand: {t}\n{'─'*50}")
        print(handle_realtime_command(t))