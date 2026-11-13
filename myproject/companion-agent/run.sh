#!/usr/bin/env bash
# companion-agent 的启动入口。三种进程、数据库迁移、语音连通性检查。
#
#   ./run.sh api        HTTP/SSE 服务（手机 App 请求的那一端）
#   ./run.sh jobs       后台任务进程（记忆、画像、提醒、主动消息、清理）——不部署它，这些功能会静默失效
#   ./run.sh voice      语音 worker（连 LiveKit，用户开语音时被派进房间）
#   ./run.sh migrate    建表/升级数据库结构
#   ./run.sh check      启动前检查：配置是否齐、库和 Redis 是否连得上
#   ./run.sh test       跑测试
#
# 环境和配置从 .env 读（不入库）。真实环境变量优先于 .env。

set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
[ -x "$PY" ] || { echo "缺少虚拟环境：先执行 python -m venv .venv && .venv/bin/pip install -e '.[dev]'"; exit 1; }
export PYTHONPATH=src

# 把 .env 载入进程环境。适配器和 LiveKit CLI 读的是 os.environ，不读 .env；
# 只靠 Settings 读 .env 的话，音色、供应商会悄悄退回默认值。
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

cmd="${1:-help}"
case "$cmd" in
  api)
    exec "$PY" -m companion.serve
    ;;
  jobs)
    exec "$PY" -m companion.worker_jobs
    ;;
  voice)
    exec "$PY" -m companion.worker
    ;;
  migrate)
    if [ -z "${COMPANION_DATABASE_URL:-}" ] && [ -z "${COMPANION_DB_HOST:-}" ]; then
      echo "没有配置数据库：COMPANION_DATABASE_URL 或 COMPANION_DB_* 至少给一组"; exit 2
    fi
    exec "$PY" -m alembic upgrade head
    ;;
  check)
    exec "$PY" - <<'PYEOF'
import asyncio, os, sys
from companion.config import Settings

s = Settings()
def need(name, ok, hint=""):
    print(f"  {'✓' if ok else '✗'} {name}{'' if ok else '  ← ' + hint}")
    return ok

print("配置：")
results = [
    need("数据库地址", bool(s.database_url), "COMPANION_DATABASE_URL 或 COMPANION_DB_*"),
    need("Redis 地址", bool(s.companion_redis_url), "COMPANION_REDIS_URL（会话锁与事件流靠它，语音与文字共用）"),
    need("模型网关", bool(s.companion_llm_api_base and s.companion_llm_api_key), "COMPANION_LLM_API_BASE / _API_KEY"),
    need("登录态校验", s.companion_auth_verifier != "allow_all" or s.companion_env != "prod",
         "生产环境不允许 allow_all：设 COMPANION_AUTH_VERIFIER=redis_token"),
]
print(f"  质检记录: {'开' if s.companion_qa_enabled else '关'}（COMPANION_QA_ENABLED）"
      f"  保留 {s.companion_qa_retention_days} 天")
print(f"  语音 worker 单进程房间上限: {s.companion_voice_max_rooms or '不限'}（COMPANION_VOICE_MAX_ROOMS）")

async def ping():
    print("连通性：")
    if s.database_url:
        from companion.bootstrap.database import make_engine, profile_for
        from sqlalchemy import text
        engine = make_engine(s.database_url, profile_for("voice"), process_tag="check")
        try:
            async with engine.connect() as c:
                v = (await c.execute(text("select current_database(), current_setting('server_version')"))).one()
                print(f"  ✓ 数据库 {v[0]}（PostgreSQL {v[1].split()[0]}）")
        except Exception as e:
            print(f"  ✗ 数据库连不上：{type(e).__name__}: {e}"); results.append(False)
        finally:
            await engine.dispose()
    if s.companion_redis_url:
        import redis.asyncio as r
        client = r.from_url(s.companion_redis_url)
        try:
            await client.ping(); print("  ✓ Redis")
        except Exception as e:
            print(f"  ✗ Redis 连不上：{type(e).__name__}: {e}"); results.append(False)
        finally:
            await client.aclose()

asyncio.run(ping())
print("\n语音（只在需要语音时看）：")
for name, ok, hint in (
    ("LiveKit 凭据", bool(s.livekit_url and s.livekit_api_key and s.livekit_api_secret), "LIVEKIT_URL / _API_KEY / _API_SECRET"),
    ("语音开关", os.getenv("COMPANION_VOICE_ENABLED", "false").lower() in {"1","true","yes"}, "COMPANION_VOICE_ENABLED=true"),
    ("火山凭据", bool(os.getenv("VOLC_TTS_API_KEY") and os.getenv("VOLC_ASR_API_KEY")), "VOLC_TTS_* / VOLC_ASR_*"),
):
    print(f"  {'✓' if ok else '·'} {name}" + ("" if ok else f"  （{hint}）"))

sys.exit(0 if all(results) else 1)
PYEOF
    ;;
  test)
    exec "$PY" -m pytest "${@:2}"
    ;;
  *)
    # 只打印文件头那段注释（到第一个空行为止），末尾不夹带代码
    awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0" 
    ;;
esac
