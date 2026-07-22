from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from scf_governed_executor.tests.test_independent_git_lifecycle import *  # noqa: F401,F403
