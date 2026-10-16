import json
from pathlib import Path

from jc.adapters.deerflow_harness_client import resolve_mcp_python_in_extensions


def test_resolve_mcp_python_rewrites_bare_python(tmp_path: Path) -> None:
    src = tmp_path / "extensions_config.json"
    src.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "jc": {
                        "command": "python",
                        "args": ["-m", "jc.mcp.server"],
                        "env": {"JC_MCP_USER_ID": "$JC_MCP_USER_ID"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    dest = tmp_path / "out.json"
    py = "/opt/venv/bin/python"
    pkg = tmp_path / "src"
    resolve_mcp_python_in_extensions(src, python_executable=py, package_src=pkg, dest=dest)
    data = json.loads(dest.read_text(encoding="utf-8"))
    spec = data["mcpServers"]["jc"]
    assert spec["command"] == py
    assert spec["env"]["PYTHONPATH"] == str(pkg)
    assert spec["cwd"] == str(tmp_path)
    assert spec["args"] == ["-m", "jc.mcp.server"]
