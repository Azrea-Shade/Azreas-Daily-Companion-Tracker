# Alerts & Data Providers

This app supports:
- **Yahoo (yahooquery)** for price (no key)
- **SEC EDGAR** for filings (no key)
- **RSS feeds** (BusinessWire, PR Newswire, WSJ Markets, GlobeNewswire) for headlines (no key)

Optional upgrades (set in `.env` or Windows Environment Variables):
- `NEWSAPI_KEY` – NewsAPI.org for richer news search
- `FINNHUB_KEY` – Finnhub company news & fundamentals
- `ALPHAVANTAGE_KEY` – extra price/fx endpoints (not required)

Runtime:
- In GUI, alerts run **only if** `ENABLE_ALERTS=1` and display is not headless.
- CI (headless) never starts background timers.
