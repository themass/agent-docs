"""端到端：HTTP → 会话 → 回合 → 历史 → 角色 → 记忆 → 上传 → 确认，全部走真实存储与控制面。

需要：COMPANION_TEST_MYSQL_URL（vpn，表前缀 ca_）、COMPANION_TEST_REDIS_URL（共用，键前缀 ca:）。
上传部分需要**测试专用**的 TOS 配置（COMPANION_TEST_TOS_ENDPOINT / _BUCKET /
_ACCESS_KEY / _SECRET_KEY）；不配就跳过上传，绝不往共享桶写。
且只写入 companion-test/ 前缀。大脑用 FakeBrain（不调用真实模型）。
"""

import io
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

MYSQL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
REDIS = os.environ.get("COMPANION_TEST_REDIS_URL", "")
ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (MYSQL and REDIS), reason="needs COMPANION_TEST_DATABASE_URL (or COMPANION_TEST_MYSQL_URL) and COMPANION_TEST_REDIS_URL")

ME = {"Authorization": "Bearer 91001"}


@pytest.fixture(scope="module")
def migrated():
    env = {**os.environ, "COMPANION_MYSQL_URL": MYSQL, "COMPANION_DATABASE_URL": MYSQL, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True,
                   capture_output=True)
    yield


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (30, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _platform():
    from companion.memory.fake import InMemoryMemoryPort
    from companion.bootstrap.platform import default_prompts
    from companion.bootstrap.platform import build_platform
    from companion.brain.fake import FakeBrain
    from companion.config import Settings

    settings = Settings(
        companion_mysql_url=MYSQL,
        companion_redis_url=REDIS,
        # 必须用测试专用的桶与凭据：共享桶（生产在用）里写入测试文件不可接受，
        # 而且生产凭据可能带前缀限制，写进去就 403，把测试变成环境问题。
        tos_endpoint=os.environ.get("COMPANION_TEST_TOS_ENDPOINT", ""),
        tos_bucket=os.environ.get("COMPANION_TEST_TOS_BUCKET", ""),
        tos_access_key=os.environ.get("COMPANION_TEST_TOS_ACCESS_KEY", ""),
        tos_secret_key=os.environ.get("COMPANION_TEST_TOS_SECRET_KEY", ""),
        tos_region=os.environ.get("COMPANION_TEST_TOS_REGION", "cn-beijing"),
        tos_key_prefix="companion-test/",
    )
    return build_platform(settings, brain=FakeBrain(["你好，", "我记住了。"]),
                          prompts=default_prompts(), memory_port=InMemoryMemoryPort())


def test_end_to_end_over_http(migrated):
    from fastapi.testclient import TestClient

    from companion.api.http.deps import AllowAllVerifier
    from companion.bootstrap.app import create_app

    platform = _platform()
    app = create_app(livekit_url="", verifier=AllowAllVerifier(), platform=platform)
    with TestClient(app) as client:
        # 会话与回合
        session = client.post("/v1/sessions", json={"role_id": "academic-anthropologist"}, headers=ME)
        assert session.status_code == 201
        sid = session.json()["id"]
        receipt = client.post(f"/v1/sessions/{sid}/messages", json={"text": "你好吗"}, headers=ME)
        assert receipt.status_code == 202
        assert receipt.json()["disposition"] == "started"

        # 等回合结束：助手回复落库后出现在历史里
        reply = None
        deadline = time.time() + 20
        while time.time() < deadline and reply is None:
            items = client.get(f"/v1/sessions/{sid}/messages", headers=ME).json()["items"]
            reply = next((m for m in items if m["role"] == "assistant"), None)
            if reply is None:
                time.sleep(0.3)
        assert reply is not None, "assistant reply never reached history"
        assert reply["content"] == "你好，我记住了。"
        assert reply["turn_id"] == receipt.json()["turn_id"]

        # 他人不可见
        stranger = {"Authorization": "Bearer 91002"}
        assert client.get(f"/v1/sessions/{sid}/messages", headers=stranger).status_code == 404

        # 角色目录
        roles = client.get("/v1/roles", params={"limit": 1}, headers=ME).json()
        assert roles["total"] >= 283

        # 记忆（内存实现，重启即丢：见 T13 报告）
        fact = client.post("/v1/memory/facts", json={"content": "喜欢喝茶"}, headers=ME)
        assert fact.status_code == 201
        assert client.delete(f"/v1/memory/facts/{fact.json()['id']}", headers=ME).status_code == 204

        # 确认：未知编号按不存在处理
        assert client.get("/v1/actions/pending", headers=ME).status_code == 200
        assert client.post("/v1/actions/cfm_unknown/confirm", json={"accepted": True},
                           headers=ME).status_code == 404

        # 上传到 TOS（companion-test/ 前缀），再用签名地址读回
        if platform.uploads is not None and os.environ.get("COMPANION_TEST_TOS_BUCKET"):
            up = client.post("/v1/uploads", content=_png(), headers=ME)
            assert up.status_code == 201, up.text
            url = client.get(f"/v1/uploads/{up.json()['upload_id']}", headers=ME).json()["url"]
            with urllib.request.urlopen(url, timeout=20) as resp:
                assert resp.status == 200
                assert resp.read()[:3] == b"\xff\xd8\xff"  # 重新编码后的 JPEG
