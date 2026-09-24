# Chrome Web Store compliance checklist

Internal runbook for publishing `@naviforge/extension`. Not shown to end users.

## Before upload

- [ ] `npm run check` and `npm run build` in `naviforge/apps/extension`
- [ ] `npm run zip` → upload `dist/*.zip` to [Developer Dashboard](https://chrome.google.com/webstore/devconsole)
- [ ] Bump `version` in `wxt.config.ts` / `package.json`
- [ ] Test zip in a **clean Chrome profile** (install → model → side panel → screenshot studio)
- [ ] Unzip build artifact; grep for `sk-`, `apiKey`, passwords, internal URLs

## Legal (required by Google)

- [ ] Host privacy policy at a **public https URL** (HTML recommended — see `docs/privacy_navi.html`)
- [ ] Set `PRIVACY_POLICY_URL` in `apps/extension/src/lib/compliance.ts` (currently points to deployed host)
- [ ] Replace placeholder support email in privacy policy
- [ ] Complete **Data safety** form in Dev Console (align with privacy policy)
- [ ] Single-purpose statement: side-panel AI agent for understanding and acting on web pages

## Store listing assets

- [ ] Extension icons: `apps/extension/public/icon-16.png` … `icon-128.png` (in zip)
- [ ] Upload **`docs/store-assets/icon-128-store.png`** (128×128) in Dev Console listing
- [ ] Optional: **`docs/store-assets/icon-512-store.png`** (512×512)
- [ ] ≥1 screenshot (1280×800 recommended): Agent side panel, screenshot studio, toolkit
- See `docs/store-assets/README.md`

## Permissions review prep

| Permission | Why | User control |
|------------|-----|--------------|
| `tabs`, `scripting`, `sidePanel` | Agent on active tab, side panel UI | Core product |
| `storage` | Settings, sessions | — |
| `debugger` | Network Plane (filtered network events) | Privacy toggles; off when network disabled |
| `declarativeNetRequest` | Modify Header | **Off by default**; Settings → Privacy |
| `contextMenus`, `downloads`, `alarms` | Toolkit, saves, host poll | — |
| `host_permissions: <all_urls>` | Read/act on arbitrary sites | **High review risk** — prepare justification; consider `optional_host_permissions` in a follow-up |
| ~~`nativeMessaging`~~ | Removed — unused | — |

## Sensitive defaults (implemented)

- Modify Header: `enabled: false` (`DEFAULT_MODIFY_HEADERS`)
- Host bridge: `enabled: false` (`DEFAULT_HOST`)
- Network intercept, DOM inject, MAIN probe: off in `DEFAULT_PRIVACY`
- `visionEnabled`: on for OCR/screenshot UX; user can disable in model settings

## Host bridge (optional, not in store package)

Explain in listing: extension works standalone. **NaviForge Host** (`apps/host`) is an
optional localhost companion for MCP / filesystem — user installs separately. See
`apps/host/README.md`.

## Post-publish

- Monitor reviews and crash reports
- Permission changes trigger re-review
- Keep `docs/LIVE_SITE_TEST_PLAN.md` publish gates for releases
