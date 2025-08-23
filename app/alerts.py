import os, time, threading, json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import requests

# Simple NewsAPI fetcher (feature 1)
def fetch_company_news(api_key: str, query: str, page_size: int = 10) -> List[Dict[str, Any]]:
    if not api_key:
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": page_size, "apiKey": api_key}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("articles", []) or []
    except Exception:
        return []

# SEC recent filings by CIK (feature 1)
def fetch_recent_sec_filings(cik: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not cik:
        return []
    try:
        cik_norm = str(cik).zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_norm}.json"
        headers = {"User-Agent": "AzreaDailyCompanion/1.0 (admin@example.com)"}
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        j = r.json()
        forms = j.get("filings", {}).get("recent", {})
        out = []
        for i, form in enumerate(forms.get("form", [])[:limit]):
            out.append({
                "form": form,
                "date": (forms.get("filingDate", [""]*9999)[:limit] + [""])[i],
                "desc": (forms.get("primaryDocDescription", [""]*9999)[:limit] + [""])[i],
            })
        return out
    except Exception:
        return []

# Background watcher skeleton (feature 1 + 5)
class Watcher:
    def __init__(self, owner, poll_seconds=300):
        self.owner = owner
        self.poll_seconds = poll_seconds
        self._stop = False
        self._th = None

    def start(self):
        if self._th or self.owner._headless() or os.environ.get("CI"):
            return
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()

    def stop(self):
        self._stop = True

    def _run(self):
        while not self._stop:
            try:
                self.owner._check_price_alerts()
                self.owner._maybe_refresh_alert_feed()
            except Exception:
                pass
            time.sleep(self.poll_seconds)
