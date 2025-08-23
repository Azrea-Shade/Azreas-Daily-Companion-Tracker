import os, time, json, re
from datetime import datetime, timedelta

# Optional keys via environment (loaded by main app with python-dotenv)
NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY", "")
FINNHUB_KEY      = os.getenv("FINNHUB_KEY", "")
ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_KEY", "")

# --- Price (Yahoo) ---
try:
    from yahooquery import Ticker
except Exception:  # CI/patch safety
    class Ticker:  # pragma: no cover
        def __init__(self, *_a, **_k): pass
        @property
        def price(self): return {}

def get_price(symbol:str):
    """
    Returns float price if available, else None. Uses yahooquery (no API key).
    """
    try:
        t = Ticker(symbol)
        # Common mappings
        d = t.price.get(symbol) if isinstance(t.price, dict) else None
        px = None
        if d and isinstance(d, dict):
            px = d.get("regularMarketPrice") or d.get("postMarketPrice") or d.get("preMarketPrice")
        if px is None and isinstance(t.price, dict):
            # Sometimes the dict is flat
            px = t.price.get("regularMarketPrice")
        if px is None:
            return None
        return float(px)
    except Exception:
        return None

# --- Legal / filings (SEC EDGAR) (no key needed) ---
import urllib.request
import urllib.error

_UA = {"User-Agent": "AzreaCompanion/1.0 (contact: none@example.com)"}  # SEC guidance: add UA

def _get_json(url:str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

# Company tickers mapping (heavy once, cache)
_EDGAR_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_SUBMISSIONS_TMPL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"

def sec_map_for_ticker(ticker:str):
    """
    Returns dict like {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."} or None.
    """
    try:
        m = _get_json(_EDGAR_MAP_URL)
        t = ticker.upper()
        for _, row in m.items():
            if (row.get("ticker") or "").upper() == t:
                return row
    except Exception:
        return None
    return None

def get_recent_filings(cik:int, limit:int=10):
    try:
        d = _get_json(_SEC_SUBMISSIONS_TMPL.format(cik=int(cik)))
        recent = d.get("filings",{}).get("recent",{})
        forms = recent.get("form",[])[:limit]
        dates = recent.get("filingDate",[])[:limit]
        descs = recent.get("primaryDocDescription",[])[:limit]
        out = []
        for i, f in enumerate(forms):
            out.append({
                "form": f,
                "filingDate": dates[i] if i < len(dates) else "",
                "description": descs[i] if i < len(descs) else ""
            })
        return out
    except Exception:
        return []

# --- News: RSS (no key) + optional APIs ---
def _safe_import_feedparser():
    try:
        import feedparser  # type: ignore
        return feedparser
    except Exception:
        return None

_DEFAULT_RSS = [
    # Broad business/markets headlines:
    "https://www.businesswire.com/portal/site/home/news/",
    "https://www.globenewswire.com/RssFeed/subjectcode/40-Mergers%20and%20Acquisitions/feedTitle/GlobeNewswire%20-%20M%26A",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.prnewswire.com/rss/finance-banking-latest-news.rss",
]

def fetch_rss_items(limit:int=30, extra_feeds=None):
    fp = _safe_import_feedparser()
    if fp is None:
        return []
    feeds = list(_DEFAULT_RSS)
    if extra_feeds:
        feeds.extend(x for x in extra_feeds if isinstance(x,str))
    items = []
    for url in feeds:
        try:
            d = fp.parse(url)
            for e in d.get("entries", [])[:limit]:
                items.append({
                    "title": e.get("title",""),
                    "summary": e.get("summary",""),
                    "link": e.get("link",""),
                    "published": e.get("published",""),
                })
        except Exception:
            continue
    return items[:limit]

def newsapi_search(query:str, limit:int=20):
    if not NEWSAPI_KEY:
        return []
    import urllib.parse
    q = urllib.parse.quote_plus(query)
    url = f"https://newsapi.org/v2/everything?q={q}&pageSize={limit}&sortBy=publishedAt&apiKey={NEWSAPI_KEY}"
    try:
        return _get_json(url).get("articles",[])
    except Exception:
        return []

def finnhub_company_news(symbol:str, _days:int=7, limit:int=50):
    if not FINNHUB_KEY:
        return []
    import datetime, urllib.parse
    to = datetime.date.today()
    fr = to - datetime.timedelta(days=_days)
    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={fr}&to={to}&token={FINNHUB_KEY}"
    try:
        data = _get_json(url)
        if isinstance(data, list):
            return data[:limit]
        return []
    except Exception:
        return []

# --- Signal helpers ---------------------------------------------------------
_BUYOUT_WORDS = ["acquisition", "buyout", "merger", "merges", "acquires", "takeover", "going private"]

def headline_matches_buyout(text:str)->bool:
    s = (text or "").lower()
    return any(w in s for w in _BUYOUT_WORDS)

def headline_matches_keywords(text:str, keywords:list)->bool:
    s = (text or "").lower()
    for k in keywords or []:
        if (k or "").lower() in s:
            return True
    return False
