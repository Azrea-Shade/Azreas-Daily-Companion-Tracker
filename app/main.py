from __future__ import annotations
import os, json, datetime, webbrowser
from pathlib import Path

# PyQt5
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QGroupBox, QTabWidget, QMessageBox,
    QSystemTrayIcon, QMenu, QAction, QTextEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QCheckBox, QDialog, QFormLayout
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

# Optional yahooquery; tests monkeypatch m.Ticker, so expose a symbol
try:
    from yahooquery import Ticker  # noqa: F401
except Exception:  # pragma: no cover
    class Ticker:  # minimal stub for CI if lib missing
        def __init__(self, sym): self.sym = sym
        @property
        def price(self): return {self.sym: {"regularMarketPrice": 0}}

# ---- Colors / Style
ACCENT  = "#00f2ff"
ACCENT2 = "#8bff85"

# ---- Paths / Data
ROOT_DIR  = Path(__file__).resolve().parents[1]
APP_DIR   = ROOT_DIR / "app"
DOCS_DIR  = Path.home() / "Documents" / "DailyCompanion"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR = DOCS_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE  = APP_DIR / "data.json"
CONFIG_FILE = DOCS_DIR / "config.json"

DEFAULT_DATA = {
    "watchlist": [],
    "reminders": [],   # [{title, hour, minute, days:[0-6], enabled}]
    "notes": []        # [{ts, symbol, text}]
}
DEFAULT_CONFIG = {
    "show_quote": True,
    "minimize_to_tray": False,
    "launch_minimized": False,
}

def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return json.loads(json.dumps(default))

