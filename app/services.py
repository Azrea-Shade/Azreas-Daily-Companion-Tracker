import os, requests
from datetime import datetime

NEWSAPI_KEY       = os.getenv("NEWSAPI_KEY")
ALPHAVANTAGE_KEY  = os.getenv("ALPHAVANTAGE_KEY")

SEC_BASE   = "https://data.sec.gov/api"
HEADERS    = {"User-Agent": "Azreas-Daily-Companion-Tracker (contact: shade.azrea@gmail.com)"}

def _get_json(url, params=None, headers=None, timeout=12):
    h = dict(HEADERS)
    if headers: h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.json()

# -------- Wikipedia --------
def get_wiki_company_summary(ticker: str):
    try:
        q = ticker.upper()
        op = _get_json("https://en.wikipedia.org/w/api.php",
                       params={"action":"opensearch","limit":1,"namespace":0,"format":"json","search":q})
        title = (op[1][0] if op and op[1] else q)
        page = _get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}")
        return {
            "title": page.get("title", title),
            "extract": page.get("extract", ""),
            "url": page.get("content_urls",{}).get("desktop",{}).get("page", "")
        }
    except Exception:
        return {"title": ticker, "extract": "", "url": ""}

# -------- SEC EDGAR --------
def _sec_map_for_ticker():
    return _get_json("https://www.sec.gov/files/company_tickers.json")

def get_cik_for_ticker(ticker: str):
    m = _sec_map_for_ticker()
    t = ticker.upper()
    for _k, v in m.items():
        if v.get("ticker","").upper() == t:
            return int(v.get("cik_str"))
    return None

def get_recent_filings_by_cik(cik: int, limit: int = 5):
    try:
        j = _get_json(f"{SEC_BASE}/submissions/CIK{int(cik):010d}.json")
        rec = j.get("filings",{}).get("recent",{})
        items = []
        for form, date, desc in zip(rec.get("form",[]), rec.get("filingDate",[]), rec.get("primaryDocDescription",[])):
            items.append({"form": form, "date": date, "desc": desc})
            if len(items) >= limit: break
        return items
    except Exception:
        return []

# -------- Prices: YahooQuery → Alpha Vantage fallback --------
def price_for(symbol: str):
    # Try YahooQuery (no key). Import lazily so tests can monkeypatch.
    try:
        from yahooquery import Ticker
        t = Ticker(symbol)
        px = None
        try:
            px = t.price[symbol].get("regularMarketPrice")
        except Exception:
            px = getattr(t, "price", {}).get("regularMarketPrice")
        if px is not None:
            return float(px)
    except Exception:
        pass
    # Fallback to Alpha Vantage if key exists
    if ALPHAVANTAGE_KEY:
        try:
            j = _get_json("https://www.alphavantage.co/query",
                          params={"function":"GLOBAL_QUOTE","symbol":symbol,"apikey":ALPHAVANTAGE_KEY})
            q = j.get("Global Quote",{}).get("05. price")
            if q: return float(q)
        except Exception:
            pass
    return None

# -------- News: NewsAPI (optional key) --------
def news_latest(symbol: str, limit: int = 10):
    key = NEWSAPI_KEY
    if not key:
        return []
    try:
        j = _get_json("https://newsapi.org/v2/everything",
                      params={"q":symbol, "pageSize":limit, "sortBy":"publishedAt", "language":"en"},
                      headers={"X-Api-Key": key})
        out = []
        for a in j.get("articles", []):
            out.append({
                "title": a.get("title",""),
                "source": a.get("source",{}).get("name",""),
                "url": a.get("url",""),
                "publishedAt": a.get("publishedAt","")
            })
        return out
    except Exception:
        return []

# -------- Composite --------
def get_company_intel(ticker: str):
    t = ticker.upper()
    wiki    = get_wiki_company_summary(t)
    cik     = get_cik_for_ticker(t)
    filings = get_recent_filings_by_cik(cik, limit=5) if cik else []
    px      = price_for(t)
    return {"ticker": t, "wiki": wiki, "cik": cik, "filings": filings, "price": px}
