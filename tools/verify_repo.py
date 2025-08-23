
#!/usr/bin/env python3
"""
Verification script for Azrea's Daily Companion Tracker.
- Checks required files exist
- Compiles all .py files
- Imports dependencies listed in requirements.txt (best effort)
- Smoke-creates QApplication + MainWindow in offscreen mode
- Writes a detailed report to build/verify/report.txt and sets exit status
"""
import os, sys, compileall, importlib, subprocess, shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "verify"
BUILD.mkdir(parents=True, exist_ok=True)
REPORT = BUILD / "report.txt"

required_files = [
    "app/main.py",
    "app/services.py",
    "app/utils.py",
    "requirements.txt",
    "installer.iss",
]

optional_files = [
    "app/assets/app_icon.ico",
    "docs/vision_document.pdf",
]

def w(line: str):
    print(line)
    with REPORT.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def check_files() -> bool:
    ok = True
    w("== File presence checks ==")
    for rel in required_files:
        p = ROOT / rel
        if p.exists():
            w(f"PASS: {rel}")
        else:
            w(f"FAIL: {rel} missing")
            ok = False
    for rel in optional_files:
        p = ROOT / rel
        if p.exists():
            w(f"INFO: {rel} present")
        else:
            w(f"INFO: {rel} not found (optional)")
    return ok

def compile_repo() -> bool:
    w("\n== Byte-compile python files ==")
    try:
        res = compileall.compile_dir(str(ROOT), force=False, quiet=1, rx=r'build|dist|.git|venv')
        w("PASS: compileall completed")
        return True
    except Exception as e:
        w(f"FAIL: compileall exception: {e}")
        return False

def parse_requirements():
    req = ROOT / "requirements.txt"
    mods = []
    if not req.exists():
        return mods
    for line in req.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].split(">=")[0].split("~=")[0].strip()
        # map common packages to import names
        mapping = {
            "PyQt5": "PyQt5",
            "requests": "requests",
            "yahooquery": "yahooquery",
            "reportlab": "reportlab",
            "pydrive2": "pydrive2",
            "packaging": "packaging",
        }
        mods.append(mapping.get(name, name.replace("-", "_")))
    return sorted(set(mods))

def import_deps(mods) -> bool:
    w("\n== Import dependencies ==")
    ok = True
    for m in mods:
        try:
            importlib.import_module(m)
            w(f"PASS: import {m}")
        except Exception as e:
            ok = False
            w(f"FAIL: import {m}: {e}")
    return ok

def smoke_gui() -> bool:
    w("\n== GUI smoke (offscreen) ==")
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        from app import main as m
        app = QApplication.instance() or QApplication([])
        wdw = m.MainWindow()  # should not raise
        w(f"PASS: MainWindow constructed; tabs={wdw.tabs.count()}")
        return True
    except Exception as e:
        w(f"FAIL: GUI smoke: {e}")
        return False

def main():
    if REPORT.exists():
        REPORT.unlink()
    w(f"Verification run: {datetime.now().isoformat(timespec='seconds')}")
    passed = True
    passed &= check_files()
    passed &= compile_repo()
    mods = parse_requirements()
    if mods:
        passed &= import_deps(mods)
    else:
        w("INFO: requirements.txt not parsed or empty")
    passed &= smoke_gui()
    w("\n== Summary ==")
    w("OVERALL: PASS" if passed else "OVERALL: FAIL")
    sys.exit(0 if passed else 2)

if __name__ == "__main__":
    main()
