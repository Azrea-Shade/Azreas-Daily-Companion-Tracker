import os, sys, json, random, datetime, time, webbrowser, csv
from pathlib import Path
import logging
from app.utils import init_logger, is_windows, enable_startup, is_startup_enabled

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTabWidget, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QSystemTrayIcon, QMenu,
    QTextEdit, QDialog, QFormLayout, QSpinBox, QPlainTextEdit, QCheckBox,
    QFileDialog, QMessageBox, QShortcut, QTimeEdit
)

import requests
from packaging import version as _v

# --- Third-party optional imports ---
try:
    from yahooquery import Ticker
except Exception:
    Ticker = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:
    canvas = None

# Optional Google Drive (used only if present)
DriveAuthErr = None
try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
except Exception as _e:
    DriveAuthErr = _e
    GoogleAuth = GoogleDrive = None

# Services (company intel)
try:
    from app.services import get_company_intel
except Exception:
    get_company_intel = None

# ---------------- App Paths & Data ----------------
APP_DIR    = Path(__file__).resolve().parent
ROOT_DIR   = APP_DIR.parent
DATA_FILE  = APP_DIR / "data.json"
CONFIG_FILE= APP_DIR / "config.json"
EXPORT_DIR = ROOT_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
DOCS_DIR   = Path.home() / "Documents" / "DailyCompanion"
LOGGER = init_logger()
DOCS_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_VERSION = "1.0.0"
RELEASES_URL    = "https://github.com/Azrea-Shade/Azreas-Daily-Companion-Tracker/releases"

DEFAULT_LEGAL_WORDS = [
    "lawsuit","sues","sued","settlement","bankruptcy","chapter 11",
    "restructuring","investigation","sec","fraud","indictment","probe"
]

DEFAULT_CONFIG = {
    "minimize_to_tray": False,
    "launch_minimized": False,
    "price_alert_pct": 3,
    "news_poll_minutes": 15,
    "legal_keywords": ", ".join(DEFAULT_LEGAL_WORDS),
    "auto_quote_8am": True,
    "update_check_hours": 24,
    "openai_api_key": "",
    "newsapi_key": ""
}

QUOTES = [
    "Success is not final; failure is not fatal. It’s the courage to continue that counts.",
    "Opportunities don’t happen. You create them.",
    "Discipline is the bridge between goals and accomplishment.",
    "The best time to plant a tree was 20 years ago. The second best time is now.",
    "Act as if what you do makes a difference. It does.",
    "Small daily improvements are the key to staggering long-term results.",
]

# ---------------- Persistence ----------------
def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {
        "watchlist": [],
        "last_prices": {},
        "last_news_check": 0,
        "last_update_check": 0,
        "reminders": [],  # [{title, hour, minute, days:[0-6], enabled}]
        "notes": []  # [{ts, symbol, text}]
    }

def save_data(data):
    try:
        DATA_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print("Save error:", e)

def load_config():
    conf = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            disk = json.loads(CONFIG_FILE.read_text())
            conf.update({k:v for k,v in disk.items() if k in DEFAULT_CONFIG})
        except Exception:
            pass
    return conf

def save_config(cfg):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    except Exception as e:
        print("Config save error:", e)

def cfg_api_key(name, cfg):
    val = (cfg.get(name) or "").strip()
    if val:
        return val
    env = os.getenv(name.upper())
    return env or ""

# ---------------- UI Theme ----------------
ACCENT  = "#00e1ff"
ACCENT2 = "#ff4dff"
BG      = "#0b0f1a"
CARD    = "#0f1626"
BORDER  = "#22314d"
TEXT    = "#e8e8f0"

APP_STYLES = f"""
* {{
  font-family: Segoe UI, Arial;
  color: {TEXT};
}}
QMainWindow {{ background: {BG}; }}
QGroupBox {{
  background: {CARD};
  border: 1px solid {BORDER};
  border-radius: 12px;
  margin-top: 16px;
}}
QGroupBox::title {{ color: {ACCENT}; subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
QLineEdit, QTimeEdit {{ background:#0d1424; border:1px solid {BORDER}; border-radius:8px; padding:8px; }}
QPushButton {{ background:#111a2a; border:1px solid {BORDER}; border-radius:10px; padding:10px 16px; }}
QPushButton:hover {{ border-color:{ACCENT}; }}
QPushButton:pressed {{ background:#0c1322; }}
QTabBar::tab {{ background:#0d1424; padding:10px 16px; margin:2px; border:1px solid {BORDER};
  border-top-left-radius:10px; border-top-right-radius:10px; }}
QTabBar::tab:selected {{ color:{ACCENT}; border-bottom:2px solid {ACCENT}; }}
QTableWidget {{ background:#0d1424; gridline-color:{BORDER}; border:1px solid {BORDER}; border-radius:10px; }}
QTextEdit, QPlainTextEdit {{ background:#0d1424; border:1px solid {BORDER}; border-radius:10px; padding:10px; }}
QCheckBox {{ spacing: 8px; }}
"""

# ---------------- Helpers ----------------
class QuotePopup(QWidget):
    def __init__(self, quote: str):
        super().__init__()
        self.setWindowTitle("🌟 Daily Motivation")
        self.setStyleSheet(f"background:{CARD}; border:2px solid {ACCENT}; border-radius:16px;")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout(self)
        title = QLabel("🌟 Daily Motivation")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{ACCENT}; font-size:22px; font-weight:600;")
        quote_lbl = QLabel(f"\n{quote}")
        quote_lbl.setWordWrap(True)
        quote_lbl.setAlignment(Qt.AlignCenter)
        quote_lbl.setStyleSheet("font-size:18px;")
        ok = QPushButton("Got it")
        ok.clicked.connect(self.close)
        ok.setStyleSheet("font-weight:600;")
        layout.addWidget(title); layout.addWidget(quote_lbl); layout.addWidget(ok, alignment=Qt.AlignCenter)
        self.resize(520, 240)

def wrap_text(text: str, width: int):
    out = []; line = ""
    for word in (text or "").split():
        if len(line) + len(word) + 1 > width:
            out.append(line); line = word
        else:
            line = word if not line else line + " " + word
    if line: out.append(line)
    return out

