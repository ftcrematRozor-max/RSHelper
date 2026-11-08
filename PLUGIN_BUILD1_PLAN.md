# RS Helper Plugin — Build 1 Implementation Plan (v0.0.1)

**Status:** Draft · 2026-11-08
**Builds on:** `PLUGIN_SPEC.md` (reviewed 2026-11-08)
**Where it runs:** the plugin beta world only. Build 1 isn't submitted to mod.io.

Build 1 is the smallest plugin that does the risky parts end to end:

> open the window → allow web access → sign consent → enter an API key → chat with an AI provider and get answers back.

Everything else in the spec (Explorer tabs, wiki, citations, memory, Gemini and OpenAI) comes in later builds and slots into what Build 1 sets up.

---

## 1. Scope

**In Build 1**

| Area | What the player can do | Spec |
|---|---|---|
| Launcher | Open RS Helper from its ribbon icon in the game's Plugins window | §5.1 |
| Window | A popup with a header and **X**, a Chat pane, an Explorer pane (placeholder: "Explorer arrives in 0.1"), and a status bar. Both panes and the quick-action row collapse. The layout is remembered. | §5.2 |
| Setup panel | Step 1 web access, step 2 signed consent, step 3 API key (save, mask, check, forget) | §5.3, §9.2 |
| Settings page | The same setup controls in Plugin Hub → Settings, plus **Withdraw consent** and **Forget key** | §5.1, §9.2 |
| Chat | Ask a question, get an answer from **Claude** (the player's chosen model), ask follow-ups (last 6 turns), Stop a request, see clear errors | §5.3, §8 |
| Model choice | Pick the Claude model (Sonnet 5.5 default, Opus 5.5, Haiku 5.5, models loaded from the key, or a custom ID) and effort (low / medium / high) | §8.1a |
| Context | A one-line summary of the character (combat level, total level, every skill level, members world). The name isn't sent. | §8.2 |
| Quick actions | The collapsible row with one button: **Goal** (fills the input) | §5.3 |
| Tests | Out-of-game test harness plus GitHub Actions | §11.3 |

**Not in Build 1** (later builds): Gemini and OpenAI adapters (shown greyed out as "coming soon"), Explorer tabs, wiki search and citations, the source line and "Suggestion:" styling, session memory, GE prices, hotkey, window size presets and dragging, quest, boss and slayer templates.

**Provider choice: Claude, with a model choice** (owner review, 2026-11-08). Its request format has been checked against the current API docs. The player picks the model: **`claude-sonnet-5-5` (Sonnet 5.5) at effort `medium` is the default**, `claude-opus-5-5` and `claude-haiku-5-5` are built-in choices, and a custom model ID is allowed (spec §8.1a). Settings are stored per provider, so Build 2 adds Gemini (`gemini-3.8-flash`) and OpenAI (`gpt-6.1-sol`, effort `medium`) with their own model choices, without touching the chat or UI code.

---

## 2. Step 0 — beta-world spike (do this first)

Some unknowns in the spec could change how Build 1 is written. A throwaway plugin answers nine of them in one beta session before the real code starts.

- **Who does what:** Claude writes `plugin/spike/` (done: two dev plugins, a smoke test, and a step-by-step guide in `plugin/spike/README.md`, never zipped). You run it in the beta world and send back the console summary.
- **What you need:** a **separate** Anthropic API key with a low spending limit. Create it in the Anthropic Console and use it only for testing.

| # | Question (spec ref) | How the spike checks | If the answer is "no" |
|---|---|---|---|
| S1 | Can a key be **pasted** into an `InputField`? Does pasting fire `KeyTyped` for other plugins? (Q14) | A field to paste into, plus a second tiny plugin that logs `Event.KeyTyped` | Typing only. The consent screen already warns about it. Ask the API Council for a paste-safe field. |
| S2 | Does a `Layer` or `GroupBox` scroll (`scrollable`, `SetScrollSize`)? (Q15) | Put 30 Text lines in each and scroll | Chat log becomes a **pager** (§5.3 fallback) |
| S3 | Can `HTTPRequest:Post` reach `api.anthropic.com` with custom headers? How long until `timedOut`? What's the largest response? (Q8) | One real Claude call (costs a penny or two) and one deliberately slow request | Lower `max_tokens` and default effort `low` |
| S4 | Do `os.time`, `os.date` and `utf8` exist? (Q1) | `print(type(os.time))` and similar | The consent record stores no date. Settings says "date not available". |
| S5 | How does `ui.Text` handle `<`, `>`, `<br>`, `<col=…>`, `•`, `—` and curly quotes? Does it wrap at its width? (Q17, Q11) | Put each in a Text and screenshot it | `lib/textfmt.lua` escapes `<` and `>` and swaps unsupported characters for plain ones |
| S6 | Do `Event.Logic` / `Event.ServerLogic` fire in the lobby? | Count ticks in the lobby | Timers (thinking counter, watchdog) only run in-world, and the setup panel tells the player to log in |
| S7 | What size is the ribbon content layer? | `print(component.width, component.height)` | The launcher shows only a button and one status line |
| S8 | Is the plugin build layer above the game's interfaces, and clickable? | A GroupBox with a button | Use the ribbon content layer as the whole window |
| S9 | Does the popup survive a trip to the lobby or a world hop? Jagex: "components only live for as long as their interface is loaded" | Read a property of the old window after returning to the game; rebuild it if that fails | Rebuild the window from saved state on every return to the game (planned in Step 3 either way) |

Answers go in `plugin/SPIKE_NOTES.md`. If any answer changes the plan, update this file before Step 1.

---

## 3. Steps

Each step is **one pull request** on its own branch, small enough to read line by line. Jagex's AI policy needs you to "personally review and understand" every line, so a step isn't done until you've reviewed it.

- **Claude** writes the code with comments and runs the out-of-game tests.
- **You** review the PR, run the beta check for that step, and report back.

### Step 1 — Skeleton and launcher
- **Build:** `plugin.json`, `main.lua`, `lang/en.lua`, `lib/log.lua`, `ui/launcher.lua`.
- **Jagex APIs:** `Event.ContentLayerReady` (`"hasRibbonIcon": true`), `ui.Button`, `ui.Text`, `log`, `PluginShutdown()`.
- **Done when:** `pon rs-helper` shows the ribbon icon, the icon opens the launcher with an **Open RS Helper** button, and `prl rs-helper` reloads without errors.

### Step 2 — Core libraries and test harness
- **Build:**
  - `lib/json.lua`: encode and decode, including `\uXXXX` escapes and surrogate pairs, with clear error messages.
  - `lib/store.lua`: PersistentDB wrapper, per-character keys (§7), typed get and set.
  - `lib/timer.lua`: `after(seconds, fn)`, `every(seconds, fn)`, `cancel(id)`, driven by the tick event chosen in S6.
  - `tests/fake_api.lua`, `tests/run.lua`, and the first test files.
  - `.github/workflows/plugin-tests.yml`: runs `lua5.4 plugin/tests/run.lua` on every push.
- **Done when:** the tests pass locally and in GitHub Actions.

### Step 3 — Window frame and collapsing
- **Build:** `ui/window.lua` (popup `GroupBox` on `TOPLEVEL_V2__PLUGIN_BUILD_LAYER_TOP`, header with **X**, horizontal `ui.Panel` with the Chat and Explorer panes, ◀ ▶ collapse strips, status bar) and `ui/widgets.lua` (collapsible section helper).
- **Saved state:** `settings.window` = `chatCollapsed`, `explorerCollapsed`, `quickActionsCollapsed`, `setupCollapsed`.
- **Rebuild on return to the game:** on `GameStateChanged` → `GAME`, check the window still works and rebuild it from saved state if not (S9).
- **Done when:** test case 10 passes (each pane collapses, the open one fills the space, both can collapse, and the states survive `prl`), and the window follows a client resize (`Event.WindowSizeChanged`).

### Step 4 — Setup panel and Settings page
- **Build:** `ui/setup_panel.lua` (three steps, collapsible), `ai/consent.lua`, and the Settings page builder used by both the panel and `Event.SettingsLayerReady` (`"hasSettingsIcon": true`).
- **Step 1, web access:** `Plugin.HasPermission(PluginPermissions.httpAccess)`, plus a live update from `Event.OptionalPermissionChanged`.
- **Step 2, consent (§9.2):**
  - Three `ui.Check` boxes, a name field and **I agree**.
  - The typed name is matched against `Player.GetEntity().displayName`.
  - Accepting writes `<char>.consent.claude` and adds an entry to `<char>.consentLog`.
  - Settings shows "Consent given … (notice v1)" with **Withdraw**.
- **Step 3, API key:**
  - A visible `ui.InputField` with `Setup(VISIBLE, NONE, 256)` and the §5.6 warning.
  - **Save** clears the field and shows `••••` plus the last 4 characters.
  - **Forget key** deletes it.
  - **Check key** is wired in Step 5.
- **Model choice (§8.1a):** a `ui.ComboField` for the Claude model, plus a low / medium / high effort `ui.RadioGroup`, saved to `settings.providers.claude`. The model list starts with the built-in choices. In Step 5 it adds the models returned by **Check key**.
- **Done when:** checks 1–4 and 9–10 of §6 pass. The out-of-game consent tests pass (name matching, provider switch, notice version bump, withdraw, log capped at 20).

### Step 5 — HTTP and the Claude adapter
- **`lib/http.lua`:**
  - Refuses to send without `httpAccess`.
  - Builds `HTTPRequest.new(Plugin.urls.<name>, path)`, `AddHeader`s, JSON-encodes the body, then `Post` or `Get`.
  - Runs one request at a time and supports `cancel()`.
  - Has its own 90-second watchdog on top of `request.timedOut` (adjusted after S3).
  - Returns `{ ok, status, json, errorText, timedOut, cancelled }`.
- **`ai/providers/claude.lua`** (exactly §8.1):
  - `buildMessageRequest{ key, model, effort, system, history }` returns path `v1/messages`; headers `x-api-key`, `anthropic-version: 2026-10-21` and `Content-Type`; and a body with `max_tokens = 16000`, top-level `cache_control`, and **no** `temperature` or `thinking`.
  - Model-dependent options come from `ai/providers/models.lua`. `output_config.effort` is sent for the built-in models. `fallbacks = "default"` plus the `anthropic-beta: server-side-fallback-2026-07-01` header is sent only for Sonnet 5.5 and Opus 5.5. A custom model ID gets neither.
  - `parseMessageResponse(status, json)` joins the `text` blocks (skipping `thinking` and `fallback`), handles `stop_reason` `max_tokens` and `refusal`, and maps the error table to player messages.
  - `buildCheckKeyRequest(key)` returns `GET v1/models`. Its result also fills the model picker.
- **`ai/providers/models.lua`:** the built-in model list per provider and what each supports (effort levels, fallbacks).
- **`ai/providers/init.lua`:** the adapter list. Gemini and OpenAI are listed as "coming soon".
- **Wire-up:** **Check key** in the setup panel.
- **Done when:**
  - Out-of-game adapter tests pass, using fixtures in the documented response shapes.
  - In the beta, **Check key** says "Key works" for a good key and "Your Claude API key was rejected" for a bad one.

### Step 6 — Chat
- **`ui/chat_view.lua`:**
  - Message log: one `ui.Text` per message, height from `config.Font.MUSEO_SANS_15PT_REGULAR:GetStringHeightAndLineCount`, scrolling or a pager (per S2), newest 40 kept.
  - Input with `Setup(VISIBLE, NONE, 1000)`, `inputMode = CHAT`; Enter (`SUBMIT`) sends.
  - **Send** and **Stop**, a "Thinking… N s" line, and error lines.
  - The collapsible quick-actions row with **Goal**.
- **`ai/chat.lua`:**
  - Checks, before **every** request: permission, consent and key.
  - Keeps the history window (last 6 turns, text only).
  - Exposes `send`, `cancel` and `clear`.
- **`ai/context.lua`:** builds the player summary from `Player.GetCombatLevel()`, `GetLevelUncapped` / `GetLevelGameplay` for `SkillType` 0–28, and `World.IsMembers()`.
- **`ai/system_prompt.lua`:** the base persona from `agent_instructions.md`, adapted, plus the §8.4 guardrails. Because Build 1 has no wiki yet: "Say when something is general knowledge that may be out of date."
- **`lib/textfmt.lua`:** a minimal Markdown-to-text conversion, plus escaping per S5.
- **The answer footer** is fixed for Build 1: "Build 1 has no wiki lookups yet: treat answers as suggestions."
- **Done when:** checks 5–8 of §6 pass.

### Step 7 — Beta test pass and fixes
- Run the full checklist in §6 in one session (about 45 minutes) and fix what it finds.
- Write `plugin/README-dev.md`: how to install into `dev_plugins`, run the tests, and use the console commands.
- Tag the release `plugin-v0.0.1`.

---

## 4. Files in Build 1

All paths are under `plugin/`. Only `rs-helper/` is ever zipped.

| File | Job | Size (lines, approx.) | Tested by |
|---|---|---|---|
| `rs-helper/plugin.json` | Manifest (below) | 20 | Beta |
| `rs-helper/main.lua` | Loads modules, subscribes events, `PluginShutdown()` | 80 | Beta |
| `rs-helper/lang/en.lua` | Every player-facing string | 80 | — |
| `rs-helper/lib/json.lua` | JSON encode and decode | 220 | `json_test` |
| `rs-helper/lib/store.lua` | PersistentDB wrapper, per-character keys | 110 | `store_test` |
| `rs-helper/lib/http.lua` | Requests, queue, watchdog, permission check | 160 | `http_test` |
| `rs-helper/lib/timer.lua` | Delayed and repeating callbacks | 60 | `timer_test` |
| `rs-helper/lib/log.lua` | Debug logging, off by default | 30 | — |
| `rs-helper/lib/textfmt.lua` | Markdown to game text, escaping | 90 | `textfmt_test` |
| `rs-helper/ai/consent.lua` | Signed consent record and log | 120 | `consent_test` |
| `rs-helper/ai/context.lua` | Player summary | 60 | `context_test` |
| `rs-helper/ai/system_prompt.lua` | Advisor instructions | 50 | Review |
| `rs-helper/ai/chat.lua` | Conversation state, checks, send and cancel | 140 | `chat_test` |
| `rs-helper/ai/providers/init.lua` | Adapter list | 30 | `chat_test` |
| `rs-helper/ai/providers/claude.lua` | Anthropic Messages API mapping | 150 | `claude_test` |
| `rs-helper/ai/providers/models.lua` | Built-in models per provider and their options | 50 | `claude_test` |
| `rs-helper/ui/launcher.lua` | Ribbon content layer | 60 | Beta |
| `rs-helper/ui/window.lua` | Popup frame, panes, collapsing, status bar | 260 | Beta |
| `rs-helper/ui/widgets.lua` | Shared helpers (collapsible section, labelled row) | 120 | Beta |
| `rs-helper/ui/setup_panel.lua` | Web access, consent, key; also used by Settings | 280 | Beta + `consent_test` |
| `rs-helper/ui/chat_view.lua` | Message log, input, Send/Stop, quick actions | 300 | Beta |
| `tests/fake_api.lua` | Stand-ins for the Jagex APIs used above | 200 | — |
| `tests/run.lua` + `tests/*_test.lua` | Test runner and tests | 500 | CI |
| `spike/` | Step 0 only | 150 | Beta |

Total: about 2,000 lines of plugin Lua plus about 700 of tests. Every file gets a header comment explaining its job, and every function gets a comment.

**Manifest for Build 1**

```json
{
    "name": "RS Helper (dev)",
    "version": "0.0.1",
    "contactEmailAddress": "<contact email>",
    "requiredDependencies": {},
    "optionalDependencies": {},
    "requiredPermissions": [],
    "optionalPermissions": [ "httpAccess" ],
    "urls": { "claude": "https://api.anthropic.com/" },
    "hasRibbonIcon": true,
    "hasSettingsIcon": true
}
```

**Data stored in Build 1** (a subset of spec §7): `settings` (provider, `providers.claude = { model, effort }`, `debug`, `window`), `keys.claude`, `<char>.consent`, and `<char>.consentLog`. Chat history stays in memory only, so reloading the plugin clears the conversation. Session memory comes later.

---

## 5. How a chat request flows

```
player presses Enter
  → chat.send(question)
      ✗ no httpAccess        → setup panel, step 1
      ✗ no valid consent     → setup panel, step 2
      ✗ no key               → setup panel, step 3
  → context.playerSummary()            -- "Combat 126; total 2438; Attack 86, Defence 91, …; members world"
  → claude.buildMessageRequest{ system = fixed prompt,
        history = last 6 turns as plain text,
        latest user message = "User Request: <question>\n\nContext:\n<summary>" }
  → http.post("claude", "v1/messages", …)   -- "Thinking… N s" with Stop
  → claude.parseMessageResponse(status, json)
      ok        → textfmt → new Advisor message + footer
      max_tokens→ answer + "The answer was cut off. Ask for a shorter answer."
      refusal   → "Claude declined this question. Try rephrasing it as planning advice."
      error     → message from the §8.1 table (429/500/529 retry up to 2 times)
```

---

## 6. Build 1 beta checklist

Run this in one session, in order:

1. **Fresh install:** `pon rs-helper` with no permission. The ribbon icon opens the launcher, and the window opens with the setup panel at step 1. The Explorer shows its placeholder, and Chat, Explorer and quick actions all collapse.
2. **Web access:** `ppe rs-helper httpAccess`. Step 1 ticks itself without a reload.
3. **Consent:**
   - **I agree** stays disabled until all three boxes are ticked and the name matches.
   - A wrong name is refused. The right one records consent, and Settings shows the date or "date not available".
   - **Withdraw** brings the panel back.
4. **Key:**
   - Paste (or type) the key, then **Save**: the field clears and shows `••••` plus the last 4 characters.
   - **Check key** works for a good key and reports 401 for a bad one.
   - **Forget key** returns to step 3.
5. **Chat:**
   - Ask "What should I train next for slayer?" A thinking counter shows, then the answer appears and wraps.
   - A follow-up ("why?") uses the earlier turns.
   - **Stop** mid-request shows "Stopped".
6. **Models and errors:**
   - Switch to Opus 5.5, then Haiku 5.5, and ask again. Both answer, and the status bar shows the model.
   - A custom model ID that doesn't exist shows "Model not found".
   - A bad key shows the 401 message.
   - Airplane mode (or pulling the network) shows a timeout and the window stays usable.
7. **Guardrail:** "what prayer do I switch to on phase 3 right now?" is declined, with preparation advice offered instead.
8. **Reload:** `prl rs-helper` keeps the collapse states, key and consent, and clears the chat.
9. **Revoke mid-session:** `ppd rs-helper httpAccess` brings back the setup panel, and no request is sent.
10. **Second character:** asks for its own consent.
11. **Crash safety:** sign consent, force-close the client, reopen. Consent is still there.

---

## 7. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Pasting doesn't work (S1) | Typing works. The consent screen already warns that other plugins can see keystrokes. Raise a paste-safe field with the API Council. |
| No scrolling (S2) | Chat log as a pager: one exchange at a time, with Older / Newer / Latest |
| Claude answers slower than the client's HTTP timeout (S3) | Default effort `low`, lower `max_tokens`, and our own watchdog message |
| `<` breaks text rendering (S5) | `textfmt` swaps `<` and `>` for safe look-alikes |
| No clock in Lua (S4) | Consent records the plugin version and notice version without a date |
| Timers don't tick in the lobby (S6) | The chat pane says "Log in to a world to chat" while in the lobby |
| The plugin build layer can't take clicks (S8) | The whole window lives in the ribbon content layer |
| The window dies on a trip to the lobby (S9) | `ui/window.lua` rebuilds itself from `settings.window` on `GameStateChanged` → `GAME`; the chat text is kept in `ai/chat.lua`, so nothing visible is lost |

---

## 8. Not covered here (Build 2 and later)

- Gemini and OpenAI adapters, and a provider switch with per-provider consent.
- The Explorer tabs (0.1), then wiki, citations, source line and Adventurer's Log (0.2), then the full advisor with memory and templates (0.3), as in spec §13.
