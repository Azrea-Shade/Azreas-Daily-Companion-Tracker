# Dynamically extend app.main.MainWindow safely after class definition.
# Adds: Alerts tab, Settings tab (Elder Mode + Price Alerts), Windows toasts,
# Google Drive upload, crash logs, dossier PDF, background watchers.
import os, json, logging, zipfile, io
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

from . import alerts as _alerts

def _ensure_logger(app_dir: Path):
    log_dir = app_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logfile = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler()]
    )
    return logfile

def install_into(ns: Dict[str, Any]):
    MainWindow = ns.get("MainWindow")
    if not MainWindow:
        return
    APP_DIR   = ns.get("APP_DIR", Path("."))
    DATA_FILE = ns.get("DATA_FILE")
    EXPORT_DIR= ns.get("EXPORT_DIR")

    _ensure_logger(APP_DIR)

    # --- helpers injected into class ---
    def _notify(self, title: str, msg: str):
        try:
            from win10toast import ToastNotifier
            if not hasattr(self, "_toaster"):
                self._toaster = ToastNotifier()
            self._toaster.show_toast(title, msg, threaded=True, icon_path=str((APP_DIR/"assets"/"app_icon.ico")) if (APP_DIR/"assets"/"app_icon.ico").exists() else None, duration=5)
        except Exception:
            try:
                # Fallback to tray message if available
                from PyQt5.QtWidgets import QSystemTrayIcon
                if not hasattr(self, "_tray"):
                    self._tray = QSystemTrayIcon(self.windowIcon(), self)
                    self._tray.show()
                self._tray.showMessage(title, msg)
            except Exception:
                logging.info("NOTIFY: %s - %s", title, msg)

    def _get_data(self):
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"watchlist": [], "reminders": [], "alerts": [], "notes": []}

    def _save_data(self, d):
        DATA_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

    # --- Price alerts (feature 5) ---
    def _check_price_alerts(self):
        d = self.data
        rules = d.get("alerts", [])
        if not rules:
            return
        try:
            from yahooquery import Ticker
        except Exception:
            return
        # group by symbol
        syms = sorted({r.get("symbol","").upper() for r in rules if r.get("symbol")})
        if not syms:
            return
        t = Ticker(" ".join(syms))
        for sym in syms:
            try:
                px = None
                try:
                    px = t.price[sym].get("regularMarketPrice")
                except Exception:
                    px = None
                if px is None:
                    continue
                for r in [r for r in rules if (r.get("symbol","").upper()==sym)]:
                    op = r.get("op", ">="); val = float(r.get("value", 0))
                    hit = (px >= val) if op == ">=" else (px <= val)
                    if hit and not r.get("_muted"):
                        self._notify(f"Price alert: {sym}", f"{sym} {op} {val} (now {px})")
            except Exception:
                continue

    # --- Alerts feed (feature 1) ---
    def _maybe_refresh_alert_feed(self):
        if not hasattr(self, "alerts_list"):
            return
        api_key = os.environ.get("NEWSAPI_KEY", "")
        items = []
        try:
            wl = self.data.get("watchlist", [])
            q = wl[0] if wl else "investment banking"
            news = _alerts.fetch_company_news(api_key, q, page_size=5)
            for a in news:
                items.append(f"📰 {a.get('title','(no title)')[:120]}")
        except Exception:
            pass
        # SEC filings for first watchlist ticker if we can resolve CIK via services
        try:
            from . import services as s
            if self.data.get("watchlist"):
                cik = s.get_cik_for_ticker(self.data["watchlist"][0])
                filings = s.get_recent_filings_by_cik(cik, limit=3)
                for f in filings:
                    items.append(f"📄 {f.get('form','?')} — {f.get('date','')} {f.get('desc','')[:80]}")
        except Exception:
            pass
        # Update UI
        try:
            self.alerts_list.clear()
            if not items:
                self.alerts_list.addItem("No alerts available (set NEWSAPI_KEY to enable news).")
            else:
                for it in items:
                    self.alerts_list.addItem(it)
        except Exception:
            pass

    # --- Google Drive (feature 2) ---
    def _connect_google_drive(self):
        try:
            from pydrive2.auth import GoogleAuth
            from pydrive2.drive import GoogleDrive
            gauth = GoogleAuth(settings_file=str(APP_DIR/"client_secrets.yaml")) if (APP_DIR/"client_secrets.yaml").exists() else GoogleAuth()
            gauth.LoadCredentialsFile(str(APP_DIR/"token.json"))
            if gauth.credentials is None:
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()
            gauth.SaveCredentialsFile(str(APP_DIR/"token.json"))
            self._drive = GoogleDrive(gauth)
            self._notify("Google Drive", "Connected successfully.")
        except Exception as e:
            logging.exception("Drive connect failed: %s", e)
            self._notify("Google Drive", "Connection failed. See logs.")

    def _upload_last_pdf(self):
        # fallback: last exported or newest in EXPORT_DIR
        path = getattr(self, "last_pdf_path", None)
        if not path:
            try:
                latest = sorted(Path(EXPORT_DIR).glob("*.pdf"))[-1]
                path = str(latest)
            except Exception:
                pass
        if not path:
            self._notify("Upload", "No PDF found to upload.")
            return
        try:
            if not hasattr(self, "_drive"):
                self._connect_google_drive()
            if hasattr(self, "_drive"):
                f = self._drive.CreateFile({"title": Path(path).name})
                f.SetContentFile(path)
                f.Upload()
                self._notify("Upload", "PDF uploaded to Drive.")
        except Exception as e:
            logging.exception("Upload failed: %s", e)
            self._notify("Upload", "Upload failed. See logs.")

    # --- Dossier builder (feature 7) ---
    def _export_dossier_pdf(self, symbol: str = None):
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from . import services as s
        except Exception:
            self._notify("Dossier", "ReportLab not available.")
            return
        symbol = (symbol or getattr(self, "_current_symbol", "") or "").upper() or "AAPL"
        data = {}
        try:
            data = s.get_company_intel(symbol)
        except Exception:
            data = {}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = Path(EXPORT_DIR) / f"dossier_{symbol}_{ts}.pdf"
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER)
        story = []
        story.append(Paragraph(f"Company Dossier: {symbol}", styles["Heading1"]))
        story.append(Spacer(1, 12))
        if "wiki" in data:
            story.append(Paragraph(f"{data['wiki'].get('title','')}", styles["Heading2"]))
            story.append(Paragraph(data['wiki'].get('extract',''), styles["BodyText"]))
        if "price" in data:
            story.append(Paragraph(f"Price: {data['price']}", styles["BodyText"]))
        if "filings" in data:
            story.append(Paragraph("Recent Filings:", styles["Heading3"]))
            for f in data["filings"][:5]:
                story.append(Paragraph(f"{f.get('form','')} — {f.get('date','')} {f.get('desc','')}", styles["BodyText"]))
        doc.build(story)
        self.last_pdf_path = str(pdf_path)
        self._notify("Dossier", f"Saved {pdf_path.name}")

    # --- Crash/diagnostics (feature 6) ---
    def _export_diagnostics_zip(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            try:
                z.writestr("build_info.txt", f"Built: {datetime.now().isoformat()}\n")
            except Exception: pass
            try:
                log_path = Path(self.__class__.__module__.replace(".", "/")).resolve().parent / "logs" / "app.log"
            except Exception:
                log_path = Path(".") / "app" / "logs" / "app.log"
            try:
                if log_path.exists():
                    z.write(str(log_path), arcname="app.log")
            except Exception: pass
        out_path = Path(self.__class__.__module__.replace(".", "/")).resolve().parent / "exports" / f"diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(out.getvalue())
        self._notify("Diagnostics", f"Saved {out_path.name}")

    # --- Elder Mode + Settings tab (feature 4) & Alerts tab (feature 1) ---
    def _post_init_plugins(self):
        try:
            from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QHBoxLayout, QCheckBox, QTableWidget, QTableWidgetItem, QGroupBox
        except Exception:
            return

        # Alerts tab
        alerts_w = QWidget(); av = QVBoxLayout(alerts_w)
        self.alerts_list = QListWidget()
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Refresh Alerts")
        btn_refresh.clicked.connect(self._maybe_refresh_alert_feed)
        btn_dossier = QPushButton("Export Dossier PDF")
        btn_dossier.clicked.connect(lambda: self._export_dossier_pdf(getattr(self, "_current_symbol", "AAPL")))
        btn_connect = QPushButton("Connect Google Drive")
        btn_connect.clicked.connect(self._connect_google_drive)
        btn_upload = QPushButton("Upload Last PDF")
        btn_upload.clicked.connect(self._upload_last_pdf)
        btn_row.addWidget(btn_refresh); btn_row.addWidget(btn_dossier); btn_row.addWidget(btn_connect); btn_row.addWidget(btn_upload)
        av.addWidget(self.alerts_list); av.addLayout(btn_row)
        self.tabs.addTab(alerts_w, "Alerts")

        # Settings (Elder mode + Price alerts table)
        settings = QWidget(); sv = QVBoxLayout(settings)
        elder_box = QGroupBox("Accessibility"); ev = QVBoxLayout(elder_box)
        chk_elder = QCheckBox("Elder Mode (bigger fonts & higher contrast)")
        def _toggle_elder(on):
            try:
                if on:
                    self.setStyleSheet("QWidget{font-size:15px;} QPushButton{padding:8px 12px;}")
                else:
                    self.setStyleSheet("")
            except Exception: pass
        chk_elder.stateChanged.connect(lambda s: _toggle_elder(bool(s)))
        ev.addWidget(chk_elder)
        sv.addWidget(elder_box)

        alerts_box = QGroupBox("Price Alerts"); pv = QVBoxLayout(alerts_box)
        self.alerts_tbl = QTableWidget(0,3)
        self.alerts_tbl.setHorizontalHeaderLabels(["Symbol","Op (>= or <=)","Value"])
        pv.addWidget(self.alerts_tbl)
        btn_add_rule = QPushButton("Add AAPL >= 200")
        def _add_rule():
            d = self.data
            rules = d.setdefault("alerts", [])
            rules.append({"symbol":"AAPL","op":">=","value":200})
            self._save_data(d)
            i = self.alerts_tbl.rowCount()
            self.alerts_tbl.insertRow(i)
            self.alerts_tbl.setItem(i,0,QTableWidgetItem("AAPL"))
            self.alerts_tbl.setItem(i,1,QTableWidgetItem(">="))
            self.alerts_tbl.setItem(i,2,QTableWidgetItem("200"))
        btn_add_rule.clicked.connect(_add_rule)
        pv.addWidget(btn_add_rule)
        sv.addWidget(alerts_box)

        btn_diag = QPushButton("Export Diagnostics Zip")
        btn_diag.clicked.connect(self._export_diagnostics_zip)
        sv.addWidget(btn_diag)

        self.tabs.addTab(settings, "Settings")

        # start background watchers (no-op in CI/headless)
        try:
            self._watcher = _alerts.Watcher(self, poll_seconds=300)
            self._watcher.start()
        except Exception:
            pass

        # Initial feed
        try:
            self._maybe_refresh_alert_feed()
        except Exception:
            pass

    # Bind methods to class
    for name, fn in {
        "_notify": _notify,
        "_check_price_alerts": _check_price_alerts,
        "_maybe_refresh_alert_feed": _maybe_refresh_alert_feed,
        "_connect_google_drive": _connect_google_drive,
        "_upload_last_pdf": _upload_last_pdf,
        "_export_dossier_pdf": _export_dossier_pdf,
        "_export_diagnostics_zip": _export_diagnostics_zip,
        "_post_init_plugins": _post_init_plugins,
    }.items():
        setattr(MainWindow, name, fn)

    # Wrap __init__ to call post-init
    old_init = MainWindow.__init__
    def __init__(self, *a, **k):
        old_init(self, *a, **k)
        try:
            self._post_init_plugins()
        except Exception:
            pass
    MainWindow.__init__ = __init__
