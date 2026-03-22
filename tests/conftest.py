from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="knowledgebase-tests-"))
os.environ.setdefault("KNOWLEDGE_DB_PATH", str(TEST_DB_DIR / "knowledge-test.db"))


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
