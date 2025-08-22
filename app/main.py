import sys, os, json, random, datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTabWidget, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QSystemTrayIcon, QMenu
)

try:
    from yahooquery import Ticker
except Exception:
    Ticker = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:
    canvas = None

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "data.json"
EXPORT_DIR = APP_DIR.parent / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

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
    return {"watchlist": []}

def save_data(data):
    try:
        DATA_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print("Save error:", e)

# ---------------- UI theme ----------------
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
QLineEdit {{ background:#0d1424; border:1px solid {BORDER}; border-radius:8px; padding:8px; }}
QPushButton {{ background:#111a2a; border:1px solid {BORDER}; border-radius:10px; padding:10px 16px; }}
QPushButton:hover {{ border-color:{ACCENT}; }}
QPushButton:pressed {{ background:#0c1322; }}
QTabBar::tab {{ background:#0d1424; padding:10px 16px; margin:2px; border:1px solid {BORDER};
  border-top-left-radius:10px; border-top-right-radius:10px; }}
QTabBar::tab:selected {{ color:{ACCENT}; border-bottom:2px solid {ACCENT}; }}
QTableWidget {{ background:#0d1424; gridline-color:{BORDER}; border:1px solid {BORDER}; border-radius:10px; }}
"""

# ---------------- Quote Popup ----------------
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
        layout.addWidget(title)
        layout.addWidget(quote_lbl)
        layout.addWidget(ok, alignment=Qt.AlignCenter)
        self.resize(520, 240)

# ---------------- Main Window ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌌 Azrea’s Daily Companion Tracker")
        self.setMinimumSize(980, 640)
        self.setWindowIcon(QIcon())
        self.data = load_data()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = self._build_dashboard()
        self.search    = self._build_search()
        self.watchlist = self._build_watchlist()
        self.ai        = self._build_ai_placeholder()

        self.tabs.addTab(self.dashboard, "📊 Dashboard")
        self.tabs.addTab(self.search,    "🔍 Search")
        self.tabs.addTab(self.watchlist, "⭐ Watchlist")
        self.tabs.addTab(self.ai,        "🤖 AI Assistant")

        self._init_tray()
        self._show_boot_quote()
        self._schedule_next_8am_quote()

    # ---------- Dashboard ----------
    def _build_dashboard(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)

        hero = QGroupBox("Welcome")
        h = QVBoxLayout(hero)
        title = QLabel("🌌 Azrea’s Daily Companion Tracker")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size:28px; color:{ACCENT}; font-weight:700;")
        subtitle = QLabel("Futuristic companion for research, quotes, and daily flow.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size:14px; color:#bfc7d6;")

        qcard = QGroupBox("Daily Quote")
        ql = QVBoxLayout(qcard)
        self.quote_label = QLabel(random.choice(QUOTES))
        self.quote_label.setWordWrap(True)
        self.quote_label.setStyleSheet("font-size:18px;")
        newq = QPushButton("New Quote ✨")
        newq.clicked.connect(lambda: self.quote_label.setText(random.choice(QUOTES)))
        ql.addWidget(self.quote_label)
        ql.addWidget(newq, alignment=Qt.AlignLeft)

        self.next_label = QLabel("")
        self._update_next_8am_label()

        h.addWidget(title)
        h.addWidget(subtitle)
        h.addWidget(qcard)
        h.addWidget(self.next_label)
        root.addWidget(hero)
        return w

    # ---------- Search ----------
    def _build_search(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter ticker (e.g., AAPL, MSFT, TSLA)")
        btn = QPushButton("Search")
        btn.clicked.connect(self.perform_search)
        row.addWidget(self.search_input)
        row.addWidget(btn)

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
        addfav = QPushButton("Add to Watchlist ⭐")
        addfav.clicked.connect(self._add_current_to_watchlist)
        export_pdf = QPushButton("Export Summary (PDF)")
        export_pdf.clicked.connect(self._export_pdf)
        btnrow.addWidget(addfav)
        btnrow.addWidget(export_pdf)

        root.addLayout(row)
        root.addWidget(self.result_box)
        root.addLayout(btnrow)
        return w

    def perform_search(self):
        symbol = self.search_input.text().strip().upper()
        if not symbol:
            QMessageBox.information(self, "Search", "Please enter a ticker symbol (e.g., AAPL).")
            return
        name = symbol; price = "—"; desc = "No description available."
        if Ticker is not None:
            try:
                t = Ticker(symbol)
                # price
                p = t.price.get(symbol) if hasattr(t, "price") else None
                if p and isinstance(p, dict):
                    price_val = p.get("regularMarketPrice") or p.get("postMarketPrice")
                    if price_val is not None:
                        price = f"${price_val:.2f}"
                # name
                qt = t.quote_type.get(symbol) if hasattr(t, "quote_type") else None
                if qt and isinstance(qt, dict):
                    name = qt.get("longName") or qt.get("shortName") or name
                # description
                profile = None
                try:
                    profile = t.asset_profile.get(symbol) if hasattr(t, "asset_profile") else None
                except Exception:
                    profile = None
                if profile and isinstance(profile, dict):
                    d = profile.get("longBusinessSummary")
                    if d:
                        desc = d
            except Exception as e:
                print("Search error:", e)
        self.lbl_name.setText(name)
        self.lbl_price.setText(price)
        self.lbl_desc.setText(desc)
        self._last_search = {"symbol": symbol, "name": name, "price": price, "desc": desc}

    def _add_current_to_watchlist(self):
        item = getattr(self, "_last_search", None)
        if not item:
            QMessageBox.information(self, "Watchlist", "Search a ticker first.")
            return
        wl = self.data.get("watchlist", [])
        sym = item.get("symbol")
        if sym and sym not in wl:
            wl.append(sym)
            self.data["watchlist"] = wl
            save_data(self.data)
            self._refresh_watchlist_table()
            QMessageBox.information(self, "Watchlist", f"Added {sym} to watchlist.")
        else:
            QMessageBox.information(self, "Watchlist", f"{sym} is already in watchlist.")

    def _export_pdf(self):
        if canvas is None:
            QMessageBox.warning(self, "PDF", "ReportLab not installed. Add to requirements.txt.")
            return
        item = getattr(self, "_last_search", None)
        if not item:
            QMessageBox.information(self, "PDF", "Search a ticker first.")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = EXPORT_DIR / f"{item['symbol']}_summary_{ts}.pdf"
        c = canvas.Canvas(str(fname), pagesize=letter)
        width, height = letter
        y = height - 72
        c.setFont("Helvetica-Bold", 16)
        c.setFillColorRGB(0, 0.88, 1)
        c.drawString(72, y, f"Company: {item['name']} ({item['symbol']})")
        y -= 28
        c.setFont("Helvetica", 12)
        c.setFillColorRGB(1, 1, 1)
        c.drawString(72, y, f"Price: {item['price']}")
        y -= 24
        c.setFont("Helvetica", 11)
        text = c.beginText(72, y)
        text.setLeading(14)
        desc = item.get("desc") or "—"
        for line in wrap_text(desc, 90):
            text.textLine(line)
        c.drawText(text)
        c.showPage()
        c.save()
        QMessageBox.information(self, "PDF", f"Saved: {fname}")

    # ---------- Watchlist ----------
    def _build_watchlist(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("Favorites")
        v = QVBoxLayout(box)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Symbol", "Price"])
        self.table.horizontalHeader().setStretchLastSection(True)
        btnrow = QHBoxLayout()
        refresh = QPushButton("Refresh Prices")
        refresh.clicked.connect(self._refresh_watchlist_table)
        remove = QPushButton("Remove Selected")
        remove.clicked.connect(self._remove_selected)
        btnrow.addWidget(refresh)
        btnrow.addWidget(remove)
        v.addWidget(self.table)
        v.addLayout(btnrow)
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
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(sym))
                    val = "—"
                    try:
                        d = p.get(sym)
                        if d and isinstance(d, dict):
                            r = d.get("regularMarketPrice") or d.get("postMarketPrice")
                            if r is not None:
                                val = f"${r:.2f}"
                    except Exception:
                        pass
                    self.table.setItem(row, 1, QTableWidgetItem(val))
            except Exception as e:
                print("Watchlist fetch error:", e)
        else:
            for sym in wl:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(sym))
                self.table.setItem(row, 1, QTableWidgetItem("—"))

    def _remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "Remove", "Select a row to remove.")
            return
        wl = self.data.get("watchlist", [])
        for r in rows:
            sym = self.table.item(r, 0).text()
            if sym in wl:
                wl.remove(sym)
            self.table.removeRow(r)
        self.data["watchlist"] = wl
        save_data(self.data)

    # ---------- AI Placeholder ----------
    def _build_ai_placeholder(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        box = QGroupBox("AI Assistant")
        v = QVBoxLayout(box)
        lbl = QLabel("Coming soon: Talk to AI for research, summaries, and guidance.")
        lbl.setStyleSheet(f"color:{ACCENT}; font-size:16px;")
        v.addWidget(lbl)
        root.addWidget(box)
        return w

    # ---------- Tray & Quotes ----------
    def _init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon())
        menu = QMenu()
        act_show  = menu.addAction("Show")
        act_show.triggered.connect(self.showNormal)
        act_quote = menu.addAction("Show Quote")
        act_quote.triggered.connect(lambda: self._show_quote(random.choice(QUOTES)))
        menu.addSeparator()
        act_quit  = menu.addAction("Quit")
        act_quit.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _show_boot_quote(self):
        self._show_quote(random.choice(QUOTES))

    def _show_quote(self, q: str):
        pop = QuotePopup(q)
        pop.show()
        if not hasattr(self, "_popups"):
            self._popups = []
        self._popups.append(pop)

    def _schedule_next_8am_quote(self):
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + datetime.timedelta(days=1)
        msec = int((target - now).total_seconds() * 1000)
        self.timer8 = QTimer(self)
        self.timer8.setSingleShot(True)
        self.timer8.timeout.connect(lambda: (self._show_quote(random.choice(QUOTES)),
                                             self._schedule_next_8am_quote(),
                                             self._update_next_8am_label()))
        self.timer8.start(max(msec, 1000))
        self._update_next_8am_label()

    def _update_next_8am_label(self):
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + datetime.timedelta(days=1)
        diff = target - now
        hrs = diff.seconds // 3600
        mins = (diff.seconds % 3600) // 60
        try:
            self.next_label.setText(f"⏰ Next 8:00 AM quote in ~ {hrs}h {mins}m")
        except Exception:
            pass

# --------- utils ---------
def wrap_text(text: str, width: int):
    out = []
    line = ""
    for word in (text or "").split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = word if not line else line + " " + word
    if line:
        out.append(line)
    return out

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLES)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
