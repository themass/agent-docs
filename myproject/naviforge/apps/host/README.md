# NaviForge Host

Local-only bridge between MCP clients and the NaviForge Chrome extension. It binds to
`127.0.0.1`, exposes an authenticated task queue to the extension, and serves MCP over
stdio.

```bash
cd naviforge
export NAVIFORGE_HOST_TOKEN="$(openssl rand -hex 24)"
npm run host
```

Copy the token to **NaviForge Settings → MCP**, enable the Host bridge, and reload the
extension after a new build.

MCP client configuration:

```json
{
  "mcpServers": {
    "naviforge": {
      "command": "node",
      "args": ["/absolute/path/to/naviforge/apps/host/dist/index.js"],
      "env": {
        "NAVIFORGE_HOST_TOKEN": "the-same-secret-token"
      }
    }
  }
}
```

Tools:

- `naviforge_get_status`
- `naviforge_execute_browser_task`

HTTP (same Bearer token):

- `POST /net/traceroute` `{ "target": "1.1.1.1", "maxHops"?: 20 }` — runs system `traceroute` / `tracert`

The Host never accepts non-loopback connections. The shared token is mandatory because
untrusted web pages can otherwise probe localhost services.
