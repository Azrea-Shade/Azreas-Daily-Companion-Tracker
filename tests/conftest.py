import os, sys
from pathlib import Path
import pytest

# Make "import app" work in CI and locally
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(autouse=True)
def clear_sec_cache():
    """Ensure each test starts fresh by removing the SEC ticker cache file."""
    try:
        from app import services as s
        cache_file = (s.CACHE / "company_tickers.json")
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass
    yield
    try:
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass
