import os, time, threading
from pathlib import Path
from typing import Callable, Dict, Any, List

from . import providers as P

DATA_PATH = Path(__file__).resolve().parent / "data.json"

def _load():
    import json
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"watchlist":[], "reminders":[], "alerts":[]}

def _save(d):
    import json
    DATA_PATH.write_text(json.dumps(d, indent=2), encoding="utf-8")

class AlertsManager:
    """
    Holds alert rules and evaluates them on tick().
    Notifies via a callback: notify(title:str, message:str).
    """
    def __init__(self, notify:Callable[[str,str],None], data:Dict[str,Any]=None):
        self.notify = notify
        self.data = data if data is not None else _load()
        self._last_news_seen = set()  # naive dedupe

    # ---- CRUD ----
    def add_price_alert(self, symbol:str, above:float=None, below:float=None):
        a = {"type":"price","symbol":symbol.upper(),"above":above,"below":below,"enabled":True}
        self.data.setdefault("alerts",[]).append(a); _save(self.data); return a

    def add_keyword_alert(self, keywords:List[str]):
        a = {"type":"keyword","keywords":[k.strip() for k in keywords if k.strip()],"enabled":True}
        self.data.setdefault("alerts",[]).append(a); _save(self.data); return a

    def add_legal_alert(self, symbol:str):
        a = {"type":"legal","symbol":symbol.upper(),"enabled":True}
        self.data.setdefault("alerts",[]).append(a); _save(self.data); return a

    def to_table(self):
        out = []
        for a in self.data.get("alerts",[]):
            if a.get("type")=="price":
                cond = []
                if a.get("above") is not None: cond.append(f"> {a['above']}")
                if a.get("below") is not None: cond.append(f"< {a['below']}")
                out.append([a.get("type"), a.get("symbol"), " & ".join(cond)])
            elif a.get("type")=="keyword":
                out.append([a.get("type"), "-", ", ".join(a.get("keywords",[]))])
            elif a.get("type")=="legal":
                out.append([a.get("type"), a.get("symbol"), "SEC Filings"])
        return out

    # ---- evaluation ----
    def _tick_price(self):
        for a in self.data.get("alerts",[]):
            if a.get("type") != "price" or not a.get("enabled"): continue
            sym = a.get("symbol","").upper()
            if not sym: continue
            px = P.get_price(sym)
            if px is None: continue
            above = a.get("above"); below = a.get("below")
            if (above is not None and px > float(above)) or (below is not None and px < float(below)):
                self.notify("Price Alert", f"{sym} hit ${px:.2f} (rule: {('> '+str(above)) if above is not None else ''} {('< '+str(below)) if below is not None else ''})")

    def _tick_legal(self):
        for a in self.data.get("alerts",[]):
            if a.get("type") != "legal" or not a.get("enabled"): continue
            sym = a.get("symbol","").upper()
            mp = P.sec_map_for_ticker(sym)
            if not mp: continue
            filings = P.get_recent_filings(mp.get("cik_str"))
            for f in filings[:3]:
                key = f"{sym}:{f.get('form')}:{f.get('filingDate')}"
                if key in self._last_news_seen: continue
                self._last_news_seen.add(key)
                self.notify("SEC Filing", f"{sym} {f.get('form')} on {f.get('filingDate')} — {f.get('description','')}")

    def _tick_news(self):
        # RSS first (free)
        items = P.fetch_rss_items(limit=25)
        for it in items:
            head = (it.get("title") or "")[:200]
            if not head: continue
            # keyword rules
            for a in self.data.get("alerts",[]):
                if a.get("type") != "keyword" or not a.get("enabled"): continue
                if P.headline_matches_keywords(head, a.get("keywords",[])):
                    key = "rss:" + head
                    if key in self._last_news_seen: continue
                    self._last_news_seen.add(key)
                    self.notify("News (keyword)", head)

            # buyout detection from RSS
            if P.headline_matches_buyout(head):
                key = "buyout:" + head
                if key in self._last_news_seen: continue
                self._last_news_seen.add(key)
                self.notify("M&A / Buyout", head)

        # Optional: NewsAPI and Finnhub (if keys present)
        if P.NEWSAPI_KEY:
            arts = P.newsapi_search("merger OR acquisition OR buyout", limit=20)
            for a in arts:
                head = (a.get("title") or "")[:200]
                if not head: continue
                key = "newsapi:" + head
                if key in self._last_news_seen: continue
                self._last_news_seen.add(key)
                if P.headline_matches_buyout(head):
                    self.notify("M&A (NewsAPI)", head)

    def tick(self):
        # call in GUI timer or background thread
        try: self._tick_price()
        except Exception: pass
        try: self._tick_legal()
        except Exception: pass
        try: self._tick_news()
        except Exception: pass
