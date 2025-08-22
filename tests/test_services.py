import builtins
from unittest.mock import patch
from app import services as s

def test_wiki_summary_parsing():
    with patch("app.services._get_json") as gj:
        gj.side_effect = [
            ["q", ["Apple Inc."], [], []],  # opensearch result
            {"title": "Apple Inc.", "extract": "Apple is a company", "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Apple_Inc."}}},
        ]
        data = s.get_wiki_company_summary("AAPL")
        assert data["title"] == "Apple Inc."
        assert "Apple is a company" in data["extract"]
        assert "wikipedia" in data["url"]

def test_sec_mapping_and_filings():
    with patch("app.services._get_json") as gj:
        # first call: company_tickers.json
        # second call: submissions/CIK json
        gj.side_effect = [
            {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
            {"filings":{"recent":{"form":["10-Q","8-K"], "filingDate":["2025-08-01","2025-07-20"], "primaryDocDescription":["Quarterly report","Current report"]}}}
        ]
        cik = s.get_cik_for_ticker("AAPL")
        assert cik == 320193
        filings = s.get_recent_filings_by_cik(cik, limit=5)
        assert filings[0]["form"] == "10-Q"

def test_company_intel():
    with patch("app.services._get_json") as gj:
        # 1: opensearch, 2: wiki summary, 3: tickers, 4: submissions
        gj.side_effect = [
            ["q", ["Apple Inc."], [], []],
            {"title": "Apple Inc.", "extract": "Apple is a company", "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Apple_Inc."}}},
            {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
            {"filings":{"recent":{"form":["10-Q"], "filingDate":["2025-08-01"], "primaryDocDescription":["Quarterly report"]}}}
        ]
        out = s.get_company_intel("AAPL")
        assert out["ticker"] == "AAPL"
        assert out["wiki"]["title"] == "Apple Inc."
        assert out["filings"][0]["form"] == "10-Q"