# ---------------- Main Window ----------------
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
        self.config = load_config()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = self._build_dashboard()
        self.search    = self._build_search()
        self.watchlist = self._build_watchlist()
        self.reminders = self._build_reminders()
        self.notes = self._build_notes()
        self.ai        = self._build_ai_tab()
        if get_company_intel:
            self.intel = self._build_intel_tab()
            self.tabs.addTab(self.intel, "🏢 Company Intel")

        self.tabs.addTab(self.dashboard, "📊 Dashboard")
        self.tabs.addTab(self.search,    "🔍 Search")
        self.tabs.addTab(self.watchlist, "⭐ Watchlist")
        self.tabs.addTab(self.reminders, "⏰ Reminders")
        self.tabs.addTab(self.notes, "🗒️ Notes")
        self.tabs.addTab(self.ai,        "🤖 AI Assistant")

        self._init_tray()
        self._install_shortcuts()
        self._maybe_show_boot_quote()
        self._maybe_schedule_8am_quote()
        self._start_price_watcher()
        self._start_news_watcher()
        self._start_reminder_timer()
        self._maybe_check_updates_silent()

        # Honor launch_minimized setting
        try:
            if self.config.get("launch_minimized", False) and not self._headless():
                self.hide()
        except Exception:
            pass

    # ---------- headless-safe helpers ----------
    def _headless(self) -> bool:
        try:
            plat = QApplication.platformName().lower()
        except Exception:
            plat = ""
        return os.getenv("CI", "").lower() == "true" or plat == "offscreen"

    def _info(self, title: str, text: str):
        if self._headless():
            print(f"[INFO] {title}: {text}")
            return
        QMessageBox.information(self, title, text)

    def _warn(self, title: str, text: str):
        if self._headless():
            print(f"[WARN] {title}: {text}")
            return
        QMessageBox.warning(self, title, text)

    def _ask(self, title: str, text: str, default_yes: bool = True):
        if self._headless():
            print(f"[ASK] {title}: {text} -> {'Yes' if default_yes else 'No'}")
            return QMessageBox.Yes if default_yes else QMessageBox.No
        return QMessageBox.question(
            self, title, text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes if default_yes else QMessageBox.No
        )

    # ---------- Dashboard ----------
    def _build_dashboard(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)

        hero = QGroupBox("Welcome")
        h = QVBoxLayout(hero)
        title = QLabel("🌌 Azrea’s Daily Companion Tracker")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size:28px; color:{ACCENT}; font-weight:700;")
        subtitle = QLabel("Futuristic companion for research, quotes, reminders, and daily flow.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size:14px; color:#bfc7d6;")

        qcard = QGroupBox("Daily Quote")
        ql = QVBoxLayout(qcard)
        self.quote_label = QLabel(random.choice(QUOTES))
        self.quote_label.setWordWrap(True)
        self.quote_label.setStyleSheet("font-size:18px;")
        newq = QPushButton("New Quote ✨"); newq.clicked.connect(lambda: self.quote_label.setText(random.choice(QUOTES)))
        brief = QPushButton("Export Morning Brief (PDF)"); brief.clicked.connect(self._export_morning_brief_pdf)
        btnrow = QHBoxLayout();
        open_exports = QPushButton("Open Exports Folder")
        open_exports.clicked.connect(lambda: webbrowser.open(str(EXPORT_DIR)))
        open_logs = QPushButton("Open Logs Folder")
        open_logs.clicked.connect(lambda: webbrowser.open(str(DOCS_DIR / "logs")))
        btnrow.addWidget(newq); btnrow.addWidget(brief); btnrow.addWidget(open_exports); btnrow.addWidget(open_logs)
        ql.addWidget(self.quote_label); ql.addLayout(btnrow)

        self.next_label = QLabel("")
        self._update_next_8am_label()

        h.addWidget(title); h.addWidget(subtitle); h.addWidget(qcard); h.addWidget(self.next_label)
        root.addWidget(hero)
        return w

    # ---------- Shortcuts ----------
    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.tabs.setCurrentIndex(0))  # Dashboard
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.tabs.setCurrentIndex(1))  # Search
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.tabs.setCurrentIndex(2))  # Watchlist
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.tabs.setCurrentIndex(3))  # Reminders
        QShortcut(QKeySequence("Ctrl+5"), self, activated=lambda: self.tabs.setCurrentIndex(4))  # AI
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._export_pdf)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self._export_morning_brief_pdf)

    def _focus_search(self):
        self.tabs.setCurrentWidget(self.search)
        try:
            self.search_input.setFocus()
            self.search_input.selectAll()
        except Exception:
            pass

    # ---------- Search ----------
    def _build_search(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter ticker (e.g., AAPL, MSFT, TSLA)")
        btn = QPushButton("Search"); btn.clicked.connect(self.perform_search)
        row.addWidget(self.search_input); row.addWidget(btn)

        self.result_box = QGroupBox("Result")
        grid = QGridLayout(self.result_box)
        self.lbl_name  = QLabel("—")
        self.lbl_price = QLabel("—")
        self.lbl_desc  = QLabel("—")
        self.lbl_name.setStyleSheet(f"color:{ACCENT}; font-size:18px; font-weight:600;")
        self.lbl_price.setStyleSheet(f"color:{ACCENT2}; font-size:16px;")
        self.lbl_desc.setWordWrap(True)
        grid.addWidget(QLabel("Name:"),  0, 0); grid.addWidget(self.lbl_name,  0, 1)
        grid.addWidget(QLabel("Price:"), 1, 0); grid.addWidget(self.lbl_price, 1, 1)
        grid.addWidget(QLabel("Description:"), 2, 0); grid.addWidget(self.lbl_desc, 2, 1)

        btnrow = QHBoxLayout()
        addfav = QPushButton("Add to Watchlist ⭐"); addfav.clicked.connect(self._add_current_to_watchlist)
        export_pdf = QPushButton("Export Summary (PDF)"); export_pdf.clicked.connect(self._export_pdf)
        upload_pdf = QPushButton("Upload Last PDF to Drive"); upload_pdf.clicked.connect(getattr(self, "_upload_last_pdf", lambda: self._info("Drive", "Upload not configured (no Google Drive setup).")))
        btnrow.addWidget(addfav); btnrow.addWidget(export_pdf); btnrow.addWidget(upload_pdf)

        root.addLayout(row); root.addWidget(self.result_box); root.addLayout(btnrow)
        return w

    def perform_search(self):
        symbol = self.search_input.text().strip().upper()
        if not symbol:
            self._info("Search", "Please enter a ticker symbol (e.g., AAPL)."); return
        name = symbol; price = "—"; desc = "No description available."
        if Ticker is not None:
            try:
                t = Ticker(symbol)
                p = t.price.get(symbol) if hasattr(t, "price") else None
                if p and isinstance(p, dict):
                    price_val = p.get("regularMarketPrice") or p.get("postMarketPrice")
                    if price_val is not None: price = f"${price_val:.2f}"
                qt = t.quote_type.get(symbol) if hasattr(t, "quote_type") else None
                if qt and isinstance(qt, dict): name = qt.get("longName") or qt.get("shortName") or name
                profile = None
                try: profile = t.asset_profile.get(symbol) if hasattr(t, "asset_profile") else None
                except Exception: profile = None
                if profile and isinstance(profile, dict):
                    d = profile.get("longBusinessSummary")
                    if d: desc = d
            except Exception as e:
                print("Search error:", e)
        self.lbl_name.setText(name); self.lbl_price.setText(price); self.lbl_desc.setText(desc)
        self._last_search = {"symbol": symbol, "name": name, "price": price, "desc": desc}

    def _add_current_to_watchlist(self):
        item = getattr(self, "_last_search", None)
        if not item:
            self._info("Watchlist", "Search a ticker first."); return
        wl = self.data.get("watchlist", []); sym = item.get("symbol")
        if sym and sym not in wl:
            wl.append(sym); self.data["watchlist"] = wl; save_data(self.data); self._refresh_watchlist_table()
            LOGGER.info(f"Watchlist add: {sym}"); self._info("Watchlist", f"Added {sym} to watchlist.")
        else:
            self._info("Watchlist", f"{sym} is already in watchlist.")

    def _export_pdf(self):
        if canvas is None:
            self._warn("PDF", "ReportLab not installed. Add to requirements.txt."); return
        item = getattr(self, "_last_search", None)
        if not item:
            self._info("PDF", "Search a ticker first."); return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = EXPORT_DIR / f"{item['symbol']}_summary_{ts}.pdf"
        c = canvas.Canvas(str(fname), pagesize=letter)
        width, height = letter; y = height - 72
        c.setFont("Helvetica-Bold", 16); c.setFillColorRGB(0, 0.88, 1)
        c.drawString(72, y, f"Company: {item['name']} ({item['symbol']})")
        y -= 28; c.setFont("Helvetica", 12); c.setFillColorRGB(1, 1, 1); c.drawString(72, y, f"Price: {item['price']}")
        y -= 24; c.setFont("Helvetica", 11); text = c.beginText(72, y); text.setLeading(14)
        desc = item.get("desc") or "—"
        for line in wrap_text(desc, 90): text.textLine(line)
        c.drawText(text); c.showPage(); c.save()
        LOGGER.info(f"PDF saved: {fname}"); self._info("PDF", f"Saved: {fname}")

    # ---------- Morning Brief PDF ----------
    def _export_morning_brief_pdf(self):
        if canvas is None:
            self._warn("PDF", "ReportLab not installed. Add to requirements.txt."); return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = EXPORT_DIR / f"morning_brief_{ts}.pdf"
        c = canvas.Canvas(str(fname), pagesize=letter)
        width, height = letter; y = height - 72
        c.setFont("Helvetica-Bold", 18); c.setFillColorRGB(0, 0.88, 1)
        c.drawString(72, y, "Morning Brief"); y -= 22
        c.setFont("Helvetica", 11); c.setFillColorRGB(1,1,1)
        c.drawString(72, y, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"); y -= 20
        c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "Quote:"); y -= 16
        c.setFont("Helvetica", 11)
        for line in wrap_text(self.quote_label.text(), 95):
            c.drawString(72, y, line); y -= 14
            if y < 72: c.showPage(); y = height - 72
        wl = self.data.get("watchlist", [])
        c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "Watchlist:"); y -= 16
        c.setFont("Helvetica", 11)
        if wl:
            last = self.data.get("last_prices", {})
            for sym in wl:
                price = last.get(sym, "—")
                try:
                    if isinstance(price, (int, float)): price = f"{price:.2f}"
                except Exception:
                    pass
                c.drawString(72, y, f"{sym}: {price}"); y -= 14
                if y < 72: c.showPage(); y = height - 72
        else:
            c.drawString(72, y, "— (no symbols yet)"); y -= 14
        c.showPage(); c.save()
        LOGGER.info(f"PDF saved: {fname}"); self._info("PDF", f"Saved: {fname}")

    # ---------- Reminders ----------
    def _build_reminders(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Daily/Weekday Reminders"); v = QVBoxLayout(box)
        row1 = QHBoxLayout()
        self.rem_title = QLineEdit(); self.rem_title.setPlaceholderText("Title (e.g., 'Morning job scans')")
        self.rem_time = QTimeEdit(); self.rem_time.setDisplayFormat("HH:mm")
        self.chk_weekdays = [QCheckBox(d) for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]
        for c in self.chk_weekdays: c.setChecked(c.text() in ["Mon","Tue","Wed","Thu","Fri"])
        add = QPushButton("Add Reminder"); add.clicked.connect(self._add_reminder)
        row1.addWidget(self.rem_title); row1.addWidget(self.rem_time); [row1.addWidget(c) for c in self.chk_weekdays]; row1.addWidget(add)

        self.rem_tbl = QTableWidget(0, 4); self.rem_tbl.setHorizontalHeaderLabels(["Title","Time","Days","Enabled"])
        self.rem_tbl.horizontalHeader().setStretchLastSection(True)

        btns = QHBoxLayout()
        rm = QPushButton("Remove Selected"); rm.clicked.connect(self._remove_selected_rem)
        imp = QPushButton("Import CSV"); imp.clicked.connect(self._import_rem_csv)
        exp = QPushButton("Export CSV"); exp.clicked.connect(self._export_rem_csv)
        btns.addWidget(rm); btns.addWidget(imp); btns.addWidget(exp)

        v.addLayout(row1); v.addWidget(self.rem_tbl); v.addLayout(btns)
        root.addWidget(box)
        self._refresh_reminders()
        return w

    def _add_reminder(self):
        t = self.rem_title.text().strip()
        if not t:
            self._info("Reminders", "Enter a title."); return
        qtime = self.rem_time.time()
        hour, minute = int(qtime.hour()), int(qtime.minute())
        days = [i for i,c in enumerate(self.chk_weekdays) if c.isChecked()]
        if not days:
            self._info("Reminders", "Select at least one day."); return
        self.data.setdefault("reminders", []).append({
            "title": t, "hour": hour, "minute": minute, "days": days, "enabled": True
        })
        save_data(self.data)
        self._refresh_reminders()
        self._info("Reminders", "Added.")

    def _refresh_reminders(self):
        rems = self.data.get("reminders", [])
        self.rem_tbl.setRowCount(0)
        for r in rems:
            row = self.rem_tbl.rowCount(); self.rem_tbl.insertRow(row)
            days_names = " ".join(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i] for i in r.get("days",[]))
            self.rem_tbl.setItem(row, 0, QTableWidgetItem(r.get("title","—")))
            self.rem_tbl.setItem(row, 1, QTableWidgetItem(f'{r.get("hour",0):02d}:{r.get("minute",0):02d}'))
            self.rem_tbl.setItem(row, 2, QTableWidgetItem(days_names or "—"))
            self.rem_tbl.setItem(row, 3, QTableWidgetItem("Yes" if r.get("enabled",True) else "No"))

    def _remove_selected_rem(self):
        rows = sorted({i.row() for i in self.rem_tbl.selectedIndexes()}, reverse=True)
        if not rows:
            self._info("Reminders", "Select a row to remove."); return
        rems = self.data.get("reminders", [])
        for r in rows:
            title = self.rem_tbl.item(r,0).text()
            # remove by title & time match
            tm = self.rem_tbl.item(r,1).text() if self.rem_tbl.item(r,1) else ""
            hh, mm = (tm.split(":")+["0","0"])[:2]
            rems = [x for x in rems if not (x.get("title")==title and f'{x.get("hour",0):02d}:{x.get("minute",0):02d}'==f"{hh}:{mm}")]
            self.rem_tbl.removeRow(r)
        self.data["reminders"] = rems; save_data(self.data)

    def _import_rem_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Reminders CSV", str(ROOT_DIR), "CSV Files (*.csv)")
        if not path: return
        try:
            with open(path, newline="") as f:
                rdr = csv.reader(f)
                for row in rdr:
                    if len(row) < 4: continue
                    title, hh, mm, days_str = row[0], int(row[1]), int(row[2]), row[3]
                    days = [i for i,d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]) if d in days_str]
                    self.data.setdefault("reminders", []).append({"title":title,"hour":hh,"minute":mm,"days":days,"enabled":True})
            save_data(self.data); self._refresh_reminders()
            self._info("Import", "Reminders imported.")
        except Exception as e:
            self._warn("Import", f"Failed to import: {e}")

    def _export_rem_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Reminders CSV", str(ROOT_DIR / "reminders.csv"), "CSV Files (*.csv)")
        if not path: return
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                for r in self.data.get("reminders", []):
                    days_names = " ".join(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i] for i in r.get("days",[]))
                    w.writerow([r.get("title",""), r.get("hour",0), r.get("minute",0), days_names])
            self._info("Export", f"Saved: {path}")
        except Exception as e:
            self._warn("Export", f"Failed to export: {e}")

    def _start_reminder_timer(self):
        self._rem_timer = QTimer(self); self._rem_timer.timeout.connect(self._tick_reminders)
        self._rem_timer.start(60 * 1000)  # every minute
        self._tick_reminders()  # initial check

    def _tick_reminders(self):
        now = datetime.datetime.now()
        dow = now.weekday()  # 0=Mon
        for r in self.data.get("reminders", []):
            if not r.get("enabled", True): continue
            if dow not in (r.get("days") or []): continue
            if now.hour == int(r.get("hour",0)) and now.minute == int(r.get("minute",0)):
                msg = f"{r.get('title','Reminder')} — {now.strftime('%I:%M %p')}"
                if getattr(self, "tray", None) and QSystemTrayIcon.supportsMessages() and not self._headless():
                    self.tray.showMessage("Reminder", msg, QSystemTrayIcon.Information, 10000)
                else:
                    print(f"[REMINDER] {msg}")

    # ---------- AI Chat ----------
    def _build_ai_tab(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        wrap = QGroupBox("Ask the AI"); v = QVBoxLayout(wrap)
        self.chat_log = QTextEdit(); self.chat_log.setReadOnly(True)
        self.chat_input = QLineEdit(); self.chat_input.setPlaceholderText("Ask about a company, market, or strategy…")
        send = QPushButton("Send"); send.clicked.connect(self._send_chat)
        v.addWidget(self.chat_log)
        row = QHBoxLayout(); row.addWidget(self.chat_input); row.addWidget(send); v.addLayout(row)
        hint = QLabel("Tip: Set OPENAI_API_KEY / NEWSAPI_KEY (Settings or Environment).")
        hint.setStyleSheet("color:#93a1be; font-size:12px;")
        root.addWidget(wrap); root.addWidget(hint)
        return w

    def _send_chat(self):
        prompt = self.chat_input.text().strip()
        if not prompt: return
        self.chat_log.append(f"🧑‍💼 You: {prompt}")
        self.chat_input.clear()
        key = cfg_api_key("openai_api_key", self.config)
        if not key:
            self.chat_log.append("🤖 AI: (No OpenAI key set. Use Settings to add one.)"); return
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a concise financial research assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.5
            }
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                data = r.json(); content = data["choices"][0]["message"]["content"]
                self.chat_log.append(f"🤖 AI: {content}")
            else:
                self.chat_log.append(f"🤖 AI: Error {r.status_code}: {r.text[:300]}")
        except Exception as e:
            self.chat_log.append(f"🤖 AI: Error: {e}")

    # ---------- Company Intel ----------
    def _build_intel_tab(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        row = QHBoxLayout()
        self.intel_input = QLineEdit(); self.intel_input.setPlaceholderText("Enter ticker (AAPL) or company name (Apple Inc.)")
        btn = QPushButton("Get Intel"); btn.clicked.connect(self._do_intel_lookup)
        row.addWidget(self.intel_input); row.addWidget(btn)

        box = QGroupBox("Company Intel"); v = QVBoxLayout(box)
        self.intel_title  = QLabel("—"); self.intel_title.setStyleSheet(f"color:{ACCENT}; font-size:18px; font-weight:600;")
        self.intel_ticker = QLabel("—")
        self.intel_url    = QLabel("")
        self.intel_summary= QTextEdit(); self.intel_summary.setReadOnly(True); self.intel_summary.setMinimumHeight(120)
        self.intel_filings= QTextEdit(); self.intel_filings.setReadOnly(True); self.intel_filings.setMinimumHeight(100)
        self.intel_leads  = QTextEdit(); self.intel_leads.setReadOnly(True); self.intel_leads.setMinimumHeight(100)

        v.addWidget(QLabel("Name:"));    v.addWidget(self.intel_title)
        v.addWidget(QLabel("Ticker:"));  v.addWidget(self.intel_ticker)
        v.addWidget(QLabel("Wikipedia:")); v.addWidget(self.intel_url)
        v.addWidget(QLabel("Summary:")); v.addWidget(self.intel_summary)
        v.addWidget(QLabel("Recent SEC Filings:")); v.addWidget(self.intel_filings)
        v.addWidget(QLabel("Leadership & Owners:")); v.addWidget(self.intel_leads)

        brow = QHBoxLayout()
        qbrief = QPushButton("Export Quick Brief (PDF)"); qbrief.clicked.connect(lambda: self._export_intel_pdf(deep=False))
        ddeep = QPushButton("Export Deep Dossier (PDF)"); ddeep.clicked.connect(lambda: self._export_intel_pdf(deep=True))
        brow.addWidget(qbrief); brow.addWidget(ddeep)
        root.addLayout(row); root.addWidget(box); root.addLayout(brow)
        return w

    def _do_intel_lookup(self):
        if not get_company_intel:
            self._warn("Intel", "services module unavailable."); return
        q = self.intel_input.text().strip()
        if not q:
            self._info("Intel", "Enter a ticker or company name."); return
        data = get_company_intel(q)
        name = data.get("name") or "—"
        ticker = data.get("ticker") or "—"
        wiki = data.get("wiki") or {}
        url = wiki.get("url") or ""
        summary = wiki.get("extract") or "No summary available."
        filings = data.get("filings") or []
        leaders = data.get("leadership") or {}

        self.intel_title.setText(name)
        self.intel_ticker.setText(ticker)
        self.intel_url.setText(url)
        self.intel_summary.setPlainText(summary)

        if filings:
            lines = [f"{f.get('date','—')}  {f.get('form','—')}  {f.get('desc','')}" for f in filings]
            self.intel_filings.setPlainText("\n".join(lines))
        else:
            self.intel_filings.setPlainText("No recent filings found for this ticker (or not provided).")

        parts = []
        if leaders.get("ceo"):        parts.append("CEO: " + ", ".join(leaders["ceo"]))
        if leaders.get("chairperson"): parts.append("Chairperson: " + ", ".join(leaders["chairperson"]))
        if leaders.get("managers"):    parts.append("Managers: " + ", ".join(leaders["managers"]))
        if leaders.get("owners"):      parts.append("Owners: " + ", ".join(leaders["owners"]))
        self.intel_leads.setPlainText("\n".join(parts) if parts else "—")
        self._last_intel = {"name": name, "ticker": ticker, "url": url, "summary": summary, "filings": filings, "leadership": leaders}

    def _export_intel_pdf(self, deep: bool):
        if canvas is None:
            self._warn("PDF", "ReportLab not installed."); return
        intel = getattr(self, "_last_intel", None)
        if not intel:
            self._info("PDF", "Run a Company Intel search first."); return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = EXPORT_DIR / f"intel_{(intel['ticker'] or 'company')}_{ts}.pdf"
        c = canvas.Canvas(str(fname), pagesize=letter)
        width, height = letter; y = height - 72
        c.setFont("Helvetica-Bold", 16); c.setFillColorRGB(0, 0.88, 1)
        title = f"Company Intel: {intel['name']} ({intel['ticker']})" if intel['ticker'] != "—" else f"Company Intel: {intel['name']}"
        c.drawString(72, y, title)
        y -= 24; c.setFont("Helvetica", 11); c.setFillColorRGB(1,1,1)
        if intel.get("url"): c.drawString(72, y, f"Wikipedia: {intel['url']}")
        y -= 20
        c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "Summary:"); y -= 16
        c.setFont("Helvetica", 11)
        for line in wrap_text(intel.get("summary") or "—", 95):
            c.drawString(72, y, line); y -= 14
            if y < 72: c.showPage(); y = height - 72
        c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "Recent SEC Filings:"); y -= 16
        c.setFont("Helvetica", 11)
        filings = intel.get("filings") or []
        max_items = 12 if deep else 5
        for f in filings[:max_items]:
            line = f"{f.get('date','—')}  {f.get('form','—')}  {f.get('desc','')}"
            for part in wrap_text(line, 95):
                c.drawString(72, y, part); y -= 14
                if y < 72: c.showPage(); y = height - 72
        if deep and len(filings) > max_items:
            c.drawString(72, y, f"... (+{len(filings) - max_items} more)")
        # Leadership
        y -= 10; c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "Leadership & Owners:"); y -= 16
        c.setFont("Helvetica", 11)
        leaders = intel.get("leadership") or {}
        for key in ["ceo","chairperson","managers","owners"]:
            vals = leaders.get(key) or []
            if vals:
                line = f"{key.capitalize()}: {', '.join(vals)}"
                for part in wrap_text(line, 95):
                    c.drawString(72, y, part); y -= 14
                    if y < 72: c.showPage(); y = height - 72
        c.showPage(); c.save()
        LOGGER.info(f"PDF saved: {fname}"); self._info("PDF", f"Saved: {fname}")

    # ---------- Tray & Settings & Quotes ----------
    def _init_tray(self):
        if self._headless() or not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self);
        icon_path = APP_DIR / "assets" / "app_icon.ico"
        self.tray.setIcon(QIcon(str(icon_path)) if icon_path.exists() else QIcon())
        menu = QMenu()
        act_show  = menu.addAction("Show"); act_show.triggered.connect(self.showNormal)
        act_settings = menu.addAction("Settings…"); act_settings.triggered.connect(self._open_settings)
        act_quote = menu.addAction("Show Quote"); act_quote.triggered.connect(lambda: self._show_quote(random.choice(QUOTES)))
        act_update= menu.addAction("Check for Updates…"); act_update.triggered.connect(lambda: self._check_updates(manual=True))
        menu.addSeparator()
        act_quit  = menu.addAction("Quit"); act_quit.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu); self.tray.show()

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec_() == QDialog.Accepted:
            self.config = load_config()
            self._restart_news_timer()
            self._restart_8am_timer()

    def _maybe_show_boot_quote(self):
        if self.config.get("auto_quote_8am", True):
            self._show_quote(random.choice(QUOTES))

    def _show_quote(self, q: str):
        if self._headless():
            print(f"[QUOTE] {q}")
            return
        pop = QuotePopup(q); pop.show()
        if not hasattr(self, "_popups"): self._popups = []
        self._popups.append(pop)

    def _maybe_schedule_8am_quote(self):
        if not self.config.get("auto_quote_8am", True):
            self.next_label = getattr(self, "next_label", QLabel(""))
            try: self.next_label.setText("⏰ 8:00 AM quote disabled in Settings")
            except Exception: pass
            return
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target: target = target + datetime.timedelta(days=1)
        msec = int((target - now).total_seconds() * 1000)
        self.timer8 = QTimer(self); self.timer8.setSingleShot(True)
        self.timer8.timeout.connect(lambda: (self._show_quote(random.choice(QUOTES)),
                                             self._maybe_schedule_8am_quote(),
                                             self._update_next_8am_label()))
        self.timer8.start(max(msec, 1000))
        self._update_next_8am_label()

    def _restart_8am_timer(self):
        if hasattr(self, "timer8"):
            self.timer8.stop()
        self._maybe_schedule_8am_quote()

    def _update_next_8am_label(self):
        if not hasattr(self, "next_label"): return
        if not self.config.get("auto_quote_8am", True):
            self.next_label.setText("⏰ 8:00 AM quote disabled in Settings"); return
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target: target = target + datetime.timedelta(days=1)
        diff = target - now; hrs = diff.seconds // 3600; mins = (diff.seconds % 3600) // 60
        try: self.next_label.setText(f"⏰ Next 8:00 AM quote in ~ {hrs}h {mins}m")
        except Exception: pass

    # ---------- Watchlist ----------
    def _build_watchlist(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Favorites"); v = QVBoxLayout(box)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Symbol", "Price"])
        self.table.horizontalHeader().setStretchLastSection(True)

        btnrow = QHBoxLayout()
        refresh = QPushButton("Refresh Prices"); refresh.clicked.connect(self._refresh_watchlist_table)
        remove  = QPushButton("Remove Selected"); remove.clicked.connect(self._remove_selected)
        impbtn  = QPushButton("Import CSV"); impbtn.clicked.connect(self._import_watchlist_csv)
        expbtn  = QPushButton("Export CSV"); expbtn.clicked.connect(self._export_watchlist_csv)
        btnrow.addWidget(refresh); btnrow.addWidget(remove); btnrow.addWidget(impbtn); btnrow.addWidget(expbtn)

        v.addWidget(self.table); v.addLayout(btnrow)
        root.addWidget(box)
        self._refresh_watchlist_table()
        return w

    def _refresh_watchlist_table(self):
        wl = self.data.get("watchlist", [])
        self.table.setRowCount(0)
        if wl and Ticker is not None:
            try:
                t = Ticker(wl)
                p = t.price if hasattr(t, "price") else {}
                for sym in wl:
                    row = self.table.rowCount(); self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(sym))
                    val = "—"
                    try:
                        d = p.get(sym)
                        if d and isinstance(d, dict):
                            r = d.get("regularMarketPrice") or d.get("postMarketPrice")
                            if r is not None:
                                val = f"${float(r):.2f}"
                                self.data.setdefault("last_prices", {})[sym] = float(r)
                    except Exception:
                        pass
                    self.table.setItem(row, 1, QTableWidgetItem(val))
                save_data(self.data)
            except Exception as e:
                print("Watchlist fetch error:", e)
        else:
            for sym in wl:
                row = self.table.rowCount(); self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(sym))
                self.table.setItem(row, 1, QTableWidgetItem("—"))

    def _remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            self._info("Remove", "Select a row to remove."); return
        wl = self.data.get("watchlist", [])
        for r in rows:
            sym = self.table.item(r, 0).text()
            if sym in wl: wl.remove(sym)
            self.table.removeRow(r)
        self.data["watchlist"] = wl; save_data(self.data)

    def _import_watchlist_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Watchlist CSV", str(ROOT_DIR), "CSV Files (*.csv)")
        if not path: return
        try:
            added = 0
            wl = set(self.data.get("watchlist", []))
            with open(path, newline="") as f:
                rdr = csv.reader(f)
                for row in rdr:
                    if not row: continue
                    sym = row[0].strip().upper()
                    if sym and sym not in wl:
                        wl.add(sym); added += 1
            self.data["watchlist"] = sorted(wl)
            save_data(self.data); self._refresh_watchlist_table()
            self._info("Import", f"Imported {added} symbols.")
        except Exception as e:
            self._warn("Import", f"Failed to import:\n{e}")

    def _export_watchlist_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Watchlist CSV", str(ROOT_DIR / "watchlist.csv"), "CSV Files (*.csv)")
        if not path: return
        try:
            wl = self.data.get("watchlist", [])
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                for sym in wl:
                    w.writerow([sym])
            self._info("Export", f"Saved: {path}")
        except Exception as e:
            self._warn("Export", f"Failed to export:\n{e}")

    # ---------- AI tab defined above ----------

    # ---------- Tray & Settings & Quotes defined above ----------

    # ---------- Background watchers ----------
    def _start_price_watcher(self):
        self._price_timer = QTimer(self); self._price_timer.timeout.connect(self._check_prices)
        self._price_timer.start(5 * 60 * 1000)

    def _check_prices(self):
        wl = self.data.get("watchlist", [])
        if not wl or Ticker is None: return
        try:
            t = Ticker(wl); p = t.price if hasattr(t, "price") else {}
            changed = []
            pct = float(self.config.get("price_alert_pct", 3))
            for sym in wl:
                d = p.get(sym) if p else None; nowp = None
                if d and isinstance(d, dict): nowp = d.get("regularMarketPrice") or d.get("postMarketPrice")
                if nowp is None: continue
                try:
                    nowp = float(nowp)
                    prev = float(self.data.get("last_prices", {}).get(sym, nowp))
                    if prev > 0:
                        delta = (nowp - prev) / prev * 100.0
                        if abs(delta) >= pct: changed.append((sym, nowp, delta))
                    self.data.setdefault("last_prices", {})[sym] = nowp
                except Exception: pass
            if changed:
                msg = "; ".join([f"{s}: {p:.2f} ({d:+.1f}%)" for s,p,d in changed])
                if getattr(self, "tray", None) and QSystemTrayIcon.supportsMessages() and not self._headless():
                    self.tray.showMessage("Watchlist movement", msg, QSystemTrayIcon.Information, 10000)
                else:
                    print(f"[ALERT] {msg}")
                save_data(self.data)
        except Exception as e:
            print("Price watcher error:", e)

    def _start_news_watcher(self):
        self._news_timer = QTimer(self); self._news_timer.timeout.connect(self._check_news)
        mins = int(self.config.get("news_poll_minutes", 15))
        self._news_timer.start(max(5, mins) * 60 * 1000)

    def _restart_news_timer(self):
        if hasattr(self, "_news_timer"):
            try: self._news_timer.stop()
            except Exception: pass
        self._start_news_watcher()

    def _check_news(self):
        key = cfg_api_key("newsapi_key", self.config)
        if not key: return
        wl = self.data.get("watchlist", [])
        if not wl: return
        now = int(time.time()); last = int(self.data.get("last_news_check", 0))
        if now - last < 8*60: return
        try:
            custom_words = [w.strip().lower() for w in (self.config.get("legal_keywords","")).split(",") if w.strip()]
            legal_words = custom_words if custom_words else DEFAULT_LEGAL_WORDS
            q = " OR ".join(wl[:5])
            url = "https://newsapi.org/v2/everything"
            params = {"q": q, "language": "en", "pageSize": 10, "sortBy": "publishedAt", "apiKey": key}
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                alerts = []
                for a in articles:
                    title = (a.get("title") or "").lower()
                    if any(word in title for word in legal_words):
                        alerts.append(a.get("title") or "Legal/Regulatory headline")
                if alerts:
                    msg = " • ".join(alerts[:3])
                    if getattr(self, "tray", None) and QSystemTrayIcon.supportsMessages() and not self._headless():
                        self.tray.showMessage("Legal/News alert", msg, QSystemTrayIcon.Warning, 12000)
                    else:
                        print(f"[NEWS] {msg}")
                self.data["last_news_check"] = now; save_data(self.data)
        except Exception as e:
            print("News watcher error:", e)

    # ---------- Updates ----------
    def _maybe_check_updates_silent(self):
        hours = max(1, int(self.config.get("update_check_hours", 24)))
        now = int(time.time()); last = int(self.data.get("last_update_check", 0))
        if now - last >= hours*3600:
            self._check_updates(manual=False)

    def _check_updates(self, manual=True):
        try:
            resp = requests.get(
                "https://api.github.com/repos/Azrea-Shade/Azreas-Daily-Companion-Tracker/releases/latest",
                timeout=10
            )
            if resp.status_code == 200:
                tag = (resp.json().get("tag_name") or "").lstrip("v")
                if tag and _v.parse(tag) > _v.parse(CURRENT_VERSION):
                    ans = self._ask("Update available", f"A new version v{tag} is available.\nOpen the Releases page?")
                    if ans == QMessageBox.Yes:
                        webbrowser.open(RELEASES_URL)
                elif manual:
                    self._info("Updates", "You're on the latest version.")
            else:
                if manual:
                    self._warn("Updates", f"Update check failed: HTTP {resp.status_code}")
        except Exception as e:
            if manual:
                self._warn("Updates", f"Update check failed: {e}")
        finally:
            self.data["last_update_check"] = int(time.time()); save_data(self.data)

