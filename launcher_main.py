#!/usr/bin/env python3
"""
Launcher for App Blocker Monitor.
Used by PyInstaller to ensure 'app' package structure is preserved.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.main import main

if __name__ == "__main__":
    main()
