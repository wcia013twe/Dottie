"""Filesystem locations and import wiring for the Orin harness.

`cane-vision/` and `databricks/platform/` are sibling source directories, not
installed packages, so they are added to `sys.path` here. Import this module
before importing anything from `cane_vision` or `magneto_platform`.
"""

from __future__ import annotations

from pathlib import Path
import sys

HARNESS_DIR = Path(__file__).resolve().parent.parent           # orin-harness/
ROOT = HARNESS_DIR.parent                                       # repository root
CANE_VISION_DIR = ROOT / "cane-vision"
PLATFORM_DIR = ROOT / "databricks" / "platform"
DEFAULT_CONFIG = HARNESS_DIR / "config.yaml"
SCHEMA_DIR = ROOT / "databricks" / "contracts" / "v1"


def ensure_import_paths() -> None:
    for path in (CANE_VISION_DIR, PLATFORM_DIR):
        entry = str(path)
        if entry not in sys.path:
            sys.path.insert(0, entry)


ensure_import_paths()
