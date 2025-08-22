import os, sys
# Add repo root to sys.path so "import app" works in CI and locally
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