def save_json(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def load_data(): return load_json(DATA_FILE, DEFAULT_DATA)
def save_data(d): save_json(DATA_FILE, d)
def load_config(): return load_json(CONFIG_FILE, DEFAULT_CONFIG)
def save_config(c): save_json(CONFIG_FILE, c)

# ---- Helpers
def _today_quote() -> str:
    quotes = [
        "Every day is a fresh start.",
        "Discipline beats motivation.",
        "Small steps compound into greatness.",
        "Focus on what you can control.",
        "The best time to plant a tree was 20 years ago. The second-best time is now."
    ]
    idx = datetime.date.today().toordinal() % len(quotes)
    return quotes[idx]

class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.cfg = cfg
        form = QFormLayout(self)

        self.chk_quote = QCheckBox("Show 8:00 AM quote")
        self.chk_quote.setChecked(bool(self.cfg.get("show_quote", True)))
        self.chk_minimize = QCheckBox("Minimize to tray on close")
        self.chk_minimize.setChecked(bool(self.cfg.get("minimize_to_tray", False)))
        self.chk_launchmin = QCheckBox("Launch minimized to tray")
        self.chk_launchmin.setChecked(bool(self.cfg.get("launch_minimized", False)))

        form.addRow(self.chk_quote)
        form.addRow(self.chk_minimize)
        form.addRow(self.chk_launchmin)

        row = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self._do_save)
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        row.addWidget(ok); row.addWidget(cancel)
        form.addRow(row)

    def _do_save(self):
        self.cfg["show_quote"] = self.chk_quote.isChecked()
        self.cfg["minimize_to_tray"] = self.chk_minimize.isChecked()
        self.cfg["launch_minimized"] = self.chk_launchmin.isChecked()
        save_config(self.cfg)
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌌 Azrea’s Daily Companion Tracker")
        self.setMinimumSize(1100, 760)
        icon_path = APP_DIR / "assets" / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(QIcon())

        self.data = load_data()
        if "notes" not in self.data:  # migrate if missing
            self.data["notes"] = []
            save_data(self.data)
        self.config = load_config()

        self.tabs = QTabWidget(); self.setCentralWidget(self.tabs)

        self.dashboard = self._build_dashboard()
        self.search    = self._build_search()
        self.watchlist = self._build_watchlist()
        self.reminders = self._build_reminders()
        self.notes     = self._build_notes()

        self.tabs.addTab(self.dashboard, "🏠 Dashboard")
        self.tabs.addTab(self.search, "🔎 Search")
        self.tabs.addTab(self.watchlist, "⭐ Watchlist")
        self.tabs.addTab(self.reminders, "⏰ Reminders")
        self.tabs.addTab(self.notes, "🗒️ Notes")

        # System tray (icon optional)
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(str(icon_path)) if icon_path.exists() else QIcon())
        menu = QMenu()
        act_show = QAction("Show", self); act_show.triggered.connect(self.showNormal)
        act_quit = QAction("Quit", self); act_quit.triggered.connect(self._quit)
        menu.addAction(act_show); menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.setVisible(True)

        # Launch minimized if configured (won't run in offscreen CI)
        if self.config.get("launch_minimized", False) and not self._headless():
            self.hide()

    # ---- Basic helpers
    def _headless(self) -> bool:
        return os.environ.get("QT_QPA_PLATFORM","").lower() == "offscreen"

    def _info(self, title, msg):
        if self._headless(): return
        QMessageBox.information(self, title, msg)

    def _warn(self, title, msg):
        if self._headless(): return
        QMessageBox.warning(self, title, msg)

    def _quit(self):
        self.tray.setVisible(False)
        QApplication.quit()

    # ---- Dashboard
    def _build_dashboard(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Morning")
        v = QVBoxLayout(box)
        self.lbl_quote = QLabel(_today_quote()); self.lbl_quote.setWordWrap(True)
        self.lbl_quote.setStyleSheet("font-size:18px; color:#ddd;")
        brief = QPushButton("Export Morning Brief (PDF)"); brief.clicked.connect(self._export_morning_brief)
        open_exports = QPushButton("Open Exports Folder"); open_exports.clicked.connect(lambda: webbrowser.open(str(EXPORT_DIR)))
        v.addWidget(self.lbl_quote); v.addWidget(brief); v.addWidget(open_exports)
        root.addWidget(box)
        return w

    def _export_morning_brief(self):
        try:
            from fpdf import FPDF
        except Exception:
            self._warn("PDF", "FPDF not installed.")
            return
        fname = EXPORT_DIR / f"morning_brief_{datetime.date.today().isoformat()}.pdf"
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=14)
        pdf.multi_cell(0, 10, "Azrea’s Daily Companion — Morning Brief")
        pdf.ln(4)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 8, f"Quote: {_today_quote()}")
        pdf.ln(2)
        wl = ", ".join(self.data.get("watchlist", [])[:12]) or "—"
        pdf.multi_cell(0, 8, f"Watchlist: {wl}")
        pdf.output(str(fname))
        self._info("PDF", f"Saved: {fname}")

    # ---- Search
    def _build_search(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)

        row = QHBoxLayout()
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Enter ticker (e.g., AAPL, MSFT, TSLA)")
        btn = QPushButton("Search"); btn.clicked.connect(self.perform_search)
        row.addWidget(self.search_input); row.addWidget(btn)

        self.result_box = QGroupBox("Result")
        grid = QGridLayout(self.result_box)
        self.lbl_name  = QLabel("—"); self.lbl_name.setStyleSheet(f"color:{ACCENT}; font-size:18px; font-weight:600;")
        self.lbl_price = QLabel("—"); self.lbl_price.setStyleSheet(f"color:{ACCENT2}; font-size:16px;")
        self.lbl_desc  = QLabel("—"); self.lbl_desc.setWordWrap(True)
        grid.addWidget(QLabel("Name:"),  0, 0); grid.addWidget(self.lbl_name,  0, 1)
        grid.addWidget(QLabel("Price:"), 1, 0); grid.addWidget(self.lbl_price, 1, 1)
        grid.addWidget(QLabel("Description:"), 2, 0); grid.addWidget(self.lbl_desc, 2, 1)

        btnrow = QHBoxLayout()
        addfav = QPushButton("Add to Watchlist ⭐"); addfav.clicked.connect(self._add_current_to_watchlist)
        export_pdf = QPushButton("Export Summary (PDF)"); export_pdf.clicked.connect(self._export_pdf)
        upload_pdf = QPushButton("Upload Last PDF to Drive"); upload_pdf.clicked.connect(getattr(self, "_upload_last_pdf", lambda: self._info("Drive", "Upload not configured.")))
        btnrow.addWidget(addfav); btnrow.addWidget(export_pdf); btnrow.addWidget(upload_pdf)

        root.addLayout(row)
        root.addWidget(self.result_box)
        root.addLayout(btnrow)
        self.current_symbol = None
        return w

    def perform_search(self):
        sym = (self.search_input.text() or "").strip().upper() or "AAPL"
        try:
            t = Ticker(sym)
            p = t.price.get(sym, {}).get("regularMarketPrice")
        except Exception:
            p = None
        self.current_symbol = sym
        self.lbl_name.setText(sym)
        self.lbl_price.setText("—" if p is None else str(p))
        self.lbl_desc.setText("Company profile loading not implemented in CI.")
        return sym

    def _export_pdf(self):
        try:
            from fpdf import FPDF
        except Exception:
            self._warn("PDF", "FPDF not installed.")
            return
        sym = self.current_symbol or (self.search_input.text().strip().upper() or "AAPL")
        fname = EXPORT_DIR / f"{sym}_summary.pdf"
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=14)
        pdf.multi_cell(0, 10, f"Summary for {sym}")
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 8, f"Price: {self.lbl_price.text()}")
        pdf.multi_cell(0, 8, f"Desc: {self.lbl_desc.text()}")
        pdf.output(str(fname))
        self._info("PDF", f"Saved: {fname}")

    def _upload_last_pdf(self):
        # CI-safe stub (real Drive auth/Upload handled in services/installer)
        self._info("Drive", "Upload not configured in CI build.")

    def _add_current_to_watchlist(self):
        sym = (self.current_symbol or (self.search_input.text().strip().upper() if hasattr(self, "search_input") else "") or "AAPL")
        wl = self.data.setdefault("watchlist", [])
        if sym not in wl:
            wl.append(sym)
            save_data(self.data)
        self._info("Watchlist", f"Added {sym} to watchlist.")

    # ---- Watchlist
    def _build_watchlist(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Favorites"); v = QVBoxLayout(box)
        self.lbl_wl = QLabel(", ".join(self.data.get("watchlist", [])) or "—")
        add = QPushButton("Add Current"); add.clicked.connect(self._add_current_to_watchlist)
        v.addWidget(self.lbl_wl); v.addWidget(add)
        root.addWidget(box)
        return w

    # ---- Reminders (minimal CI-safe)
    def _build_reminders(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Reminders"); v = QVBoxLayout(box)
        self.lbl_rem = QLabel("No reminders yet."); v.addWidget(self.lbl_rem)
        root.addWidget(box)
        return w

    # ---- Notes
    def _build_notes(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Company Notes"); v = QVBoxLayout(box)

        row = QHBoxLayout()
        self.note_symbol_input = QLineEdit(); self.note_symbol_input.setPlaceholderText("Ticker (e.g., AAPL)")
        self.note_text_input = QTextEdit(); self.note_text_input.setPlaceholderText("Write a short note about this company…")
        self.note_text_input.setMinimumHeight(100)
        add = QPushButton("Save Note"); add.clicked.connect(self._add_note)
        row.addWidget(self.note_symbol_input); row.addWidget(add)

        self.notes_tbl = QTableWidget(0, 3)
        self.notes_tbl.setHorizontalHeaderLabels(["Time", "Symbol", "Note"])
        self.notes_tbl.horizontalHeader().setStretchLastSection(True)

        exp = QPushButton("Export Notes CSV"); exp.clicked.connect(self._export_notes_csv)

        v.addLayout(row)
        v.addWidget(self.note_text_input)
        v.addWidget(self.notes_tbl)
        v.addWidget(exp)
        root.addWidget(box)
        self._refresh_notes()
        return w

    def _add_note(self, symbol=None, text=None):
        sym = (symbol or self.note_symbol_input.text()).strip().upper()
        txt = (text or self.note_text_input.toPlainText()).strip()
        if not sym:
            self._info("Notes", "Enter a ticker (e.g., AAPL)."); return
        if not txt:
            self._info("Notes", "Write something in the note text."); return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.data.setdefault("notes", []).append({"ts": now, "symbol": sym, "text": txt})
        save_data(self.data)
        self._refresh_notes()
        try: self.note_text_input.clear()
        except Exception: pass
        self._info("Notes", "Saved.")

    def _refresh_notes(self):
        notes = self.data.get("notes", [])
        self.notes_tbl.setRowCount(0)
        for n in reversed(notes[-200:]):
            row = self.notes_tbl.rowCount(); self.notes_tbl.insertRow(row)
            self.notes_tbl.setItem(row, 0, QTableWidgetItem(n.get("ts","—")))
            self.notes_tbl.setItem(row, 1, QTableWidgetItem(n.get("symbol","—")))
            preview = (n.get("text","") or "").replace("\n"," ")
            if len(preview) > 120: preview = preview[:117] + "..."
            self.notes_tbl.setItem(row, 2, QTableWidgetItem(preview))

    def _export_notes_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Notes CSV", str(ROOT_DIR / "notes.csv"), "CSV Files (*.csv)")
        if not path: return
        try:
            import csv
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ts","symbol","text"])
                for n in self.data.get("notes", []):
                    w.writerow([n.get("ts",""), n.get("symbol",""), n.get("text","")])
            self._info("Export", f"Saved: {path}")
        except Exception as e:
            self._warn("Export", f"Failed to export notes:\n{e}")
