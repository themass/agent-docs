# NaviForge Privacy Policy

_Last updated: 2026-11-06_

NaviForge (“we”, “the Product”, “the extension”) is a Chrome browser extension that helps you run an AI agent on web pages you choose. This privacy policy explains **what personal or sensitive user data we collect**, **how we handle and use it**, **how we store it**, and **how we share it**. Omission of any of these topics is not intended; each is addressed below.

**Developer / data controller contact:** `justbegin010@gmail.com`

---

## 1. Summary

- **Local-first by default**: Chat history, settings, API keys (if you opt in to store them), and workspace files are stored on your device.
- **Bring your own model (BYOK, default)**: When you configure your own LLM or search API, task content goes to **the provider you choose**. We do not operate a NaviForge cloud that receives that traffic in BYOK mode.
- **Optional hosted inference**: If you enable managed/hosted mode and sign in, requests may go through our API gateway for metering; login is required only for that mode.
- **Optional ads**: When enabled in a release, Google AdSense may load in iframes from pages we host (not inside the extension package).
- **We do not sell** your personal or sensitive user data.

---

## 2. Personal and sensitive user data we collect or process

Depending on which features you use, the Product may process:

| Category | Examples | When |
|----------|----------|------|
| **Web page content** | Visible text, DOM summaries, links, titles, URLs of tabs you use with the Agent | When you run Agent / toolkit actions on a page |
| **Screenshots & images** | Page captures, OCR crops, screenshot-studio exports | When you capture, OCR, or attach images |
| **Audio** | Microphone input for dictation | Only if you use voice features and grant permission |
| **Credentials you provide** | LLM API keys, web-search API keys | If you enter them and enable “Store API Key” |
| **Account data (hosted mode only)** | Email / login identifiers, access tokens, usage/quota metadata | Only if you register and use managed login |
| **Network technical data (optional)** | Request URLs, headers, response bodies from pages you debug | Only if you enable Network Plane / related privacy toggles |
| **Local settings & activity** | Preferences, retention settings, run/session logs, site profiles/playbooks | Continuously while the extension is installed |
| **Ad-related identifiers (optional)** | Cookie / device signals used by Google for ad delivery | Only when AdSense embeds are enabled in a release |

We do **not** require a NaviForge account for the default BYOK experience. We do **not** intentionally collect government IDs, payment card numbers, or precise GPS location through the extension UI.

Chrome permissions (e.g. access to websites you use with the Agent, storage, optional debugger) are used only to provide the features described in the store listing and this policy.

---

## 3. How we handle and use data

We use the data above solely to:

1. **Perform your requested tasks** (Agent runs, OCR, screenshot studio, toolkit actions).
2. **Authenticate to services you configure** (your LLM / search keys, or hosted login tokens).
3. **Persist local history and settings** so the Product works across sessions.
4. **Improve reliability on your device** (e.g. optional site profiles / playbooks stored locally).
5. **Meter optional hosted usage** (if you use managed inference).
6. **Show optional advertising** (if AdSense is enabled in that release).
7. **Respond to support requests** you send to our contact email.

We do **not** use personal or sensitive user data to build unrelated advertising profiles beyond what Google AdSense may do when ads are enabled. We do **not** use your page content for our own model training unless a future hosted feature explicitly discloses that and you opt in (today: **no**).

---

## 4. How we store data

| Location | What | Control |
|----------|------|---------|
| **Your browser** (`chrome.storage.local` / session) | Settings, optional API keys, extension activity logs | Clear via Settings → Advanced / retention controls |
| **Your computer** (`~/NaviForge` workspace when used) | Saved files, scripts, shots, optional audio | Delete the folder yourself; extension “clear” may not remove it |
| **Your chosen LLM / search provider** | Prompt content you send during a run | Subject to that provider’s privacy policy and retention |
| **NaviForge hosted API (optional)** | Account session and usage metering if you use hosted mode | Contact us to request account deletion |
| **Ad embed host (optional)** | AdSense scripts on pages we host for iframes | See Google’s policies; ads off until configured |

**Security**: Keys and tokens are stored in browser extension storage when you opt in; we recommend not storing keys on shared devices. Transmission to third-party APIs uses HTTPS when those providers support it. Optional Local Host binds to `127.0.0.1` with a Bearer token and is **not** part of the Chrome Web Store package.

**Retention**: Adjust activity retention in Settings → Privacy. Disabling “Store API Key” and saving removes stored keys. Hosted account records are kept while the account is active and as needed for billing/abuse prevention.

---

## 5. How we share data (disclosure / third parties)

We share or transmit data only as follows. **We do not sell personal or sensitive user data.**

| Recipient | What may be shared | Purpose | When |
|-----------|--------------------|---------|------|
| **LLM / vision / speech providers you configure** (e.g. OpenAI-compatible APIs) | Page text, images, prompts, tool results you generate | To complete Agent / OCR / voice tasks | Every BYOK (or vision) run you start |
| **Web search providers you configure** (e.g. Brave, Tavily) | Search queries | Web search tool | When you use search features with those keys |
| **NaviForge hosted gateway** | Account auth, prompts/usage as needed for the plan | Hosted inference & metering | Only if you enable hosted mode and sign in |
| **Google (AdSense)** | Standard ad / cookie signals | Display ads in extension UI iframes | Only if ads are enabled in that release |
| **Service providers we use to host this privacy page / static files** | Ordinary web server logs (IP, user agent) when you open the policy URL | Serve documentation | When you visit the policy page |
| **Legal / safety** | Limited data if required | Comply with law or protect users | Only when legally required or to prevent abuse |

**Optional Local Host** (separate install): exchanges data only between processes on **your machine** and the extension; it does not send browsing data to NaviForge servers.

We do not share your data with unrelated advertisers for their own marketing, other than Google AdSense when ads are on.

---

## 6. Your choices and rights

- Use **BYOK** without creating a NaviForge account.
- Leave Network Plane, Modify Header, DOM inject/probe, and ads **off** (defaults / release configuration).
- Clear local extension data in Settings; delete `~/NaviForge` manually if needed.
- Revoke Chrome site permissions or uninstall the extension at any time.
- For hosted accounts or policy questions: email `justbegin010@gmail.com` to request access, correction, or deletion of account-related data we hold.

---

## 7. Children

NaviForge is not directed at children under 13. We do not knowingly collect personal information from children under 13. If you believe a child has provided such data, contact us and we will delete it.

---

## 8. International transfers

If you use third-party APIs or hosted mode, data may be processed in countries where those providers or our gateway operate. Those transfers are necessary to provide the feature you requested and are subject to the recipient’s terms and applicable law.

---

## 9. Changes

We may update this policy. The “Last updated” date at the top will change when we do. Material changes will also be noted in extension release notes when practical. Continued use after an update means you accept the revised policy.

---

## 10. Contact

**Email:** [justbegin010@gmail.com](mailto:justbegin010@gmail.com)

If you have questions about collection, handling, storage, or sharing of your data, contact us at the address above.
