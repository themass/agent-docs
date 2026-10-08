# Third-party notices (NaviForge extension)

NaviForge includes open-source components. MIT unless noted.

| Component | License | Source |
|-----------|---------|--------|
| `@page-agent/page-controller` | MIT | https://github.com/alibaba/page-agent |
| `@mozilla/readability` | Apache-2.0 | https://github.com/mozilla/readability |
| `rrweb` | MIT | https://github.com/rrweb-io/rrweb |
| React / WXT / Vite ecosystem | MIT | see `package-lock.json` |

Full dependency tree: `npm ls` in `apps/extension`.

Dom automation in the content script uses **`@page-agent/page-controller`** as a library (not a separate product install).

**Public hosting:** upload [`third_party_navi.html`](third_party_navi.html) (not this `.md`) to your file server so browsers render a readable page.
