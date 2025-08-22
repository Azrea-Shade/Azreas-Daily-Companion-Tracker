import os, sys, json, random, datetime, time, webbrowser
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTabWidget, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QSystemTrayIcon, QMenu,
    QTextEdit
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

# pydrive2 is optional at runtime; we gate it inside methods
DriveAuthErr = None
try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
except Exception as _e:
    DriveAuthErr = _e
    GoogleAuth = GoogleDrive = None

# ---------------- App Paths & Data ----------------
APP_DIR    = Path(__file__).resolve().parent
ROOT_DIR   = APP_DIR.parent
DATA_FILE  = APP_DIR / "data.json"
EXPORT_DIR = ROOT_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
DOCS_DIR   = Path.home() / "Documents" / "DailyCompanion"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_VERSION = "1.0.0"
RELEASES_URL    = "https://github.com/Azrea-Shade/Azreas-Daily-Companion-Tracker/releases"

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
    return {"watchlist": [], "last_prices": {}, "last_news_check": 0, "last_update_check": 0}

def save_data(data):
    try:
        DATA_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print("Save error:", e)

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
QLineEdit {{ background:#0d1424; border:1px solid {BORDER}; border-radius:8px; padding:8px; }}
QPushButton {{ background:#111a2a; border:1px solid {BORDER}; border-radius:10px; padding:10px 16px; }}
QPushButton:hover {{ border-color:{ACCENT}; }}
QPushButton:pressed {{ background:#0c1322; }}
QTabBar::tab {{ background:#0d1424; padding:10px 16px; margin:2px; border:1px solid {BORDER};
  border-top-left-radius:10px; border-top-right-radius:10px; }}
QTabBar::tab:selected {{ color:{ACCENT}; border-bottom:2px solid {ACCENT}; }}
QTableWidget {{ background:#0d1424; gridline-color:{BORDER}; border:1px solid {BORDER}; border-radius:10px; }}
QTextEdit {{ background:#0d1424; border:1px solid {BORDER}; border-radius:10px; padding:10px; }}
"""

LEGAL_WORDS = ["lawsuit", "sues", "sued", "settlement", "bankruptcy", "chapter 11",
               "restructuring", "investigation", "sec", "fraud", "indictment", "probe"]

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
        layout.addWidget(title); layout.addWidget(quote_lbl); layout.addWidget(ok, alignment=Qt.AlignCenter)
        self.resize(520, 240)

# ---------------- Main Window ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌌 Azrea’s Daily Companion Tracker")
        self.setMinimumSize(1000, 680)
        self.setWindowIcon(QIcon())

        self.data = load_data()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = self._build_dashboard()
        self.search    = self._build_search()
        self.watchlist = self._build_watchlist()
        self.ai        = self._build_ai_tab()

        self.tabs.addTab(self.dashboard, "📊 Dashboard")
        self.tabs.addTab(self.search,    "🔍 Search")
        self.tabs.addTab(self.watchlist, "⭐ Watchlist")
        self.tabs.addTab(self.ai,        "🤖 AI Assistant")

        self._init_tray()
        self._show_boot_quote()
        self._schedule_next_8am_quote()

        # Background watchers
        self._start_price_watcher()   # every 5 min
        self._start_news_watcher()    # every 10–15 min
        self._maybe_check_updates_silent()  # once a day

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
        ql.addWidget(self.quote_label); ql.addWidget(newq, alignment=Qt.AlignLeft)

        self.next_label = QLabel("")
        self._update_next_8am_label()

        h.addWidget(title); h.addWidget(subtitle); h.addWidget(qcard); h.addWidget(self.next_label)
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
        upload_pdf = QPushButton("Upload Last PDF to Drive"); upload_pdf.clicked.connect(self._upload_last_pdf)
        btnrow.addWidget(addfav); btnrow.addWidget(export_pdf); btnrow.addWidget(upload_pdf)

        root.addLayout(row); root.addWidget(self.result_box); root.addLayout(btnrow)
        return w

    def perform_search(self):
        symbol = self.search_input.text().strip().upper()
        if not symbol:
            QMessageBox.information(self, "Search", "Please enter a ticker symbol (e.g., AAPL)."); return
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
        if not item: QMessageBox.information(self, "Watchlist", "Search a ticker first."); return
        wl = self.data.get("watchlist", []); sym = item.get("symbol")
        if sym and sym not in wl:
            wl.append(sym); self.data["watchlist"] = wl; save_data(self.data); self._refresh_watchlist_table()
            QMessageBox.information(self, "Watchlist", f"Added {sym} to watchlist.")
        else:
            QMessageBox.information(self, "Watchlist", f"{sym} is already in watchlist.")

    def _export_pdf(self):
        if canvas is None:
            QMessageBox.warning(self, "PDF", "ReportLab not installed. Add to requirements.txt."); return
        item = getattr(self, "_last_search", None)
        if not item: QMessageBox.information(self, "PDF", "Search a ticker first."); return
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
        QMessageBox.information(self, "PDF", f"Saved: {fname}")

    # ---------- Google Drive Upload ----------
    def _find_client_secrets(self):
        candidates = [
            APP_DIR / "client_secrets.json",
            ROOT_DIR / "client_secrets.json",
            DOCS_DIR / "client_secrets.json",
        ]
        for p in candidates:
            if p.exists(): return p
        return None

    def _ensure_drive(self):
        if GoogleAuth is None or GoogleDrive is None:
            QMessageBox.warning(self, "Drive", "pydrive2 not installed. (It will be bundled in the installer.)")
            return None
        secrets = self._find_client_secrets()
        if not secrets:
            QMessageBox.warning(self, "Drive",
                                "client_secrets.json not found.\n\n"
                                "Put it next to DailyCompanion.exe OR in Documents/DailyCompanion.\n"
                                "See docs/GOOGLE_DRIVE_SETUP.md in the repository.")
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
                # Try local webserver auth first (user-friendly)
                gauth.LocalWebserverAuth()
            except Exception:
                # Fallback to command-line copy/paste
                gauth.CommandLineAuth()
            gauth.SaveCredentialsFile(settings["save_credentials_file"])
        return GoogleDrive(gauth)

    def _upload_last_pdf(self):
        # Find the most recent PDF in exports/
        files = sorted(EXPORT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            QMessageBox.information(self, "Drive", "No exported PDFs found in the 'exports' folder."); return
        drive = self._ensure_drive()
        if not drive: return
        fpath = files[0]
        try:
            f = drive.CreateFile({'title': fpath.name})
            f.SetContentFile(str(fpath))
            f.Upload()
            QMessageBox.information(self, "Drive", f"Uploaded to Google Drive: {fpath.name}")
        except Exception as e:
            QMessageBox.warning(self, "Drive", f"Upload failed:\n{e}")

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
        btnrow.addWidget(refresh); btnrow.addWidget(remove)
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
            QMessageBox.information(self, "Remove", "Select a row to remove."); return
        wl = self.data.get("watchlist", [])
        for r in rows:
            sym = self.table.item(r, 0).text()
            if sym in wl: wl.remove(sym)
            self.table.removeRow(r)
        self.data["watchlist"] = wl; save_data(self.data)

    # ---------- AI Chat ----------
    def _build_ai_tab(self):
        w = QWidget(); root = QVBoxLayout(w); root.setContentsMargins(16,16,16,16)
        wrap = QGroupBox("Ask the AI"); v = QVBoxLayout(wrap)
        self.chat_log = QTextEdit(); self.chat_log.setReadOnly(True)
        self.chat_input = QLineEdit(); self.chat_input.setPlaceholderText("Ask about a company, market, or strategy…")
        send = QPushButton("Send"); send.clicked.connect(self._send_chat)
        v.addWidget(self.chat_log)
        row = QHBoxLayout(); row.addWidget(self.chat_input); row.addWidget(send); v.addLayout(row)
        hint = QLabel("Tip: Set environment variables OPENAI_API_KEY and NEWSAPI_KEY for full features.")
        hint.setStyleSheet("color:#93a1be; font-size:12px;")
        root.addWidget(wrap); root.addWidget(hint)
        return w

    def _send_chat(self):
        prompt = self.chat_input.text().strip()
        if not prompt: return
        self.chat_log.append(f"🧑‍💼 You: {prompt}")
        self.chat_input.clear()
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            self.chat_log.append("🤖 AI: (No OPENAI_API_KEY set. Add it to use the assistant.)"); return
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

    # ---------- Tray & Quotes ----------
    def _init_tray(self):
        self.tray = QSystemTrayIcon(self); self.tray.setIcon(QIcon())
        menu = QMenu()
        act_show  = menu.addAction("Show"); act_show.triggered.connect(self.showNormal)
        act_quote = menu.addAction("Show Quote"); act_quote.triggered.connect(lambda: self._show_quote(random.choice(QUOTES)))
        act_update= menu.addAction("Check for Updates…"); act_update.triggered.connect(lambda: self._check_updates(manual=True))
        menu.addSeparator()
        act_quit  = menu.addAction("Quit"); act_quit.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu); self.tray.show()

    def _show_boot_quote(self):
        self._show_quote(random.choice(QUOTES))

    def _show_quote(self, q: str):
        pop = QuotePopup(q); pop.show()
        if not hasattr(self, "_popups"): self._popups = []
        self._popups.append(pop)

    def _schedule_next_8am_quote(self):
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target: target = target + datetime.timedelta(days=1)
        msec = int((target - now).total_seconds() * 1000)
        self.timer8 = QTimer(self); self.timer8.setSingleShot(True)
        self.timer8.timeout.connect(lambda: (self._show_quote(random.choice(QUOTES)),
                                             self._schedule_next_8am_quote(),
                                             self._update_next_8am_label()))
        self.timer8.start(max(msec, 1000)); self._update_next_8am_label()

    def _update_next_8am_label(self):
        now = datetime.datetime.now()
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target: target = target + datetime.timedelta(days=1)
        diff = target - now; hrs = diff.seconds // 3600; mins = (diff.seconds % 3600) // 60
        try: self.next_label.setText(f"⏰ Next 8:00 AM quote in ~ {hrs}h {mins}m")
        except Exception: pass

    # ---------- Background watchers ----------
    def _start_price_watcher(self):
        self._price_timer = QTimer(self); self._price_timer.timeout.connect(self._check_prices)
        self._price_timer.start(5 * 60 * 1000)  # every 5 minutes

    def _check_prices(self):
        wl = self.data.get("watchlist", [])
        if not wl or Ticker is None: return
        try:
            t = Ticker(wl); p = t.price if hasattr(t, "price") else {}
            changed = []
            for sym in wl:
                d = p.get(sym) if p else None; nowp = None
                if d and isinstance(d, dict): nowp = d.get("regularMarketPrice") or d.get("postMarketPrice")
                if nowp is None: continue
                try:
                    nowp = float(nowp)
                    prev = float(self.data.get("last_prices", {}).get(sym, nowp))
                    if prev > 0:
                        delta = (nowp - prev) / prev * 100.0
                        if abs(delta) >= 3.0: changed.append((sym, nowp, delta))
                    self.data.setdefault("last_prices", {})[sym] = nowp
                except Exception: pass
            if changed:
                msg = "; ".join([f"{s}: {p:.2f} ({d:+.1f}%)" for s,p,d in changed])
                self.tray.showMessage("Watchlist movement", msg, QSystemTrayIcon.Information, 10000)
                save_data(self.data)
        except Exception as e:
            print("Price watcher error:", e)

    def _start_news_watcher(self):
        self._news_timer = QTimer(self); self._news_timer.timeout.connect(self._check_news)
        self._news_timer.start(15 * 60 * 1000) # every ~15 minutes

    def _check_news(self):
        key = os.getenv("NEWSAPI_KEY")
        if not key: return
        wl = self.data.get("watchlist", [])
        if not wl: return
        now = int(time.time()); last = int(self.data.get("last_news_check", 0))
        if now - last < 10*60: return  # throttle
        try:
            q = " OR ".join(wl[:5])  # concise query
            url = "https://newsapi.org/v2/everything"
            params = {"q": q, "language": "en", "pageSize": 10, "sortBy": "publishedAt", "apiKey": key}
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                alerts = []
                for a in articles:
                    title = (a.get("title") or "").lower()
                    if any(word in title for word in LEGAL_WORDS):
                        alerts.append(a.get("title") or "Legal/Regulatory headline")
                if alerts:
                    msg = " • ".join(alerts[:3])
                    self.tray.showMessage("Legal/News alert", msg, QSystemTrayIcon.Warning, 12000)
                self.data["last_news_check"] = now; save_data(self.data)
        except Exception as e:
            print("News watcher error:", e)

    # ---------- Updates ----------
    def _maybe_check_updates_silent(self):
        # Check once per 24h
        now = int(time.time()); last = int(self.data.get("last_update_check", 0))
        if now - last >= 24*3600:
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
                    ans = QMessageBox.question(
                        self, "Update available",
                        f"A new version v{tag} is available.\nOpen the Releases page?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    if ans == QMessageBox.Yes:
                        webbrowser.open(RELEASES_URL)
                elif manual:
                    QMessageBox.information(self, "Updates", "You're on the latest version.")
            else:
                if manual:
                    QMessageBox.warning(self, "Updates", f"Update check failed: HTTP {resp.status_code}")
        except Exception as e:
            if manual:
                QMessageBox.warning(self, "Updates", f"Update check failed: {e}")
        finally:
            self.data["last_update_check"] = int(time.time()); save_data(self.data)

# --------- utils ---------
def wrap_text(text: str, width: int):
    out = []; line = ""
    for word in (text or "").split():
        if len(line) + len(word) + 1 > width:
            out.append(line); line = word
        else:
            line = word if not line else line + " " + word
    if line: out.append(line)
    return out

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLES)
    w = MainWindow(); w.show()
    sys.exit(app.exec_())
