"""启动检查（fail-closed，A §5.5）。任一项不过就拒绝启动，并列出具体原因。"""

from __future__ import annotations


class StartupRefused(RuntimeError):
    pass


def assert_startup_safe(*, env: str, auth_verifier: str, brain_name: str | None = None) -> None:
    problems: list[str] = []
    if env == "prod":
        if auth_verifier == "allow_all":
            problems.append("COMPANION_ENV=prod 时不允许 COMPANION_AUTH_VERIFIER=allow_all（任何人都能冒充任何用户）")
        if brain_name is not None and brain_name.lower().startswith("fake"):
            problems.append("COMPANION_ENV=prod 时不允许假大脑（会静默返回占位回复）")
    if problems:
        raise StartupRefused("; ".join(problems))
