#!/usr/bin/env bash
# systemd 的前台执行器：api / voice 各起一个进程，环境变量口径与 process.sh 完全一致。
#
#   run-as-service.sh api | voice
#
# 为什么单独一个脚本而不是把命令行写进 unit：.env 里的键必须导出到进程环境
# （适配器和 LiveKit CLI 只读 os.environ，不读 .env），unit 里写 `set -a; . ./.env`
# 可读性差且引号陷阱多。脚本 exec 掉自己，systemd 跟踪到的就是 python 本体。
#
# 日志走 stdout/stderr，由 systemd journal 收（journald 负责轮转），
# 不再写 .data/logs/*.log —— 两处写同一文件会互相踩。process.sh 的 `logs` 子命令
# 在 systemd 模式下会改读 journal。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"      # 项目根：scripts/ server/ .data/
SERVER="${ROOT}/server"
DEPLOY_ENV="${ROOT}/.data/deploy.env"

name="${1:-}"
case "$name" in
  api)   module="companion.serve" ;;
  voice) module="companion.worker" ;;
  *) printf '[run-as-service] 用法: %s api|voice\n' "$0" >&2; exit 2 ;;
esac

# deploy.env：只认白名单键，按字面读（与 process.sh 同一套规矩，已导出的环境变量优先）。
_deploy_env_keys="CA_API_HOST CA_API_PORT CA_START_TIMEOUT"
declare -A _from_env=()
for key in $_deploy_env_keys; do
  [[ -n "${!key+x}" ]] && _from_env[$key]="${!key}"
done
if [[ -r "$DEPLOY_ENV" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$line" in "" | "#"*) continue ;; esac
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"; value="${line#*=}"
    key="${key//[[:space:]]/}"
    case " $_deploy_env_keys " in
      *" $key "*) printf -v "$key" '%s' "${_from_env[$key]:-$value}" ;;
    esac
  done <"$DEPLOY_ENV"
fi
CA_API_HOST="${CA_API_HOST:-127.0.0.1}"
CA_API_PORT="${CA_API_PORT:-8081}"

[[ -x "${SERVER}/.venv/bin/python" ]] || { printf '[run-as-service] 没有虚拟环境 %s — 先跑 ./scripts/deploy.sh\n' "${SERVER}/.venv" >&2; exit 1; }
[[ -f "${SERVER}/.env" ]] || { printf '[run-as-service] 缺 %s/.env\n' "$SERVER" >&2; exit 1; }

cd "$SERVER"
export PYTHONPATH=src
set -a
# shellcheck disable=SC1091
. ./.env
set +a
export COMPANION_HOST="$CA_API_HOST" COMPANION_PORT="$CA_API_PORT"

exec "${SERVER}/.venv/bin/python" -m "$module"
