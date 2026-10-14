"""TencentDB Memory Proxy — transport headers for Hermes (no core patches).

Reads TDAI_TEAM_ID / TDAI_AGENT_ID / TDAI_TASK_ID from the Gateway process env
(written by sync-content-studio-secrets.sh) and merges model.default_headers from config.
Sets x-conversation-id from the active Hermes session_id on each main-turn LLM request.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
logger = logging.getLogger(__name__)

_ENV_HEADERS = (
    ("x-team-id", "TDAI_TEAM_ID"),
    ("x-agent-id", "TDAI_AGENT_ID"),
    ("x-task-id", "TDAI_TASK_ID"),
)


def _config_default_headers() -> Dict[str, str]:
    try:
        from hermes_cli.config import cfg_get, load_config_readonly

        cfg = load_config_readonly()
        raw = cfg_get(cfg, "model", "default_headers")
        if not isinstance(raw, dict):
            raw = {}
        alias = cfg_get(cfg, "model", "extra_headers")
        if isinstance(alias, dict) and alias:
            raw = {**raw, **alias}
        return {str(k): str(v) for k, v in raw.items() if v is not None}
    except Exception:
        logger.debug("tdai-proxy-headers: could not read model headers from config", exc_info=True)
        return {}


def _merge_tdai_headers(existing: Dict[str, str]) -> Dict[str, str]:
    out = dict(existing)
    for hdr, env_key in _ENV_HEADERS:
        val = os.environ.get(env_key, "").strip()
        if val:
            out[hdr] = val
    for k, v in _config_default_headers().items():
        if k.startswith("x-") and v:
            out[k] = v
    return out


def _proxy_url_candidates() -> list[str]:
    out: list[str] = []
    for key in ("TDAI_PROXY_URL", "TDAI_PROXY_HERMES_BASE"):
        val = os.environ.get(key, "").strip().rstrip("/")
        if val:
            out.append(val.lower())
    return out


def _is_memory_proxy_base_url(base_url: str) -> bool:
    """True when this LLM request targets TencentDB Memory Proxy (8096 /hermes/…)."""
    u = (base_url or "").strip()
    if not u:
        return False
    low = u.lower()
    if "/hermes/" in low:
        return True
    if ":8096" in low:
        return True
    for proxy in _proxy_url_candidates():
        if proxy and proxy in low:
            return True
    return False


def _on_llm_request(**kwargs: Any) -> Optional[Dict[str, Any]]:
    request = kwargs.get("request")
    if not isinstance(request, dict):
        return None
    base_url = str(kwargs.get("base_url") or "")
    if not _is_memory_proxy_base_url(base_url):
        return None

    merged = dict(request)
    xh = _merge_tdai_headers(dict(merged.get("extra_headers") or {}))
    session_id = str(kwargs.get("session_id") or "").strip()
    if session_id:
        xh["x-conversation-id"] = session_id
    if not any(xh.get(h) for h, _ in _ENV_HEADERS):
        logger.warning(
            "tdai-proxy-headers: memory proxy URL but missing team/agent/task "
            "(set TDAI_* in Gateway .env and tdai-hermes-ids.env)"
        )
        return None
    merged["extra_headers"] = xh
    return {"request": merged}


def register(ctx: Any) -> None:
    ctx.register_middleware("llm_request", _on_llm_request)
    logger.info("tdai-proxy-headers: llm_request middleware registered")
