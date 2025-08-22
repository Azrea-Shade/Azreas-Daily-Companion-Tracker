import os, glob
from pathlib import Path
from unittest.mock import patch

# Force offscreen to avoid display
os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from app import main as m

class FakeTicker:
    def __init__(self, symbols):
        if isinstance(symbols, (list, tuple, set)):
            syms = list(symbols)
        else:
            syms = [symbols]
        self._syms = [s if isinstance(s, str) else str(s) for s in syms]
        self.price = {s: {"regularMarketPrice": 123.45} for s in self._syms}
        self.quote_type = {s: {"longName": "Apple Inc.", "shortName": "Apple"} for s in self._syms}
        self.asset_profile = {s: {"longBusinessSummary": "Apple is a company that makes devices."} for s in self._syms}

    # mimic .price.get(...) usage (dict interface is enough)

def test_mainwindow_basic_flow(tmp_path, monkeypatch):
    # Redirect export dir to a temp so CI stays clean
    m.EXPORT_DIR = tmp_path

    # Mock YahooQuery ticker
    monkeypatch.setattr(m, "Ticker", FakeTicker)

    w = m.MainWindow()

    # Simulate a search for AAPL
    w.search_input.setText("AAPL")
    w.perform_search()
    assert "Apple" in w.lbl_name.text()
    assert w.lbl_price.text().startswith("$")

    # Add to watchlist
    w._add_current_to_watchlist()
    assert "AAPL" in w.data.get("watchlist", [])

    # Export a PDF summary
    if m.canvas is None:
        # If ReportLab missing, just skip the PDF assertion
        return
    before = set(glob.glob(str(tmp_path / "*.pdf")))
    w._export_pdf()
    after = set(glob.glob(str(tmp_path / "*.pdf")))
    assert len(after - before) >= 1
