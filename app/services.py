import json, time
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from .config import OPENAI_API_KEY, NEWSAPI_KEY, ALPHAVANTAGE_KEY, SEC_USER_AGENT

# ---- Utilities (requests) ----
def _get_json(url: str, headers: Optional[Dict[str,str]]=None, params: Optional[Dict[str,Any]]=None) -> Any:
    h = {"User-Agent": SEC_USER_AGENT or "Mozilla/5.0"}
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, params=params, timeout=15)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return None

# ---- Wikipedia summary by ticker ----
def get_wiki_company_summary(ticker: str) -> Dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    # opensearch to resolve name
    q = _get_json(f"https://en.wikipedia.org/w/api.php", params={
        "action":"opensearch","search":ticker,"limit":1,"namespace":0,"format":"json"
    })
    title = (q[1][0] if (isinstance(q, list) and q and len(q)>1 and q[1]) else ticker)
    s = _get_json("https://en.wikipedia.org/api/rest_v1/page/summary/"+title)
    if not isinstance(s, dict): s = {}
    return {
        "title": s.get("title", title),
        "extract": s.get("extract",""),
        "url": (s.get("content_urls",{}) or {}).get("desktop",{}).get("page","")
    }

# ---- SEC mapping & filings ----
def get_cik_for_ticker(ticker: str) -> Optional[int]:
    ticker = (ticker or "").upper().strip()
    m = _get_json("https://www.sec.gov/files/company_tickers.json")
    if not isinstance(m, dict): return None
    for _, row in m.items():
        if str(row.get("ticker","")).upper() == ticker:
            try:
                return int(row.get("cik_str"))
            except Exception:
                return None
    return None

def get_recent_filings_by_cik(cik: int, limit: int = 5) -> List[Dict[str,Any]]:
    try:
        cik_str = str(int(cik)).zfill(10)
    except Exception:
        return []
    j = _get_json(f"https://data.sec.gov/submissions/CIK{cik_str}.json")
    out = []
    try:
        forms  = j["filings"]["recent"]["form"]
        dates  = j["filings"]["recent"]["filingDate"]
        descs  = j["filings"]["recent"].get("primaryDocDescription", [])
        for i, f in enumerate(forms[:limit]):
            out.append({
                "form": f,
                "date": dates[i] if i < len(dates) else "",
                "desc": descs[i] if i < len(descs) else ""
            })
    except Exception:
        pass
    return out

# ---- Alpha Vantage price (fallback to YahooQuery at app level) ----
def get_alpha_price(symbol: str) -> Optional[float]:
    if not ALPHAVANTAGE_KEY: return None
    try:
        j = _get_json("https://www.alphavantage.co/query", params={
            "function":"GLOBAL_QUOTE","symbol":symbol,"apikey":ALPHAVANTAGE_KEY
        })
        p = j.get("Global Quote",{}).get("05. price")
        return float(p) if p is not None else None
    except Exception:
        return None

# ---- NewsAPI simple search ----
def get_news_articles(query: str, limit: int = 5) -> List[Dict[str,Any]]:
    if not NEWSAPI_KEY: return []
    try:
        j = _get_json("https://newsapi.org/v2/everything", headers={"X-Api-Key": NEWSAPI_KEY}, params={
            "q":query, "pageSize":limit, "sortBy":"publishedAt", "language":"en"
        })
        arts = j.get("articles", []) if isinstance(j, dict) else []
        out = []
        for a in arts[:limit]:
            out.append({
                "title": a.get("title",""),
                "source": (a.get("source") or {}).get("name",""),
                "url": a.get("url",""),
                "publishedAt": a.get("publishedAt","")
            })
        return out
    except Exception:
        return []

# ---- Company Intel aggregator ----
def get_company_intel(ticker: str) -> Dict[str,Any]:
    t = (ticker or "").upper().strip()
    wiki = get_wiki_company_summary(t)
    cik  = get_cik_for_ticker(t)
    filings = get_recent_filings_by_cik(cik, limit=5) if cik else []
    news = get_news_articles(t, limit=5)
    return {"ticker": t, "wiki": wiki, "cik": cik, "filings": filings, "news": news}
