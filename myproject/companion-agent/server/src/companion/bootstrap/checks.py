"""启动检查（fail-closed，A §5.5）。任一项不过就拒绝启动，并列出具体原因。"""

from __future__ import annotations


class StartupRefused(RuntimeError):
    pass


def assert_storage_reachable(store: object, *, bucket: str) -> None:
    """对象存储凭据真的能用吗（HEAD bucket）。

    **为什么需要这一步**：TOS 的 secret 配错时，服务能正常启动、接口也都挂上了，
    只在真正上传时抛 ``SignatureDoesNotMatch`` 变成 500。客户端看到的是"服务器坏了"，
    实际原因是一行 ``.env``——2026-11-17 就是这样连续失败了 8 天（``companion/`` 下 0 个对象）。
    HEAD bucket 是一次请求的代价，把这类错误从"运行期 500"挪到"启动即失败"。

    只在配置了 TOS 时调用；没配 TOS 的环境（上传接口本来就不挂）不受影响。
    """
    try:
        store.check_bucket()
    except Exception as exc:  # noqa: BLE001 —— 启动期要把原始错误完整带出来
        raise StartupRefused(
            f"对象存储不可用（bucket={bucket}）：{type(exc).__name__}: {exc}。"
            f"检查 TOS_ENDPOINT / TOS_BUCKET / TOS_ACCESS_KEY / TOS_SECRET_KEY 是否配对"
        ) from exc


def assert_startup_safe(*, env: str, auth_verifier: str, brain_name: str | None = None) -> None:
    problems: list[str] = []
    if env == "prod":
        if auth_verifier == "allow_all":
            problems.append("COMPANION_ENV=prod 时不允许 COMPANION_AUTH_VERIFIER=allow_all（任何人都能冒充任何用户）")
        if brain_name is not None and brain_name.lower().startswith("fake"):
            problems.append("COMPANION_ENV=prod 时不允许假大脑（会静默返回占位回复）")
    if problems:
        raise StartupRefused("; ".join(problems))