# --------- Settings Dialog (at bottom to keep file compact) ---------

# ---------- Notes ----------
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

    btns = QHBoxLayout()
    exp = QPushButton("Export Notes CSV"); exp.clicked.connect(self._export_notes_csv)
    btns.addWidget(exp)

    v.addLayout(row)
    v.addWidget(self.note_text_input)
    v.addWidget(self.notes_tbl)
    v.addLayout(btns)
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
    try:
        self.note_text_input.clear()
    except Exception:
        pass
    try:
        LOGGER.info(f"Note saved for {sym}")
    except Exception:
        pass
    self._info("Notes", "Saved.")

def _refresh_notes(self):
    notes = self.data.get("notes", [])
    self.notes_tbl.setRowCount(0)
    # Show latest first
    for n in reversed(notes[-200:]):
        row = self.notes_tbl.rowCount(); self.notes_tbl.insertRow(row)
        self.notes_tbl.setItem(row, 0, QTableWidgetItem(n.get("ts","—")))
        self.notes_tbl.setItem(row, 1, QTableWidgetItem(n.get("symbol","—")))
        # Show a compact preview; full text is in data.json
        preview = n.get("text","").replace("\n"," ")
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
        try: LOGGER.info(f"Notes CSV exported: {path}")
        except Exception: pass
    except Exception as e:
        self._warn("Export", f"Failed to export notes:\n{e}")

