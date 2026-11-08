# RS Helper — In-Game Plugin Specification

**Status:** Draft v0.1 · 2026-11-08
**Target:** RuneScape 3 official plugin system (Lua 5.4.8, distributed via mod.io)
**Source app:** `app.py` (Streamlit), `agent_instructions.md`, `account_profiles_archive.md`

> Everything in this spec comes from Jagex's official developer documentation
> (developer.runescape.com, read 2026-11-08) and from this repository's code.
> Jagex's AI policy allows feeding its API docs and their examples to AI tools.
> It does **not** allow feeding in other developers' plugins, so this spec
> deliberately never looks at any third-party plugin code.

---

## 0. Assumptions and decisions already made

| # | Decision | Notes |
|---|----------|-------|
| A1 | `httpAccess` to the Gemini and OpenAI APIs is assumed to be approvable. | Confirm with the Plugin Moderator at submission time. |
| A2 | The plugin is a **rewrite**, not a translation of `app.py`. | Jagex rejects "code output from language transcoding processes". |
| A3 | All code is hand-reviewed by the repo owner before submission. | Required by the AI Policy ("AI-assisted code is acceptable provided you personally review and understand it"). |
| A4 | The desktop app keeps working alongside the plugin. | It still needs moving off RuneMetrics (see Appendix A). |
| A5 | Bring-your-own-key: each player enters their own Gemini or OpenAI key. | The plugin has no server of its own. |

---

## 1. Goals and non-goals

**Goals**

1. One in-game popup window with two halves:
   - **Chat:** ask the AI advisor questions, grounded in the player's live stats, quests, goals and the RuneScape Wiki.
   - **Explorer:** browse the same data directly: Profile, Quests, Bosses, Items, To-Do, Wiki, Settings.
2. Read the player's data **live from the game client** instead of RuneMetrics or scraping.
3. Keep every feature of the desktop app that can legally and technically run in a plugin. Drop or replace the rest (see §6).
4. Pass Jagex moderation: readable, commented code, clear docs, correct permissions and data-protection statements.

**Non-goals**

- Anything that acts for the player, or gives live in-combat instructions (prayer switches, ability calls, where to stand). These are prohibited.
- Looking up, storing or sending data about **other** players.
- Image upload or screenshots for the AI (no screenshot API exists).
- Running Python, Playwright, or any local server.

---

## 2. Jagex rules that shape the design

| Rule (quoted from Jagex docs) | Source page | Design consequence |
|---|---|---|
| "Features that provide interpreted or actionable gameplay recommendations may be subject to stricter review." | Plugin guidelines → Subject to review | The AI advisor will get a stricter review. Keep it to planning and preparation, and say so in the listing. |
| Prohibited: "Automatic prayer switching/ability recommendations or execution." | Guidelines → Prohibited | The system prompt forbids live combat calls (§8.4). The Bosses tab shows preparation only (levels, gear, wiki links). |
| Prohibited: "Plugins cannot export any information about other players." Subject to review: "Obtaining any information about other players." | Guidelines | Only the logged-in character is ever read or sent. The desktop app's multi-account switcher is not ported. |
| Subject to review: "Any plugin which requests a permission." | Guidelines | `httpAccess` is **optional**. Without it the plugin still works offline (Explorer, To-Do, Profile from the client). |
| Subject to review: "Containing custom resources like images or sounds." | Guidelines | v1 ships no custom images or sounds and uses built-in game sprites only. |
| "Plugin code which is unnecessarily difficult to follow will result in rejection … transcoding … unvetted AI generation." | Guidelines → AI Policy | Small files, one job each, comments on every function, no clever tricks. The owner reviews every line. |
| "Specifying malformed URLs or URL shortener/redirect addresses will cause your plugin to be rejected." | HTTPRequest | Exact HTTPS base URLs only (§4). |
| Data sent outside the UK/EEA (e.g. USA) is "Case 3". | Submission process, UK adequacy | Gemini and OpenAI are US services, so: privacy notice, public contact email, and Jagex's adequacy form (§9). |
| "Plugins should support all of the major platforms … Windows, Linux, and Mac." | Submission process | No OS-specific code or paths. |
| "If you want to include lots of logging then it should be toggleable, and off by default." | Good practice | A `debug` switch in Settings, off by default. |
| Localisation: "Store all of your different text strings in a table structure in separate files for each language." | Good practice | All UI text lives in `lang/en.lua` from day one. |
| "Try not make a plugin that does pretty much the same as another plugin." | Good practice | Don't rebuild step-by-step quest guidance. Quest Helper already does that. Our Quests tab lists what's *available* and links to the wiki. |

---

