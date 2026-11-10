"""测试共享夹具。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def memory_schema():
    """确保 ca_memory_item 存在。alembic upgrade head 幂等，且不 downgrade，避免影响其他模块的 ca_ 表。"""
    url = os.environ.get("COMPANION_TEST_MYSQL_URL", "")
    if not url:
        pytest.skip("needs COMPANION_TEST_MYSQL_URL")
    env = {**os.environ, "COMPANION_MYSQL_URL": url, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=ROOT, env=env, check=True, capture_output=True)