class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setStyleSheet(f"background:{CARD};")
        self.cfg = cfg.copy()

        form = QFormLayout(self)

        self.chk_quote = QCheckBox("Show 8:00 AM quote")
        self.chk_startup = QCheckBox("Start with Windows (current user)")
        self.chk_startup.setChecked(is_startup_enabled())
        self.chk_minimize = QCheckBox("Minimize to tray on close")
        self.chk_minimize.setChecked(bool(self.cfg.get("minimize_to_tray", False)))
        self.chk_launchmin = QCheckBox("Launch minimized to tray")
        self.chk_launchmin.setChecked(bool(self.cfg.get("launch_minimized", False)))
        self.chk_quote.setChecked(bool(self.cfg.get("auto_quote_8am", True)))
        form.addRow(self.chk_quote)
        form.addRow(self.chk_startup)
        form.addRow(self.chk_minimize)
        form.addRow(self.chk_launchmin)

        self.spin_pct = QSpinBox(); self.spin_pct.setRange(1, 50)
        self.spin_pct.setValue(int(self.cfg.get("price_alert_pct", 3)))
        form.addRow("Price alert threshold (%)", self.spin_pct)

        self.spin_news = QSpinBox(); self.spin_news.setRange(5, 120)
        self.spin_news.setValue(int(self.cfg.get("news_poll_minutes", 15)))
        form.addRow("News check interval (minutes)", self.spin_news)

        self.spin_update = QSpinBox(); self.spin_update.setRange(1, 168)
        self.spin_update.setValue(int(self.cfg.get("update_check_hours", 24)))
        form.addRow("Update check interval (hours)", self.spin_update)

        self.txt_legal = QPlainTextEdit()
        self.txt_legal.setPlainText(self.cfg.get("legal_keywords", ", ".join(DEFAULT_LEGAL_WORDS)))
        self.txt_legal.setFixedHeight(80)
        form.addRow("Legal keywords (comma-separated)", self.txt_legal)

        self.inp_openai = QLineEdit(); self.inp_openai.setEchoMode(QLineEdit.Password)
        self.inp_openai.setPlaceholderText("(optional) store OPENAI_API_KEY")
        self.inp_openai.setText(self.cfg.get("openai_api_key",""))
        form.addRow("OpenAI API key", self.inp_openai)

        self.inp_news = QLineEdit(); self.inp_news.setEchoMode(QLineEdit.Password)
        self.inp_news.setPlaceholderText("(optional) store NEWSAPI_KEY")
        self.inp_news.setText(self.cfg.get("newsapi_key",""))
        form.addRow("NewsAPI key", self.inp_news)

        row = QHBoxLayout()
        save = QPushButton("Save"); cancel = QPushButton("Cancel")
        row.addWidget(save); row.addWidget(cancel)
        form.addRow(row)

        save.clicked.connect(self._do_save)
        cancel.clicked.connect(self.reject)

    def _do_save(self):
        self.cfg["auto_quote_8am"] = self.chk_quote.isChecked()
        self.cfg["price_alert_pct"] = int(self.spin_pct.value())
        self.cfg["news_poll_minutes"] = int(self.spin_news.value())
        self.cfg["update_check_hours"] = int(self.spin_update.value())
        self.cfg["legal_keywords"] = self.txt_legal.toPlainText().strip()
        self.cfg["openai_api_key"] = self.inp_openai.text().strip()
        self.cfg["newsapi_key"] = self.inp_news.text().strip()
        self.cfg["minimize_to_tray"] = self.chk_minimize.isChecked()
        self.cfg["launch_minimized"] = self.chk_launchmin.isChecked()
        # Attempt to set startup only on Windows; ignore failure silently
        try:
            enable_startup(self.chk_startup.isChecked())
        except Exception:
            pass
        save_config(self.cfg)
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLES)
    w = MainWindow(); w.show()
    sys.exit(app.exec_())

