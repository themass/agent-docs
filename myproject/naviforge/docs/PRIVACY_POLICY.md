# NaviForge Privacy Policy

_Last updated: 2026-08-18_

NaviForge (“we”, “the extension”) is a Chrome extension that runs an AI agent in
your browser. This policy describes what data is processed, where it stays, and what
you control.

## Summary

- **Local-first**: Chat history, settings, and workspace files default to your device.
- **Bring your own model (default)**: When you configure your own API, page text and
  attachments go directly to **the LLM endpoint you choose**. We do not receive that traffic.
- **Optional NaviForge hosted inference**: If you register and choose fully managed mode,
  requests go through our API gateway; we meter usage against your subscription. Login is
  required only for hosted mode—not for self-configured models.
- **Optional local Host**: Separate software on your machine (`127.0.0.1`); not part of the
  Chrome Web Store package.

## Data the extension may process

| Data | Purpose | Stored locally? | Sent off-device? |
|------|---------|-----------------|------------------|
| Page text / DOM summaries | Agent tasks | Session logs in extension storage / `~/NaviForge` | To your LLM provider when you run the Agent |
| Screenshots / images / OCR | Vision tasks, screenshot studio | Workspace `shots/` when saved | To your vision model when you OCR or attach images |
| Voice / microphone | Dictation in composer | Optional audio files in workspace | To speech/LLM services if you use voice features |
| API keys (LLM, Brave/Tavily search) | Authentication | `chrome.storage.local` if you enable “Store API Key” | Only to the provider you chose |
| Network metadata / bodies | Debugging, Agent verification | Sniff projects locally when enabled | Not to NaviForge; may appear in prompts to your LLM |
| Site profiles / playbooks | Faster re-extraction | Local storage / workspace | Only if included in Agent prompts |

## Optional features (higher risk, off by default)

- **Network Plane / debugger**: Observes network activity on pages you use with the Agent.
- **Modify Header**: Injects request/response headers on all `http(s)` traffic when you
  explicitly enable it in Settings → Privacy.
- **DOM script injection / MAIN probe**: Only when toggled in Privacy settings.

## Optional Local Host (not part of the Chrome Web Store package)

You may install **NaviForge Host** separately: a process on `127.0.0.1` that lets
external tools (e.g. MCP clients) queue browser tasks and access your `~/NaviForge`
folder. It uses a Bearer token on localhost. The Host does not send data to NaviForge;
it only communicates between your machine and the extension.

## Data retention and deletion

- Adjust **activity retention** in Settings → Privacy.
- **Clear all local data** in Settings → Advanced removes extension storage (not
  `~/NaviForge` unless you delete that folder yourself).
- Disabling **Store API Key** and saving privacy settings removes stored keys.

## Children

NaviForge is not directed at children under 13.

## Changes

We may update this policy. Material changes will be reflected in the extension release
notes or an updated date above.

## Contact

**Support:** `justbegin010@gmail.com`
