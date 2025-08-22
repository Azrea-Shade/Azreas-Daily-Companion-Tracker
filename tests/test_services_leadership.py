from unittest.mock import patch
from app import services as s

def test_leadership_from_wikidata():
    def fake_get_json(url, params=None, headers=None, timeout=20):
        url = url or ""
        if "w/api.php" in url and params and params.get("action") == "opensearch":
            return ["q", ["Apple Inc."], ["desc"], ["https://en.wikipedia.org/wiki/Apple_Inc."]]
        if "api/rest_v1/page/summary" in url:
            return {"title":"Apple Inc.","extract":"Apple is a company","content_urls":{"desktop":{"page":"https://en.wikipedia.org/wiki/Apple_Inc."}},"wikibase_item":"Q312"}
        if "w/api.php" in url and params and params.get("action") == "wbgetentities" and params.get("ids") == "Q312":
            return {
                "entities": {
                    "Q312": {
                        "labels":{"en":{"value":"Apple Inc."}},
                        "claims": {
                            "P169":[{"mainsnak":{"datavalue":{"value":{"id":"Q1035"}}}}],
                            "P488":[{"mainsnak":{"datavalue":{"value":{"id":"Q2001"}}}}],
                            "P1037":[{"mainsnak":{"datavalue":{"value":{"id":"Q3001"}}}}],
                            "P127":[{"mainsnak":{"datavalue":{"value":{"id":"Q4001"}}}}]
                        }
                    }
                }
            }
        # label lookups
        if "w/api.php" in url and params and params.get("action") == "wbgetentities" and params.get("ids") in {"Q1035","Q2001","Q3001","Q4001"}:
            lbl = {
                "Q1035":"Tim Cook",
                "Q2001":"Arthur Levinson",
                "Q3001":"Luca Maestri",
                "Q4001":"Public shareholders"
            }[params["ids"]]
            return {"entities": {params["ids"]: {"labels":{"en":{"value":lbl}}}}}
        if "company_tickers.json" in url:
            return {"0":{"cik_str":320193,"ticker":"AAPL","title":"Apple Inc."}}
        if "submissions/CIK" in url:
            return {"filings":{"recent":{"form":["10-Q"],"filingDate":["2025-08-01"],"primaryDocDescription":["Quarterly report"]}}}
        raise AssertionError(f"Unexpected URL in fake_get_json: {url}, params={params}")
    with patch("app.services._get_json", side_effect=fake_get_json):
        out = s.get_company_intel("AAPL")
        assert out["ticker"] == "AAPL"
        assert out["wiki"]["title"] == "Apple Inc."
        assert out["filings"][0]["form"] == "10-Q"
        # leadership
        leads = out["leadership"]
        assert "Tim Cook" in leads.get("ceo", [])
        assert "Arthur Levinson" in leads.get("chairperson", [])
        assert "Luca Maestri" in leads.get("managers", [])
        assert "Public shareholders" in leads.get("owners", [])
