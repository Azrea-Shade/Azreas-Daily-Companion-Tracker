import json, time, re
from pathlib import Path
from typing import Dict, List, Any
import requests

ROOT = Path(__file__).resolve().parent.parent

# -------- HTTP helpers (mockable) --------
def _get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 20) -> Any:
    r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _get(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 20) -> requests.Response:
    r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r

# -------- Core functions --------
def _wiki_opensearch(q: str) -> dict:
    url = "https://en.wikipedia.org/w/api.php"
    params = {"action":"opensearch","limit":5,"namespace":0,"format":"json","search":q}
    res = _get_json(url, params=params)
    # Normalize
    return {"q": q, "titles": res[1], "descs": res[2], "links": res[3]}

def _wiki_summary(title: str) -> dict:
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    data = _get_json(url)
    out = {
        "title": data.get("title"),
        "extract": data.get("extract"),
        "url": (data.get("content_urls",{}) or {}).get("desktop",{}).get("page"),
        "wikibase_item": data.get("wikibase_item")
    }
    return out

def _wikidata_leadership(qid: str) -> dict:
    """Return leadership/ownership lists using Wikidata claims. Tries to resolve labels."""
    if not qid:
        return {"ceo":[], "chairperson":[], "managers":[], "owners":[]}
    # get entities with claims + labels
    url = "https://www.wikidata.org/w/api.php"
    data = _get_json(url, params={"action":"wbgetentities","ids":qid,"props":"labels|claims","languages":"en","format":"json"})
    ent = (data.get("entities") or {}).get(qid) or {}
    labels = ent.get("labels", {})
    def label_for(id_):
        # single-entity resolution step if the claim points to another entity
        try:
            d = _get_json("https://www.wikidata.org/w/api.php",
                          params={"action":"wbgetentities","ids":id_,"props":"labels","languages":"en","format":"json"})
            return ((d.get("entities") or {}).get(id_,"").get("labels") or {}).get("en",{}).get("value") or id_
        except Exception:
            return id_

    def pull(claim_prop: str) -> List[str]:
        out = []
        for claim in (ent.get("claims",{}).get(claim_prop) or []):
            mainsnak = claim.get("mainsnak") or {}
            dv = (mainsnak.get("datavalue") or {}).get("value")
            if not dv: continue
            # item link
            if isinstance(dv, dict) and "id" in dv:
                out.append(label_for(dv["id"]))
            # string literal fallback
            elif isinstance(dv, str):
                out.append(dv)
        # uniq while preserving order
        uniq = []
        for n in out:
            if n and n not in uniq:
                uniq.append(n)
        return uniq

    leadership = {
        "ceo":        pull("P169"),   # CEO
        "chairperson":pull("P488"),   # chairperson
        "managers":   pull("P1037"),  # manager/director
        "owners":     pull("P127"),   # owned by
    }
    return leadership

def _sec_map_for_ticker(ticker: str) -> dict:
    """Get SEC mapping for a ticker -> CIK/official name; use cached public JSON if available."""
    url = "https://www.sec.gov/files/company_tickers.json"
    # Set a respectful User-Agent with contact; replace email as needed in main app configs.
    headers = {"User-Agent": "DailyCompanion/1.0 (contact: shade.azrea@gmail.com)"}
    try:
        data = _get_json(url, headers=headers, timeout=30)
    except Exception:
        return {}
    # data like {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    for _, row in data.items():
        if (row.get("ticker") or "").upper() == ticker.upper():
            return {"cik": str(row.get("cik_str")), "ticker": row.get("ticker"), "title": row.get("title")}
    return {}

def _sec_recent_filings(cik: str, limit: int = 10) -> List[dict]:
    if not cik: return []
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    headers = {"User-Agent": "DailyCompanion/1.0 (contact: shade.azrea@gmail.com)"}
    try:
        data = _get_json(url, headers=headers, timeout=30)
    except Exception:
        return []
    rec = ((data.get("filings") or {}).get("recent") or {})
    forms   = rec.get("form") or []
    dates   = rec.get("filingDate") or []
    descs   = rec.get("primaryDocDescription") or []
    out = []
    for i in range(min(len(forms), len(dates), len(descs), limit)):
        out.append({"form": forms[i], "date": dates[i], "desc": descs[i]})
    return out

def get_company_intel(query: str) -> Dict[str, Any]:
    """
    Aggregates:
      - Wikipedia summary (+ url)
      - SEC: ticker → CIK → recent filings
      - Wikidata: leadership (ceo, chairperson, managers) and owners
    Returns dict with keys: name, ticker, wiki{title, url, extract}, filings[], leadership{}
    """
    q = (query or "").strip()
    out = {"name":"", "ticker":"", "wiki":{}, "filings":[], "leadership":{"ceo":[], "chairperson":[], "managers":[], "owners":[]}}

    # Try ticker mapping first if looks like a ticker
    is_ticker = len(q) <= 6 and q.upper() == q and re.fullmatch(r"[A-Z.\-]+", q or "") is not None
    title = None
    wiki_qid = None

    try:
        if not is_ticker:
            # Use opensearch to get canonical title
            osr = _wiki_opensearch(q)
            title = (osr.get("titles") or [None])[0]
        else:
            # Map ticker to official title via SEC (often matches Wikipedia)
            sec = _sec_map_for_ticker(q.upper())
            if sec:
                out["ticker"] = sec.get("ticker") or q.upper()
                out["name"]   = sec.get("title") or q.upper()
                title = sec.get("title")
            else:
                title = q  # fallback
    except Exception:
        title = q

    # Wikipedia summary
    try:
        if title:
            ws = _wiki_summary(title)
            out["wiki"] = ws
            out["name"] = out["name"] or (ws.get("title") or "")
            wiki_qid = ws.get("wikibase_item")
    except Exception:
        pass

    # SEC filings (if we have/guess ticker)
    try:
        if not out.get("ticker") and is_ticker:
            out["ticker"] = q.upper()
        # Try sec mapping again if needed
        if not out.get("name") or not out.get("ticker"):
            sec2 = _sec_map_for_ticker(out.get("ticker") or q)
            if sec2:
                out["ticker"] = sec2.get("ticker") or out.get("ticker")
                out["name"] = out["name"] or sec2.get("title")
                out["filings"] = _sec_recent_filings(sec2.get("cik"))
        else:
            sec2 = _sec_map_for_ticker(out["ticker"])
            if sec2:
                out["filings"] = _sec_recent_filings(sec2.get("cik"))
    except Exception:
        pass

    # Wikidata leadership/ownership
    try:
        if wiki_qid:
            out["leadership"] = _wikidata_leadership(wiki_qid)
    except Exception:
        pass

    return out
