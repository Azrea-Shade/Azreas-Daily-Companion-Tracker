import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:
    from yahooquery import Ticker
except Exception:
    Ticker = None  # CI may monkeypatch or skip

# ---------- Shared helpers ----------

def _get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Any:
    """HTTP GET JSON with safe fallbacks; test doubles will patch this."""
    r = requests.get(url, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _sec_headers() -> Dict[str, str]:
    # SEC fair access requires a descriptive UA & contact email
    email = os.environ.get("CONTACT_EMAIL", "Shade.azrea@gmail.com")
    return {
        "User-Agent": f"azrea-daily-companion/1.0 ({email})",
        "Accept": "application/json",
    }

# ---------- Wikipedia ----------

def get_wiki_company_summary(symbol_or_name: str) -> Dict[str, Any]:
    """
    1) Resolve a likely title via OpenSearch
    2) Fetch summary via REST v1
    Returns {'title', 'extract', 'url'}
    """
    q = symbol_or_name.strip()
    try:
        # resolve a name (OpenSearch)
        search = _get_json(
            f"https://en.wikipedia.org/w/api.php?action=opensearch&search={q}&limit=1&namespace=0&format=json"
        )
        title = search[1][0] if search and search[1] else q
        # summary
        summ = _get_json(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        )
        return {
            "title": summ.get("title", title),
            "extract": summ.get("extract", ""),
            "url": (summ.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
        }
    except Exception:
        return {"title": q, "extract": "", "url": ""}

# ---------- SEC EDGAR map + filings ----------

def _sec_map_for_ticker() -> Dict[str, Dict[str, Any]]:
    """
    Returns the SEC company_tickers map (ticker -> obj with cik_str, title).
    Structure example: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    We'll normalize into {TICKER: {...}} for easier lookup.
    """
    raw = _get_json("https://www.sec.gov/files/company_tickers.json", headers=_sec_headers())
    out = {}
    for _, v in (raw or {}).items():
        t = str(v.get("ticker", "")).upper()
        if t:
            out[t] = v
    return out

def get_cik_for_ticker(ticker: str) -> Optional[int]:
    t = (ticker or "").upper().strip()
    try:
        m = _sec_map_for_ticker()
        if t in m:
            # Ensure int, tests expect an int not str
            return int(m[t].get("cik_str"))
    except Exception:
        pass
    return None

def _pad_cik(cik: int | str) -> str:
    c = str(cik).strip()
    return c.zfill(10)

def get_recent_filings_by_cik(cik: int | str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Returns a simplified list of recent filings:
    [{'form': '10-Q', 'date': 'YYYY-MM-DD', 'desc': 'Quarterly report'}, ...]
    """
    try:
        padded = _pad_cik(cik)
        j = _get_json(f"https://data.sec.gov/submissions/CIK{padded}.json", headers=_sec_headers())
        recent = (j.get("filings", {}) or {}).get("recent", {}) or {}
        forms  = recent.get("form", []) or []
        dates  = recent.get("filingDate", []) or []
        descs  = recent.get("primaryDocDescription", []) or []
        out = []
        for i in range(min(limit, len(forms), len(dates))):
            out.append({"form": forms[i], "date": dates[i], "desc": (descs[i] if i < len(descs) else "")})
        return out
    except Exception:
        return []

# ---------- Prices (Yahoo then AV fallback) ----------

def price_from_yahoo(symbol: str) -> Optional[float]:
    if Ticker is None:
        return None
    try:
        t = Ticker(symbol)
        px = t.price.get(symbol, {}).get("regularMarketPrice")
        if px is None and isinstance(t.price, dict):
            px = t.price.get("regularMarketPrice")
        return float(px) if px is not None else None
    except Exception:
        return None

def price_from_alpha_vantage(symbol: str) -> Optional[float]:
    key = os.environ.get("ALPHAVANTAGE_KEY")
    if not key:
        return None
    try:
        j = _get_json(
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={key}"
        )
        q = j.get("Global Quote", {})
        val = q.get("05. price")
        return float(val) if val is not None else None
    except Exception:
        return None

def get_realtime_price(symbol: str) -> Optional[float]:
    return price_from_yahoo(symbol) or price_from_alpha_vantage(symbol)

# ---------- News ----------

def get_news(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    NewsAPI if NEWSAPI_KEY is present; otherwise return empty (safe for CI).
    Returns [{'title','url','source','publishedAt'}...]
    """
    key = os.environ.get("NEWSAPI_KEY")
    if not key:
        return []
    try:
        j = _get_json(
            f"https://newsapi.org/v2/everything?q={requests.utils.quote(query)}&sortBy=publishedAt&pageSize={limit}",
            headers={"X-Api-Key": key},
        )
        arts = j.get("articles", []) or []
        out = []
        for a in arts[:limit]:
            out.append({
                "title": a.get("title",""),
                "url": a.get("url",""),
                "source": (a.get("source") or {}).get("name",""),
                "publishedAt": a.get("publishedAt",""),
            })
        return out
    except Exception:
        return []

# ---------- Roll-up ----------

def get_company_intel(symbol: str) -> Dict[str, Any]:
    """
    Convenience aggregator:
    {
      'ticker': 'AAPL',
      'price': 123.45 or None,
      'wiki': {...},
      'cik': 320193 or None,
      'filings': [...],
      'news': [...]
    }
    """
    sym = (symbol or "").upper().strip()
    wiki = get_wiki_company_summary(sym)
    price = get_realtime_price(sym)
    cik = get_cik_for_ticker(sym)
    filings = get_recent_filings_by_cik(cik, limit=5) if cik else []
    news = get_news(sym, limit=10)

    return {
        "ticker": sym,
        "price": price,
        "wiki": wiki,
        "cik": cik,
        "filings": filings,
        "news": news,
    }
