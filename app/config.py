from pathlib import Path
import os

# API keys (leave blank and app will gracefully degrade in CI / offline)
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY", "")
NEWSAPI_KEY          = os.getenv("NEWSAPI_KEY", "")
ALPHAVANTAGE_KEY     = os.getenv("ALPHAVANTAGE_KEY", "")

# SEC polite headers (SEC asks for identifying UA)
SEC_USER_AGENT       = os.getenv("SEC_USER_AGENT", "AzreasDailyCompanion/1.0 (contact: your-email@example.com)")

APP_DIR              = Path(__file__).resolve().parent
DATA_FILE            = APP_DIR / "data.json"
EXPORT_DIR           = APP_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
