#!/usr/bin/env python3
"""Runs the error-copy assertions against the real frontend sources.

Why a script and not a test: the frontend has no JS test runner, and the two modules
that decide what a user reads on a failure (`lib/api/errors.ts`,
`lib/api/user-error.ts`) are pure functions. So we compile just those two with the
project's own TypeScript and run assertions on them -- no browser, no served build, no
network. `scripts/verify_auth_errors.py` covers the same ground through the actual
forms; this one can run anywhere, which is what makes it suitable for test-local.sh.

Usage:
    python scripts/verify_error_copy.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lib.bootstrap import ensure_project_env

ROOT = ensure_project_env()
WEB = ROOT / "frontend" / "web"
CHECKS = ROOT / "scripts" / "lib" / "error-copy-checks.mjs"
MODULES = ("errors.ts", "user-error.ts")
SERVER_SRC = ROOT / "backend" / "server" / "src" / "jc"

#: Codes the frontend is not expected to translate. Admin endpoints are operational
#: surfaces, read by whoever is holding the token, not by a user mid-task.
UNMAPPED_BY_DESIGN = frozenset({"admin_disabled", "admin_token_invalid"})

_RAISE = re.compile(
    r"(?:AppError|AuthError|ConflictError|NotFoundError|ForbiddenError)\("
    r"(?P<args>[^()]{0,300}?)code=\"(?P<code>[a-z0-9_]+)\"",
    re.S,
)
#: Codes written straight into an HTTP error body rather than raised. Exception handlers
#: do this (`JSONResponse(..., content={"code": "invalid_upload", ...})`), and the
#: `_RAISE` pattern cannot see them — which is how `invalid_upload` reached users with no
#: copy behind it while this gate still reported PASS.
#:
#: Anchored on `content=` on purpose. `"code"` on its own is used by two other, unrelated
#: namespaces that are not HTTP errors and have no business in a user-copy map: reviewer
#: findings (`issues=[{"code": "llm_disabled", ...}]`, rendered by the review UI with its
#: own wording) and MCP tool results (`{"code": "review_required"}`, addressed to the
#: model, never to a person).
_RESPONSE_CODE = re.compile(
    r'content=\{[^{}]{0,200}?"code":\s*"(?P<code>[a-z0-9_]+)"',
    re.S,
)
_MESSAGE = re.compile(r'"([^"]{4,})"')
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _server_raises() -> dict[str, list[tuple[str, str]]]:
    """Every `raise` that carries an error code: code -> [(file:line, message)]."""
    found: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(SERVER_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _RAISE.finditer(text):
            message = _MESSAGE.search(match.group("args"))
            where = f"{path.relative_to(SERVER_SRC)}:{text[: match.start()].count(chr(10)) + 1}"
            found.setdefault(match.group("code"), []).append(
                (where, message.group(1) if message else "")
            )
    return found


def _response_literal_codes() -> dict[str, list[str]]:
    """Codes emitted as a literal response body: code -> ["file:line", ...]."""
    found: dict[str, list[str]] = {}
    for path in sorted(SERVER_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _RESPONSE_CODE.finditer(text):
            where = f"{path.relative_to(SERVER_SRC)}:{text[: match.start()].count(chr(10)) + 1}"
            found.setdefault(match.group("code"), []).append(where)
    return found


def _mapped_codes() -> set[str]:
    text = (WEB / "lib" / "api" / "user-error.ts").read_text(encoding="utf-8")
    block = text.split("const CODE_MESSAGES")[1].split("};")[0]
    return set(re.findall(r"^\s{2}([a-z0-9_]+):", block, re.M))


def check_codes_are_covered() -> int:
    """No error may reach a user as a generic status fallback.

    There are two layers and either one is enough, which is why this checks both rather
    than demanding a map entry for everything:

    - the `code -> copy` map, which does not depend on how the message was worded at the
      point of failure, and
    - a Chinese `message` at the `raise` itself, which can be more specific than one map
      entry can be (`fetch_too_large` means 500KB for a static page and a different limit
      for a dynamic one; collapsing them loses the number the user needs).

    With neither, the request falls through to `statusFallback` — 「请求的内容不存在。」
    for a 404 — which names no cause and suggests no next step. Nothing about adding a
    new `raise` prompts anyone to come back here, so the two sides get compared directly.
    """
    raises = _server_raises()
    literals = _response_literal_codes()
    mapped = _mapped_codes()
    uncovered: list[str] = []
    for code, sites in sorted(raises.items()):
        if code in mapped or code in UNMAPPED_BY_DESIGN:
            continue
        for where, message in sites:
            if not _CJK.search(message):
                uncovered.append(f"  {code}  ({where})  message={message!r}")
    # A literal code carries no message to inspect: the handler forwards whatever the
    # exception said, which may be in any language. So the map entry is the only
    # possible guarantee, and it is required rather than one of two options.
    for code, sites in sorted(literals.items()):
        if code in mapped or code in UNMAPPED_BY_DESIGN:
            continue
        for where in sites:
            uncovered.append(f"  {code}  ({where})  response literal, no CODE_MESSAGES entry")
    if uncovered:
        print(f"FAIL: {len(uncovered)} error sites would reach a user as a generic fallback")
        print("\n".join(uncovered))
        print("  fix either side: Chinese copy at the raise, or an entry in")
        print("  CODE_MESSAGES in frontend/web/lib/api/user-error.ts")
        return 1
    total = len(set(raises) | set(literals))
    print(
        f"PASS  every coded error has user-facing copy ({total} codes, "
        f"{len(literals)} from response literals; {len(mapped)} mapped in the frontend, "
        f"{len(UNMAPPED_BY_DESIGN)} operational exempt)"
    )
    return 0


def main() -> int:
    tsc = WEB / "node_modules" / ".bin" / "tsc"
    if not tsc.exists():
        print(f"FAIL: TypeScript not installed; run npm install in {WEB}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="jc-error-copy-") as tmp:
        work = Path(tmp)
        src = work / "src"
        src.mkdir()
        for name in MODULES:
            text = (WEB / "lib" / "api" / name).read_text(encoding="utf-8")
            # The path alias is a bundler concern; outside Next we resolve relatively.
            text = text.replace('"@/lib/api/errors"', '"./errors.js"')
            (src / name).write_text(text, encoding="utf-8")

        out = work / "out"
        compiled = subprocess.run(
            [
                str(tsc),
                *[f"src/{name}" for name in MODULES],
                "--target", "es2022",
                "--module", "esnext",
                "--moduleResolution", "bundler",
                "--strict",
                "--outDir", "out",
            ],
            cwd=work,
            capture_output=True,
            text=True,
        )
        if compiled.returncode != 0:
            print("FAIL: could not compile the error modules", file=sys.stderr)
            print(compiled.stdout or compiled.stderr, file=sys.stderr)
            return 1

        # Plain .mjs would be enough, but the compiled output is .js, so the directory
        # needs to be a module package for the imports to resolve.
        (out / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
        shutil.copy(CHECKS, out / "checks.mjs")

        result = subprocess.run(["node", "checks.mjs"], cwd=out, capture_output=True, text=True)
        sys.stdout.write(result.stdout)
        if result.stderr.strip():
            sys.stderr.write(result.stderr)

    return result.returncode or check_codes_are_covered()


if __name__ == "__main__":
    raise SystemExit(main())
