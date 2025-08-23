from __future__ import annotations
import os, sys, platform, logging
from pathlib import Path

LOG_DIR = Path.home() / "Documents" / "DailyCompanion" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "app.log"

def init_logger() -> logging.Logger:
    logger = logging.getLogger("dailycompanion")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=3, encoding="utf-8")
    except Exception:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

def is_windows() -> bool:
    return platform.system().lower().startswith("win")

def app_exec_path() -> str:
    # Path to the executable when frozen; fall back to interpreter otherwise.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys.executable
    return sys.executable  # PyInstaller bundles still use sys.executable

# ---- Startup (Windows Run key) ----
def _winreg():
    if not is_windows():
        return None
    try:
        import winreg
        return winreg
    except Exception:
        return None

RUN_VALUE_NAME = "AzreaDailyCompanion"

def is_startup_enabled() -> bool:
    wr = _winreg()
    if not wr: return False
    try:
        with wr.OpenKey(wr.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, wr.KEY_READ) as k:
            try:
                val, _ = wr.QueryValueEx(k, RUN_VALUE_NAME)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception:
        return False

def enable_startup(enable: bool) -> bool:
    wr = _winreg()
    if not wr: return False
    try:
        with wr.OpenKey(wr.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, wr.KEY_SET_VALUE) as k:
            if enable:
                wr.SetValueEx(k, RUN_VALUE_NAME, 0, wr.REG_SZ, f'"{app_exec_path()}"')
            else:
                try:
                    wr.DeleteValue(k, RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
