import os, json, time
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests

SEC_HEADERS = {
    # SEC requires a descriptive UA with contact email
    "User-Agent": "DailyCompanion/1.0 (Shade.azrea@gmail.com)"
}
TIMEOUT = 12
CACHE = Path(__file__).resolve().parent / "cache"
CACHE.mkdir(exist_ok=True)

def _get_json(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

# ---------- Wikipedia ----------
def wiki_search_title(query: str) -> Optional[str]:
    # Use Opensearch to get best title
    data = _get_json("https://en.wikipedia.org/w/api.php", {
        "action": "opensearch",
        "search": query,
        "limit": 1,
        "namespace": 0,
        "format": "json"
    })
    if not data or len(data) < 2:
        return None
    titles = data[1]
    return titles[0] if titles else None

def wiki_summary(title: str) -> Optional[Dict[str, Any]]:
    # Wikipedia REST summary
    title_path = title.replace(" ", "_")
    data = _get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title_path}")
    if not data: return None
    return {
        "title": data.get("title"),
        "extract": data.get("extract"),
        "url": (data.get("content_urls") or {}).get("desktop", {}).get("page"),
    }

def get_wiki_company_summary(query: str) -> Optional[Dict[str, Any]]:
    title = wiki_search_title(query)
    if not title: return None
    return wiki_summary(title)

# ---------- SEC (EDGAR) ----------
def _load_ticker_cik_cache_path() -> Path:
    return CACHE / "company_tickers.json"

def _load_ticker_cik_cache() -> Optional[List[Dict[str, Any]]]:
    p = _load_ticker_cik_cache_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None

def _save_ticker_cik_cache(data: List[Dict[str, Any]]):
    try:
        _load_ticker_cik_cache_path().write_text(json.dumps(data))
    except Exception:
        pass

def refresh_ticker_cik_cache() -> Optional[List[Dict[str, Any]]]:
    # Download once; SEC serves a JSON mapping of tickers->CIK
    # https://www.sec.gov/files/company_tickers.json (object with numeric keys)
    data = _get_json("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS)
    if not data:
        return None
    arr: List[Dict[str, Any]] = []
    for _, row in data.items():
        # {cik_str, title, ticker}
        arr.append({
            "cik": int(row.get("cik_str") or 0),
            "ticker": (row.get("ticker") or "").upper(),
            "title": row.get("title") or ""
        })
    _save_ticker_cik_cache(arr)
    return arr

def get_cik_for_ticker(symbol: str) -> Optional[int]:
    symbol = (symbol or "").upper()
    cache = _load_ticker_cik_cache()
    if not cache:
        cache = refresh_ticker_cik_cache()
    if not cache:
        return None
    for row in cache:
        if row.get("ticker") == symbol:
            return int(row.get("cik") or 0)
    return None

def get_recent_filings_by_cik(cik: int, limit: int = 5) -> List[Dict[str, Any]]:
    # https://data.sec.gov/submissions/CIK##########.json
    if not cik: return []
    cik_str = f"{int(cik):010d}"
    data = _get_json(f"https://data.sec.gov/submissions/CIK{cik_str}.json", headers=SEC_HEADERS)
    if not data: return []
    filings = data.get("filings", {}).get("recent", {})
    forms  = filings.get("form", [])[:limit]
    dates  = filings.get("filingDate", [])[:limit]
    descs  = filings.get("primaryDocDescription", [])[:limit]
    out = []
    for i in range(min(len(forms), len(dates))):
        out.append({
            "form": forms[i],
            "date": dates[i],
            "desc": (descs[i] or "").strip() if i < len(descs) else ""
        })
    return out

# ---------- High-level aggregator ----------
def get_company_intel(query: str) -> Dict[str, Any]:
    """
    query can be a ticker (e.g., 'AAPL') or a company name.
    Returns: {
      'ticker': str|None,
      'name': str|None,
      'wiki': {'title','extract','url'}|None,
      'filings': list of {form,date,desc}
    }
    """
    q = (query or "").strip()
    if not q:
        return {"ticker": None, "name": None, "wiki": None, "filings": []}

    # Heuristic: if alnum <=5 treat as ticker
    ticker_guess = q.upper() if q.isalnum() and len(q) <= 5 else None
    name_guess = None

    wiki = get_wiki_company_summary(q)
    if wiki and wiki.get("title"):
        name_guess = wiki.get("title")

    filings = []
    if ticker_guess:
        cik = get_cik_for_ticker(ticker_guess)
        if cik:
            filings = get_recent_filings_by_cik(cik, limit=5)

    return {
        "ticker": ticker_guess,
        "name": name_guess,
        "wiki": wiki,
        "filings": filings
    }
