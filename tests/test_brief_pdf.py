import glob
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from app import main as m

app = QApplication.instance() or QApplication([])

def test_morning_brief_pdf(tmp_path, monkeypatch):
    # Redirect exports to tmp
    m.EXPORT_DIR = tmp_path
    w = m.MainWindow()
    # Ensure there is at least a deterministic quote text
    w.quote_label.setText("Test quote for morning brief.")
    before = set(glob.glob(str(tmp_path / "*.pdf")))
    if m.canvas is None:
        # If reportlab missing, just ensure calling doesn't crash
        w._export_morning_brief_pdf()
        return
    w._export_morning_brief_pdf()
    after = set(glob.glob(str(tmp_path / "*.pdf")))
    assert len(after - before) >= 1