# -------------- Bind Google Drive helpers back onto MainWindow --------------
def _mw_find_client_secrets(self):
    candidates = [
        APP_DIR / "client_secrets.json",
        ROOT_DIR / "client_secrets.json",
        DOCS_DIR / "client_secrets.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def _mw_ensure_drive(self):
    # Optional dependency – safe no-op if missing
    if GoogleAuth is None or GoogleDrive is None:
        # Only warn in interactive mode; tests won't call this anyway
        self._warn("Drive", "pydrive2 not installed. (It will be bundled in the installer.)")
        return None
    secrets = _mw_find_client_secrets(self)
    if not secrets:
        self._warn("Drive",
            "client_secrets.json not found.\n\n"
            "Put it next to the EXE or in Documents/DailyCompanion.")
        return None
    settings = {
        "client_config_file": str(secrets),
        "save_credentials": True,
        "save_credentials_backend": "file",
        "save_credentials_file": str(APP_DIR / "token.json"),
        "get_refresh_token": True,
        "oauth_scope": ["https://www.googleapis.com/auth/drive.file"],
    }
    gauth = GoogleAuth(settings=settings)
    try:
        gauth.LoadCredentialsFile(settings["save_credentials_file"])
    except Exception:
        pass
    if not getattr(gauth, "credentials", None) or getattr(gauth.credentials, "access_token_expired", True):
        try:
            gauth.LocalWebserverAuth()
        except Exception:
            gauth.CommandLineAuth()
        gauth.SaveCredentialsFile(settings["save_credentials_file"])
    return GoogleDrive(gauth)

def _mw_upload_last_pdf(self):
    files = sorted(EXPORT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        self._info("Drive", "No exported PDFs found in the 'exports' folder.")
        return
    drive = _mw_ensure_drive(self)
    if not drive:
        return
    fpath = files[0]
    try:
        f = drive.CreateFile({'title': fpath.name})
        f.SetContentFile(str(fpath))
        f.Upload()
        self._info("Drive", f"Uploaded to Google Drive: {fpath.name}")
    except Exception as e:
        self._warn("Drive", f"Upload failed:\n{e}")

# Attach as methods so existing UI connects succeed during init
try:
    MainWindow._find_client_secrets = _mw_find_client_secrets
    MainWindow._ensure_drive = _mw_ensure_drive
    MainWindow._upload_last_pdf = _mw_upload_last_pdf
except Exception as _e:
    # If MainWindow isn't defined (import path oddities), it's fine; tests import normally.
    pass

# ---- CI safety: ensure _upload_last_pdf exists even if Drive helpers not bound yet ----
try:
    if not hasattr(MainWindow, "_upload_last_pdf"):
        def __dc_stub_upload(self):
            # Minimal no-op for tests; real upload provided by Drive helpers when configured
            self._info("Drive", "Upload not configured (no Google Drive setup).")
        MainWindow._upload_last_pdf = __dc_stub_upload
except Exception:
    pass


# --- CI-safe: ensure _upload_last_pdf exists even without Drive setup ---
try:
    if not hasattr(MainWindow, "_upload_last_pdf"):
        def __dc_stub_upload(self):
            self._info("Drive", "Upload not configured (no Google Drive setup).")
        MainWindow._upload_last_pdf = __dc_stub_upload
except Exception:
    pass


    def closeEvent(self, event):
        try:
            if self.config.get("minimize_to_tray", False) and self.tray is not None and not self._headless():
                event.ignore()
                self.hide()
                try:
                    self.tray.showMessage("Running in background", "App is minimized to tray. Right-click tray icon to Quit.", QSystemTrayIcon.Information, 6000)
                except Exception:
                    pass
                LOGGER.info("Window hidden to tray")
                return
        except Exception:
            pass
        LOGGER.info("Window closed")
        super().closeEvent(event)
