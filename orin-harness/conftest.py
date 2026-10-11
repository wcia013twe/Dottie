"""Pytest path setup: `orin-harness/` on sys.path so `magneto_harness` imports.

Kept at the package root (not in tests/) so pytest adds it to sys.path on
collection. The harness wires `cane-vision/` and `databricks/platform/` itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))
