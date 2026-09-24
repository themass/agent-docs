#!/usr/bin/env python3
"""Legacy wrapper — use skills/content-studio/knowledge-library/scripts/report_dispatcher.py instead."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[1] / "skills/content-studio/knowledge-library/scripts/report_dispatcher.py"
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
