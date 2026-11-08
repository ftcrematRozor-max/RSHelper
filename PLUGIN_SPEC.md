# RS Helper — In-Game Plugin Specification

**Status:** Draft v0.1 · 2026-11-08
**Target:** RuneScape 3 official plugin system (Lua 5.4.8, distributed via mod.io)
**Source app:** `app.py` (Streamlit), `agent_instructions.md`, `account_profiles_archive.md`

> Everything in this spec comes from Jagex's official developer documentation
> (developer.runescape.com, read 2026-11-08) and from this repository's code.
> Jagex's AI policy allows feeding its API docs and their examples to AI tools.
> It does **not** allow feeding in other developers' plugins, so this spec
> deliberately never looks at any third-party plugin code.

**Contents:** 0 Assumptions · 1 Goals · 2 Jagex rules · 3 Architecture · 4 Manifest · 5 UI · 6 Module-by-module port · 7 Data model · 8 AI integration · 9 Privacy · 10 Endpoints · 11 Testing (beta world, harness) · 12 Submission checklist · 13 Milestones · 14 Open questions · A Legacy app & RuneMetrics · B Docs used

---

## 0. Assumptions and decisions already made

| # | Decision | Notes |
|---|----------|-------|
| A1 | `httpAccess` to the Claude (Anthropic), Gemini and OpenAI APIs is assumed to be approvable. | Confirm with the Plugin Moderator at submission time. |
| A2 | The plugin is a **rewrite**, not a translation of `app.py`. | Jagex rejects "code output from language transcoding processes". |
| A3 | All code is hand-reviewed by the repo owner before submission. | Required by the AI Policy ("AI-assisted code is acceptable provided you personally review and understand it"). |
| A4 | The plugin is the product. The desktop app is **legacy**: kept in the repo as a reference for the port, not maintained. | Owner decision (review, 2026-11-08). It stops loading live stats when RuneMetrics shuts down on 10 Nov 2026. Appendix A records the fix in case it's ever wanted. |
| A5 | Bring-your-own-key: each player enters their own Claude (Anthropic), Gemini or OpenAI key. | The plugin has no server of its own. Claude added per owner review (2026-11-08). |

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
| "Features that provide interpreted or actionable gameplay recommendations may be subject to stricter review." | Plugin guidelines → Subject to review | The AI advisor will get a stricter review. Two kinds of content are kept apart (§8.3, §8.4). **Wiki-sourced information** (requirements, mechanics, drops, item stats) is public, player-known information, which the guidelines allow, so it's presented as fact and guidance, with a citation. **The advisor's own recommendations** (what to do next) are labelled as suggestions and stay planning and preparation only. The listing explains both. (Owner decision, review 2026-11-08.) |
| Prohibited: "Automatic prayer switching/ability recommendations or execution." | Guidelines → Prohibited | The system prompt forbids live combat calls (§8.4). The Bosses tab shows preparation only (levels, gear, wiki links). |
| Prohibited: "Plugins cannot export any information about other players." Subject to review: "Obtaining any information about other players." | Guidelines | Only the logged-in character is ever read or sent. The desktop app's multi-account switcher is not ported. |
| Subject to review: "Any plugin which requests a permission." | Guidelines | `httpAccess` is **optional**. Without it the plugin still works offline (Explorer, To-Do, Profile from the client). |
| Subject to review: "Containing custom resources like images or sounds." | Guidelines | v1 ships no custom images or sounds and uses built-in game sprites only. |
| "Plugin code which is unnecessarily difficult to follow will result in rejection … transcoding … unvetted AI generation." | Guidelines → AI Policy | Small files, one job each, comments on every function, no clever tricks. The owner reviews every line. |
| "Specifying malformed URLs or URL shortener/redirect addresses will cause your plugin to be rejected." | HTTPRequest | Exact HTTPS base URLs only (§4). |
| Data sent outside the UK/EEA (e.g. USA) is "Case 3". | Submission process, UK adequacy | Anthropic, Google and OpenAI are US services, so: privacy notice, public contact email, and Jagex's adequacy form (§9). |
| "Plugins should support all of the major platforms … Windows, Linux, and Mac." | Submission process | No OS-specific code or paths. |
| "If you want to include lots of logging then it should be toggleable, and off by default." | Good practice | A `debug` switch in Settings, off by default. |
| Localisation: "Store all of your different text strings in a table structure in separate files for each language." | Good practice | All UI text lives in `lang/en.lua` from day one. |
| "Try not make a plugin that does pretty much the same as another plugin." | Good practice | Don't rebuild step-by-step quest guidance. Quest Helper already does that. Our Quests tab lists what's *available* and links to the wiki. |

---

## 3. Architecture

### 3.1 Folder layout

The repo keeps the legacy desktop app at the root as a reference (A4). The plugin lives in its own folder, and **only** `plugin/rs-helper/` is zipped for mod.io.

```
plugin/
  rs-helper/                    <- zipped for submission (main.lua + plugin.json at top level)
    plugin.json                 manifest (§4)
    main.lua                    entry point: loads modules, subscribes events, PluginShutdown()
    lang/en.lua                 every user-facing string
    lib/json.lua                small hand-written JSON encode/decode
    lib/store.lua               PersistentDB wrapper: character key, typed get/set, defaults
    lib/http.lua                HTTPRequest wrapper: permission check, User-Agent, JSON, errors, one queue
    lib/timer.lua               "run this later" helper driven by Event.ServerLogic (~600 ms ticks)
    lib/textfmt.lua             AI Markdown -> game text tags (<col>, <br>), word limits
    lib/log.lua                 debug logging, off by default
    data/bosses.lua             boss catalog (ported from RS3_BOSS_CATALOG)
    data/items.lua              major-items catalog (ported from MAJOR_ITEMS_CATALOG)
    data/prompts.lua            prompt templates (quest, boss, slayer, goal, to-do)
    game/profile.lua            live stats from the Player API
    game/quests.lua             quest status and requirements from config.Quest
    game/items.lua              owned-item detection from inventories
    web/wiki.lua                wiki search, extract, category lists, title check
    web/advlog.lua              Adventurer's Log: own events and quest eligibility
    web/ge.lua                  GE prices
    ai/system_prompt.lua        the advisor's base instructions (readable by moderators)
    ai/context.lua              builds the context block (§8.2)
    ai/providers.lua            Claude / Gemini / OpenAI request and response mapping
    ai/chat.lua                 conversation state, send/cancel, session memory
    ui/window.lua               popup shell: header, Chat | Explorer split, tab bar
    ui/chat_view.lua            chat pane
    ui/explorer/*.lua           profile, quests, bosses, items, todo, wiki, settings
    ui/widgets.lua              shared rows, chips, badges
  tests/                        out-of-game tests with fake Jagex APIs (never zipped, §11.3)
  tools/                        dev-only helpers (never zipped)
  README-dev.md                 how to run in the beta world (never zipped)
```

Rules: one job per file, under ~300 lines each, a header comment explaining the file, and a comment on every function. No metatable tricks, no code generation, no minified code.

### 3.2 Data flow

```
 game client ──(Player, config.Quest, Inventory, events)──► game/*  ─┐
                                                                    ├─► ai/context ─► ai/providers ─► Claude/Gemini/OpenAI
 runescape.wiki / Adventurer's Log / GE ──(HTTPRequest)──► web/* ───┤                     │
                                                                    │                     ▼
 PersistentDB ◄──► lib/store ◄──► To-Do, favourites, items, memory ─┘           lib/textfmt ─► ui/chat_view
                                                                     ui/explorer/* ◄── game/*, web/*, store
```

### 3.3 Lifecycle and events

| When | Event / hook | What happens |
|---|---|---|
| Plugin enabled | `main.lua` runs | Load settings. Subscribe events. If `Player.IsAvailable()`, build the profile now. |
| Ribbon icon clicked | `Event.ContentLayerReady` (`component`) | Build the Chat + Explorer UI inside the provided layer (§5). The layer is "cleared of pre-existing elements immediately before this event is called", so rebuild from saved state each time. |
| Launcher button or hotkey | `ui.Hook.ONBUTTONPRESSED` / `Event.KeyDown` | Show the popup on the plugin build layer, creating it the first time (§5.1). |
| Plugin Hub → Settings icon | `Event.SettingsLayerReady` (`component`) | Build the Settings page (§5.4). |
| Login / world hop / lobby | `Event.GameStateChanged` (`newState`: `GAME` = 30, `LOBBY` = 20 …) | On `GAME`: refresh profile and quests, and load this character's data. On leaving `GAME`: save a snapshot. |
| XP gained | `Event.SkillTransmit` (`skill`, `newXP`, `newGameplayLevel` …) | Update that skill in the profile cache. Re-mark the Profile tab dirty. |
| Quest progress | `Event.VarTransmit` (`var`, `newValue`) | If `var` is one of the quests' `masterQuestVars[1].varPlayer`, refresh that quest. |
| Inventory seen / changed | `Event.InventoryAdded` / `InventoryUpdated` | Re-check owned major items (§6.8). |
| Permission granted / revoked | `Event.OptionalPermissionChanged` | Enable or disable the online features live. |
| Every ~600 ms | `Event.ServerLogic` | Drive `lib/timer` (retries, debounce, idle timeout). |
| Disabled / client closes | `PluginShutdown()` (global function) | Final save. Data is also saved on every change, because a crash skips this hook. |

---

## 4. Manifest (`plugin.json`)

```json
{
    "name": "RS Helper",
    "version": "0.1.0",
    "contactEmailAddress": "<public contact email, not your mod.io login>",
    "requiredDependencies": {},
    "optionalDependencies": {},
    "requiredPermissions": [],
    "optionalPermissions": [ "httpAccess" ],
    "urls": {
        "wiki":   "https://runescape.wiki/",
        "advlog": "https://secure.runescape.com/m=adventurers-log/",
        "ge":     "https://api.weirdgloop.org/",
        "claude": "https://api.anthropic.com/",
        "gemini": "https://generativelanguage.googleapis.com/",
        "openai": "https://api.openai.com/"
    },
    "hasRibbonIcon": true,
    "hasSettingsIcon": true
}
```

- `httpAccess` is **optional**: Jagex recommends that "unless your plugin won't work at all without a specific permission". The plugin checks `Plugin.HasPermission(PluginPermissions.httpAccess)` before any network feature. Until web access is allowed, the data notice is accepted and a key is saved, the chat pane is **replaced by the Set up the advisor panel** (§5.3). The Explorer works regardless. (Owner review, 2026-11-08.)
- `chatAccess` and `trackingAccess` are **not** requested. Nothing needs them, and every permission adds review.
- v0.1 ships with no `urls` and no permissions at all (§13). Each URL is added in the milestone that first uses it.

---

## 5. User interface: the popup Chat + Explorer window

### 5.1 Where the window lives and how it opens

Jagex: "Since plugins can't create new interfaces, they must instead use components in the appropriate interface as a parent." Two hosts are available:

| Host | API | Used for |
|---|---|---|
| **Ribbon content layer**: the plugin's page inside the game's floating *Plugins* window | `Event.ContentLayerReady` → `component`, with `"hasRibbonIcon": true` | The **launcher**: an "Open RS Helper" button, a one-line status (profile loaded / key set / permission), and the three newest open To-Do items. |
| **Plugin build layer**: a layer "on the game window that appears above most game and interface components" | `ui.Interfaces:GetComponent(id.Component.TOPLEVEL_V2__PLUGIN_BUILD_LAYER_TOP)` | The **popup** itself: a `ui.GroupBox` (stylesheet `id.StyleSheet.DEFAULT`), the same pattern as Jagex's UI tutorial. |
| **Settings layer**: the Settings icon in Plugin Hub → Manage | `Event.SettingsLayerReady` → `component`, with `"hasSettingsIcon": true` | The same Settings page as the popup's ⚙ tab (one builder function used in both places). |

**Opening and closing**
- Open: the launcher button, or an optional hotkey (`Event.KeyDown` with a modifier, default **Ctrl+Shift+H**, configurable or off, §14 Q16).
- Close: the **X** button in the popup header (`hidden = true`). Components are hidden and reused, not destroyed and rebuilt, so reopening is instant and keeps chat scroll and tab state.
- Don't add minimenu (right-click) entries. "Input or menu customisation" is subject to review, and the plugin doesn't need them.

**Position and size**
- Default size: 46% × 62% of the game window, clamped to at least 560 × 380 units. Placed at the right-centre. Uses `SetSize(w, h, pctW, pctH)` and `SetPos(x, y, parentPct, selfPct)` so it follows client resizes. Also listen to `Event.WindowSizeChanged`.
- **Size presets** (Small / Medium / Large) in the header menu. Jagex documents no resize handle.
- **Moving:** drag the header. The pieces are `dragConfig`, `ONDRAG` / `ONDRAGCOMPLETE` and `Mouse.GetPosition()`, but Jagex documents no full window-drag pattern (§14 Q15). Fallback: a **Position** preset (left / centre / right). The position is saved in `settings`.
- **Small screens** (or the Small preset): opening one pane collapses the other automatically, using the collapse controls in §5.2.

### 5.2 Layout

```
┌─ RS Helper ───────────────────────────────────────── [Size ▾] [X] ┐
│ ◀ CHAT                              │ EXPLORER ▶                  │
│ ┌─────────────────────────────────┐ │ Profile Quests Bosses Items │
│ │ You  How do I unlock Rigour?    │ │ To-Do  Wiki  ⚙              │
│ │ Advisor                         │ │ ┌─────────────────────────┐ │
│ │ • Needs 74 Dungeoneering...     │ │ │                         │ │
│ │ Source: RuneScape Wiki          │ │ │  (active tab content)   │ │
│ │ [Wiki: Rigour] [Wiki: Daemon…]  │ │ │                         │ │
│ │                         ▲ ▼ ⤓   │ │ │                         │ │
│ └─────────────────────────────────┘ │ │                         │ │
│ Quick actions ▾                     │ │                         │ │
│ [Goal] [Quest] [Boss] [Slayer] [★]  │ │                         │ │
│ ┌───────────────────────────┐[Send] │ └─────────────────────────┘ │
│ │ Ask the advisor…          │[Stop] │ [Ask about this ▸]          │
│ └───────────────────────────┘       │                             │
├─────────────────────────────────────┴─────────────────────────────┤
│ Claude · claude-sonnet-5-5 │ Sends: stats, 3 goals, Wiki "Rigour" │
└───────────────────────────────────────────────────────────────────┘
```

**Collapsing** (owner review, 2026-11-08)
- **Both panes collapse.** ◀ in the Chat header and ▶ in the Explorer header shrink that pane to a narrow strip showing its name and an expand arrow. The other pane **expands to fill** the window: the outer `ui.Panel` recomputes the percentage widths.
- **Both collapsed** leaves only the header and status bar, so the window can stay on screen out of the way.
- **Quick actions are part of the chat pane** and collapse on their own: "Quick actions ▾" hides the button row, and the chat log grows into the space.
- **The setup panel** (§5.3) collapses to a single line: "Advisor not set up · Set up ▸".
- Every collapse state is saved in `settings.window` (§7), so the window reopens the way the player left it.

- **Outer structure:** a horizontal `ui.Panel` (`isVertical = false`). With both panes open, Chat takes 55% and Explorer 45%. A collapsed pane becomes a fixed strip of about 28 units, and the open pane takes the rest. Nested vertical Panels go inside each.
- **Explorer tabs:** a `ui.PagedLayer` with one `PagedLayerHeader` (stylesheet `PAGED_LAYER_DEFAULT`). The pages are Profile, Quests, Bosses, Items, To-Do, Wiki, and ⚙ Settings. Jagex: "Components are associated with the currently active page when created", so each tab is built after switching `activePage` to it.
- **Ask about this ▸** (bottom of the Explorer) sends whatever is selected (a quest, boss, wiki page or To-Do item) to the Chat input using the matching template. This is the main link between the two halves.
- **Status bar:** provider and model, plus a one-line list of the context that *will* be sent. Clicking it opens **What will be sent**, showing the full context text, for transparency with players and moderators.

### 5.3 Chat pane

| Part | Component | Behaviour |
|---|---|---|
| Message log | A `ui.Layer` holding one `ui.Text` per message (`maxLines = 0`) | Each message's height comes from `config.Font.<font>:GetStringHeightAndLineCount(text, wrapWidth, lineSpacing)`. Messages are stacked top to bottom, and `SetScrollSize` / `SetScrollPos` are driven by `ONSCROLLWHEEL` plus the ▲ ▼ ⤓ (jump to latest) buttons. Only the newest 40 messages are kept as components (ID budget, §5.7). |
| Log fallback | — | If layer scrolling turns out unsupported (§14 Q15): a **pager** showing one exchange at a time, with ◀ Older / Newer ▶ / Latest. |
| Speaker label | `ui.Text`, coloured | "You" or "Advisor". Colour plus a word, so it isn't colour alone. |
| Citation chips | `ui.Button` row (`BUTTON_CORNERED_NEUTRAL`) under an answer | One per wiki link: `Wiki: <Title>`, with a `⚠` prefix if the page is missing. A click opens the Explorer's Wiki tab on that page. Above the chips, a source line: **"Source: RuneScape Wiki (CC BY-NC-SA 3.0)"** when at least one cited page exists, or **"No wiki source: treat this as a suggestion"** when none does. |
| Quick actions | `ui.Button` row inside the chat pane, under a "Quick actions ▾" toggle | Goal, Quest (opens Quests), Boss (opens Bosses), Slayer (opens the Slayer form), ★ Saved prompts (a `ui.List` dropdown). Each **fills** the input and never sends. The row collapses on its own (§5.2). |
| Input | `ui.InputField`, `Setup(VISIBLE, NONE, 1000)`, `inputMode = CHAT`, `emptyText = "Ask the advisor…"` | Enter submits (`ONCONTENTCHANGED` with reason `SUBMIT`). Escape doesn't send (`SUBMIT_ON_ESCAPE` is ignored). |
| Send / Stop | `ui.Button` | Send is disabled while a request is running. Stop calls `HTTPRequest:Cancel()`. |
| States | `ui.Text` in the log | "Thinking…" with a counter in seconds (updated on `ServerLogic`), plus errors in plain words: "Your API key was rejected", "Out of credit or rate-limited, try again in a minute", "No response after 60 s". |
| Setup panel | Replaces the **whole chat pane** until setup is complete; collapsible | See "Set up the advisor" below. |

**Set up the advisor** (replaces the chat pane; owner review, 2026-11-08)

```
│ ◀ SET UP THE ADVISOR             ▾  │
│ The advisor needs three things.     │
│ The Explorer works without them.    │
│                                     │
│ ✓ 1 Web access    Allowed           │
│ ○ 2 Consent       [Read and sign]   │
│ ○ 3 API key       (●) Claude        │
│                   ( ) Gemini        │
│                   ( ) OpenAI        │
│   [Paste your key…        ] [Save]  │
│   [Check key]                       │
```

1. **Web access** shows the result of `Plugin.HasPermission(PluginPermissions.httpAccess)`. Jagex documents no Lua call that asks for a permission (only `HasPermission` and the `OptionalPermissionChanged` event), so this step explains where to allow it: "Plugin Hub → Manage → RS Helper → allow Web access". It ticks itself when `Event.OptionalPermissionChanged` reports `httpAccess` enabled (§14 Q18).
2. **Consent:** the signed, recorded consent in §9.2, naming the company for the chosen provider (Anthropic, Google or OpenAI). It stays greyed out until web access is allowed, because nothing is sent before that. The key step unlocks only after consent is signed.
3. **API key:** provider choice (`ui.RadioGroup`) and a visible key field (§5.6). **Save** stores the key and shows only `••••` plus its last 4 characters. **Check key** calls the provider's free model-list endpoint, which uses no tokens: Claude `GET v1/models` (headers `x-api-key` and `anthropic-version`), Gemini `GET v1beta/models` (`x-goog-api-key`), OpenAI `GET v1/models` (`Authorization: Bearer`). It reports "Key works" or the error message from §8.1.

When all three are done, the panel closes and the chat pane appears. Settings (⚙) keeps the same three controls for later changes. If permission is revoked later, or the key is forgotten, the panel comes back.

### 5.4 Explorer tabs

| Tab | Content | Main components |
|---|---|---|
| **Profile** | Header: name, combat level, total level and total XP, members/F2P world. A 29-skill grid showing the level (and the boosted level when it differs). Below: "Recent activity" (Adventurer's Log, online only, 10-minute cache). | `ui.Grid` `SetColumnRows(4, 8)`, `ui.Text` cells, `ui.Sprite` skill icons if suitable built-in sprite IDs exist |
| **Quests** | Filter (Can start / In progress / Done / Blocked / All), a search box, and a list with QP and difficulty. The detail area shows missing requirements and buttons: Ask about this, Open on wiki. | `ui.RadioGroup` (toggle buttons), `ui.InputField`, `ui.List` (`entryHeight` 22, fixed), `ui.Text` |
| **Bosses** | Tier filter, a favourites-first list with a readiness word (Ready / Borderline / Under-levelled) and recommended combat level. Detail: ★ Favourite toggle, Plan this boss. A Slayer card opens the Slayer form (monster combo, count, master). | `ui.List`, `ui.Check`, `ui.ComboField`, `ui.InputField` (`NUMERIC`) |
| **Items** | 5 categories × catalog items, each with an item icon, a tick, and a "Seen in bank 3 Nov" note. Progress "17 / 35". | `ui.Check` + `ui.Sprite:SetAssociatedObject(objectID)` (item icon by object ID) |
| **To-Do** | Add row (text, priority, category), filters, and task rows: tick, text, Ask, Edit, Delete (Delete asks to confirm). Suggest my next goals. | `ui.InputField`, `ui.List` dropdowns, `ui.Check`, `ui.Button` |
| **Wiki** | Search box → result list → reader (title, intro text, Ask about this, related-link chips). Quick links. A Prices box: item name(s) → price and daily volume. | `ui.InputField`, `ui.List`, `ui.Text`, `ui.Button` |
| **⚙ Settings** | Provider (Claude / Gemini / OpenAI), and **for each provider its own model and effort** (§8.1a), key status (`set ••••abcd` / not set) with Enter key and Forget key, custom instructions (2,000 characters), answer length, hotkey, debug logging, Forget memory, Delete all my data (confirmation). | `ui.RadioGroup`, `ui.InputField`, `ui.Slider`, `ui.Check`, `ui.Button` |

### 5.5 Text, images and colour

- **Font:** `id.Font.MUSEO_SANS_15PT_REGULAR`, the only font Jagex's docs name. Text without a font is invisible.
- **Line breaks:** `<br>` works in `ui.Text` (Jagex's database tutorial uses it). Colour tags (`<col=FF0000>`) are documented for chat messages. Whether they work in `ui.Text` is unverified (§14 Q17), so colour whole Text components with `colour` instead.
- **AI answers** are converted by `lib/textfmt.lua`: `#` headings become their own line in the header colour; `-`/`*` bullets become `•`; `**bold**` loses its markers; tables become "Column: value" lines; links become citation chips (§5.3). Anything else stays plain text.
- **No emoji.** The game font may not have them (§14 Q11). The app's 🟢🟡🔴 badges become coloured words.
- **Images:**
  - Item icons by object ID (`SetAssociatedObject`) are fine and need no custom resources.
  - No web images: nothing turns downloaded bytes into a sprite.
  - Bundled PNGs (≤ 1024×1024) are possible but count as "custom resources", which are subject to review. v1 uses none.

### 5.6 Input and keyboard

- **API keys:** a field set to `HIDDEN` or `SHOW_LAST` becomes "restricted" and **the plugin then reads its content as an empty string**. So the key is typed in a **visible** field marked "Paste your key", saved on Enter, then the field is cleared and the key shown only as `••••` plus its last 4 characters. Warn: "Don't do this while streaming." The field also says what §9.3 confirms: **other plugins can see keystrokes while you type**, so paste the key rather than typing it if pasting works (§14 Q14).
- **Pasting** isn't documented for `InputField` (§14 Q14). Typing a 40–160-character key by hand would be painful, so check this in the beta first.
- **Hotkey:** Jagex's key events are read-only, so the plugin can't stop the game from also seeing the key. Use a modifier combination the game doesn't use by default, and let players change or turn it off.
- `Keyboard.IsAvailable()` is false on mobile. Hide the hotkey setting there.

### 5.7 Component IDs and performance

- ID limits (Jagex `ui/index`): category IDs 0–235. Dynamic IDs go up to 4096 under category 0, and up to 235 under other categories. Give each area its own category: 1 header, 2 chat log, 3 chat controls, 4–10 the Explorer tabs, 11 dialogs.
- Build each Explorer tab the **first time** it's opened, then update it in place. Lists use `SetEntries`, not rebuilt components.
- Prefer `SetPos` / `SetSize` over separate setters ("less layout operations").
- Use `PluginLogic` / `ServerLogic` for timers, not `ONTIMER`.
- Stylesheets: `DEFAULT` (group boxes), `BUTTON_DEFAULT` / `BUTTON_CORNERED_NEUTRAL`, `INPUT_DEFAULT`, `CHECKBOX_DEFAULT`, `RADIO_DEFAULT`, `DROPDOWN_DEFAULT`, `COMBO_DEFAULT`, `PAGED_LAYER_DEFAULT`, `SLIDER_DEFAULT`.

---

## 6. Module-by-module port

Each subsection gives: **From** (the `app.py` code), **To** (the plugin file), **How** (the Jagex API used), and **Changes** (what's dropped or fixed).

### 6.1 Settings and persistence
- **From:** `load_settings` / `save_settings` (41–79), `~/.rshelper/settings.json`.
- **To:** `lib/store.lua`.
- **How:** `PersistentDB:GetStructuredData` / `SetStructuredData`, plus the typed string and bool helpers. Keys as in §7.
- **Changes:** per-character keys, and each value saved on its own (no nine-argument `save_settings`).

### 6.2 Player profile
- **From:** `fetch_runemetrics_profile` (323–399), `fetch_player_profile` (411–429), `extract_player_cb_level` (302–312), the archive (98–135), the Profile tab (1161–1218).
- **To:** `game/profile.lua` + `ui/explorer/profile.lua`.
- **How:**
  - `Player.IsAvailable()`, then:
  - name: `Player.GetEntity().displayName`
  - combat: `Player.GetCombatLevel()`
  - per skill, for every `SkillType` 0–28: `Player.GetLevelUncapped(s)`, `Player.GetXPUncapped(s)`, and `Player.GetLevelGameplay(s)` (boosted/drained)
  - members world: `World.IsMembers()`
  - total level and total XP are sums (the API has no total function)
  - recent activity (optional, online): `web/advlog.lua` → `api/v1/playerEvents/<own name>`, cached 10 min
- **Changes:**
  - Removes the whole RuneMetrics → archive → Playwright chain, so the data is always live.
  - Removes the default combat level of 100, which made the boss indicators meaningless.
  - The profile is a **table**, not a text blob, so the UI no longer parses its own text with regexes.
  - Rank is dropped: it isn't in the client API, and it's of little use to the advisor.

### 6.3 Accounts and login gate
- **From:** sidebar accounts (1032–1076), login form (952–976).
- **To:** removed.
- **How:** the logged-in character is the account. Data switches automatically on `GameStateChanged` → `GAME`.
- **Changes:** there's no multi-account lookup, because "obtaining any information about other players" is subject to review and "exporting" it is prohibited. There's no login gate: everything except Chat works without an API key, and Chat shows "Add your API key in Settings".

### 6.4 Quests
- **From:** `fetch_rs_quests` (447–462), `extract_completed_quests` / `get_available_quests` (488–524), `quest_dialog` (864–872).
- **To:** `game/quests.lua` + `ui/explorer/quests.lua`.
- **How:**
  - Each quest is a `config.Quest` object with `name`, `questPoints`, `difficulty`, `isMembers`, `hasStartedQuest`, `hasFinishedQuest`, `canStartQuest`, `preReqSkills` (+ `completedPreReqSkills`), `preReqQuests` (+ `completedPreReqQuests`), and `preReqQuestPoints`.
  - **Finding all quest IDs:** the client API has no "list all quests" call. Plan:
    1. **Online:** the Adventurer's Log `playerData?includeQuests=true` returns every quest keyed by its internal numeric ID, which can be passed to `config.Quest.FromID(id)`. Check in the beta that the IDs match (§14 Q2).
    2. **Offline fallback:** a quest-ID list in `data/quest_ids.lua`, produced in the dev client by a `tools/` script and reviewed by hand.
  - QP: the advlog `qp` value when online, otherwise the sum of `questPoints` over finished quests (Jagex warns this can differ slightly).
- **Explorer view:** filters for *Can start now* / *In progress* / *Completed* / *Blocked*. A blocked quest lists its missing requirements ("Needs 70 Agility (you: 64)", "Needs quest: Plague's End"). Buttons: **Ask the advisor** and **Open on wiki** (reader tab).
- **Changes:**
  - "Available" now means `canStartQuest` and not started, using the game's real requirement check. The app only checked "not completed", and had a case bug.
  - The prompt template drops "puzzle solutions" and "step-by-step walkthrough", because the guidelines bar trivialising "intended gameplay challenge". It becomes: "requirements, preparation, recommended items and the wiki quick guide link". Step-by-step help is Quest Helper's job (good-practice rule on duplicates).

### 6.5 Bosses
- **From:** `RS3_BOSS_CATALOG` (137–170), `fetch_rs_bosses` (464–486), `get_combat_indicator` (314–321), `boss_dialog` (875–926), `get_favorite_bosses_memory` (590–594).
- **To:** `data/bosses.lua`, `ui/explorer/bosses.lua`.
- **How:**
  - The 32-entry catalog is ported as plain data: `{ name, wikiTitle, recCombat, tier }`.
  - The wiki list `Category:Bosses` is merged in as "no recommendation" entries.
  - Player combat level comes from `Player.GetCombatLevel()`.
  - Optional: `config.NPC.<NAME>.visibleCombatLevel` for the boss's own level, where the NPC config name is known.
- **Readiness badge:** same thresholds as the app: ready if `cb ≥ rec`, borderline if `cb ≥ rec − 15`, otherwise under-levelled. Colour plus a word, never colour alone.
- **Changes:**
  - Wiki-merged bosses no longer get a made-up `rec_cb` of 110.
  - The global catalog is no longer mutated.
  - The template keeps preparation (gear, inventory, levels, a summary of mechanics from the wiki) and must not ask for live in-fight instructions.
  - Boss images: no web images (§5.5). The window shows the name and tier text, plus an NPC model only if the Model component supports it (§14 Q10).

### 6.6 Wiki search, reader and citations
- **From:** `fetch_rs_wiki_info` (613–626), the Wiki tab (1220–1277), `update_wiki_cache_background` (183–240), `verify_wiki_urls` (673–701), `format_wiki_links_source_block` (262–290).
- **To:** `web/wiki.lua`, `ui/explorer/wiki.lua`.
- **How:** `HTTPRequest.new(Plugin.urls.wiki, path):Get(cb)` with:
  - search: `api.php?action=query&format=json&formatversion=2&list=search&srlimit=10&srsearch=<q>`
  - extract: `…&prop=extracts&exintro=1&explaintext=1&redirects=1&titles=<t>`, max 3,000 chars
  - existence check: `…&redirects=1&titles=A|B|…`, up to 50 at once (§8.3)
  - category lists: `…&list=categorymembers&cmtitle=<cat>&cmlimit=500&cmcontinue=…`
- **Reader:** title, intro text, an attribution line ("From the RuneScape Wiki · CC BY-NC-SA 3.0", required by the wiki's licence), **Ask the advisor about this page** (passes the extract into the chat context), and links within the page as chips. The five Quick Links (Quests, Money making, Skill guides, Grand Exchange, D&Ds) open in the reader.
- **Changes:**
  - **Dropped:** the 8.8 MB title cache, the weekly ~824-request crawl, the background thread, and the 3,000-URL context block.
  - Citation checks are one batched request per answer.
  - Requests always have a callback timeout path (`request.timedOut`). The app had no timeouts on four wiki calls.

### 6.7 Slayer
- **From:** `fetch_slayer_monsters` (431–445), `slayer_dialog` (928–938).
- **To:** a **Slayer** card on the Bosses tab, which opens a small form: monster (list from `Category:Slayer_assignments`), count (default 150), and master (the app's 8 names).
- **How:** form → `data/prompts.lua` slayer template → Chat.
- **Changes:** none functional. The Jagex docs don't document reading the current task (§14 Q6), so it stays manual.

### 6.8 Major items tracker
- **From:** `MAJOR_ITEMS_CATALOG` (526–572), `get_owned_items_memory` (574–581), Items tab (1279–1316).
- **To:** `data/items.lua`, `game/items.lua`, `ui/explorer/items.lua`.
- **How:**
  - 35 items in 5 categories, ported as data: `{ id, name, objConfig }`, where `objConfig` is the `config.Obj` name found in the dev client (`pan Obj`).
  - **Auto-detect:** when `InventoryAdded` / `InventoryUpdated` fires for the backpack (`config.Inv.INV`), worn equipment, or the bank (`config.Inv.BANK`, only while the server has sent it), call `inv:GetTotal(config.Obj.X) > 0`. Mark the item **Seen** with a date.
  - Manual ticks stay, for items kept elsewhere (POH, cape rack, etc.).
- **Changes:**
  - Emoji category labels become plain text (the game font may not have emoji, §14 Q11).
  - The progress counter only counts catalog IDs (it went over 100% in the app).
  - Item icons come from the game by object ID (`ui.Sprite:SetAssociatedObject`), with no web images.

### 6.9 Grand Exchange prices
- **From:** `fetch_ge_prices` (628–642), `extract_ge_context_from_prompt` (644–671), GE expander (1244–1261).
- **To:** `web/ge.lua`, plus a **Prices** box on the Wiki tab.
- **How:**
  - The client API has **no price lookup**. `GrandExchange` only reads the player's own offers, and `ObjType.cost` isn't documented as a GE price.
  - So keep the app's source: `HTTPRequest.new(Plugin.urls.ge, "exchange/history/rs/latest?name=A|B")`. Only item names are sent.
  - `ObjType.isStockmarket` tells whether an item is tradeable at all.
- **Changes:**
  - Use exact item names, from catalogs or `ObjType.name`, instead of the app's lowercase keyword list. That list included "herblore", which isn't an item, and lowercase names may not match.
  - Cache prices for 5 minutes (the app used 300 s).
  - Guard against error payloads (the app's GE tab could crash on one).

### 6.10 To-Do and goals
- **From:** `get_todo_memory` (583–588), To-Do panel (1637–1684), `roo_task.md`.
- **To:** `ui/explorer/todo.lua` + `<char>.todo`.
- **Features:** add (text, priority, category), tick done, edit text (planned in `roo_task.md` but never built), delete with confirmation, filter by status and category, **Ask the advisor** per task, and **Suggest my next goals** (fills the chat box with the app's template).
- **Changes:** real categories, counter IDs, and priority included in the AI context.

### 6.11 Prompt templates and saved prompts
- **From:** Goal / Quest / Boss / Slayer / Custom buttons (1440–1492), `custom_prompt_dialog` (940–950).
- **To:** `data/prompts.lua` + quick-action chips above the chat input (§5.2).
- **Changes:** templates **fill** the input and never auto-send, the same as the app. Saved prompts move to `<char>.prompts`.

### 6.12 System prompt and custom instructions
- **From:** `load_agent_instructions` (81–96), `agent_instructions.md`, the instructions editor (1116–1135).
- **To:** `ai/system_prompt.lua`, plus a Settings field for custom instructions.
- **Changes:** the base prompt is fixed in code, so a moderator can read exactly what the advisor is told, and it includes the guideline guardrails (§8.4). Players can only *append* custom instructions. The character name is no longer inserted into the prompt.

### 6.13 LLM providers
- **From:** Gemini and OpenAI SDK calls (1572–1624). Claude is a new third provider (A5).
- **To:** `ai/providers.lua` (§8.1).
- **Changes:**
  - Raw HTTPS instead of SDKs.
  - Retries on HTTP 503 and 429: up to 2, at 2 s and then 5 s, using `lib/timer` (no `sleep` is available).
  - The default provider is whichever key is present; with several keys, the player picks in Settings (the app defaulted to Gemini even when only an OpenAI key was set).
  - The last 6 turns of history are sent (the app sent none).

### 6.14 Session memory and logs
- **From:** `load_past_session_memories` (596–611), `log_interaction` (991–1014), the log viewer (1092–1114).
- **To:** `ai/chat.lua`, `<char>.memory` (§8.5).
- **Changes:**
  - Full transcripts are **not** stored, for privacy and storage size. Only 3 short summaries are kept.
  - "Clear chat" empties the current conversation. "Forget memory" in Settings deletes `<char>.memory`.

### 6.15 Dropped entirely

| App feature | Lines | Why |
|---|---|---|
| Image upload, paste and multimodal | 765–859, 1343–1364, 1418–1439, 1478–1530 | No file or clipboard API, and no screenshot API |
| RuneApps Playwright scraper | 401–409 | Not possible in Lua. Jagex best practice: "Avoid scraping HTML pages". |
| Background wiki crawler + 8.8 MB cache | 172–245 | Replaced by on-demand calls (§6.6) |
| Remote images / HEAD checks | 293–300, 902–906, 1298–1302 | HTTP returns text; images come from game sprites or resources |
| Custom CSS / JS | 709–859 | Engine UI components only |
| Opening links in a browser | 1237, 1268–1277 | Not documented. Links open in the in-game wiki reader instead. |
| Launcher and .exe | `launcher.pyw` | The Plugin Hub enables the plugin |

---

## 7. Data model (PersistentDB)

PersistentDB stores values per plugin, and they persist across game sessions. Jagex: records "are shared by all game clients of the same type on the device, and therefore all characters that are played from the device". So every per-character key is prefixed with a **character key**.

- **Character key** = the display name, lowercased, with spaces and underscores both turned into `_`. Jagex treats names as "case-insensitive, and spaces and underscores are treated the same".
- A name change starts a fresh profile. The optional `trackingAccess` permission would fix that, but it adds another permission to review, so v1 doesn't use it (§14 Q5).
- All values use the **typed** setters and getters (`SetStructuredData` / `GetStructuredData`, `SetString` / `GetString`, …). Jagex warns that the untyped `Set` can't tell Int from Float.
- Save on every user change, not only in `PluginShutdown()`. Jagex notes data is lost "if the client crashes".

| Key | Type | Contents | Replaces (app) |
|---|---|---|---|
| `settings` | StructuredData | `{ provider = "claude"\|"gemini"\|"openai", providers = { claude = { model = "claude-sonnet-5-5", effort = "medium" }, gemini = { model = "gemini-3.8-flash" }, openai = { model = "gpt-6.1-sol", effort = "medium" } }, maxAnswerWords = 250, debug = false, hotkey = "ctrl+shift+h", window = { size = "M", x = .., y = .., chatCollapsed = false, explorerCollapsed = false, quickActionsCollapsed = false, setupCollapsed = false } }` (consent moved to `<char>.consent`, §9.2) | `settings.json` (global parts) |
| `keys` | StructuredData | `{ claude = "", gemini = "", openai = "" }` | `gemini_api_key`, `openai_api_key` (Claude is new) |
| `<char>.todo` | StructuredData | `{ nextId = 7, items = { { id = 6, text = "...", done = false, priority = "high"\|"med"\|"low", category = "quest"\|"skill"\|"boss"\|"other" } } }` | `todo_tasks` |
| `<char>.favBosses` | StructuredData | `{ "Giant Mole", ... }` | `favorite_bosses` |
| `<char>.ownedItems` | StructuredData | `{ slayer_helm_1 = true, ... }` (manual ticks only, see §6.8) | `owned_items` |
| `<char>.prompts` | StructuredData | `{ { name = "...", text = "..." } }` | `custom_prompts` |
| `<char>.customInstructions` | String | free text, max 2,000 chars | `custom_instructions` |
| `<char>.consent` | StructuredData | the current consent per provider: `{ claude = { noticeVersion = 1, signedName = "RozRaid", acceptedAt = <time or nil>, pluginVersion = "0.0.1" } }` (§9.2) | new |
| `<char>.consentLog` | StructuredData | the last 20 consent events: `{ { event = "accepted"\|"withdrawn", provider, noticeVersion, at, pluginVersion } }` | new |
| `<char>.memory` | StructuredData | last 3 sessions: `{ { date = "2026-11-08", summary = "..." } }`, each summary ≤ 300 chars | `sessions/*.json` + `load_past_session_memories` |
| `<char>.snapshot` | StructuredData | last known profile (skills, QP, combat level, time), used in the lobby or when the client data isn't loaded | `account_profiles_archive.md` |
| `cache.<name>` | StructuredData | `{ fetchedAt = <time>, data = {...} }` for wiki category lists, events and so on | `st.cache_data` |

Fixes carried in from the app's bugs: per-character data (the app stored everything globally), unique task ids (`nextId` counter instead of `task_<unix time>`), and real categories (the app's category filters did nothing).

**Storing API keys.** PersistentDB is a local file, so the keys sit in plain text on the player's device, the same as the desktop app's `settings.json` today. The listing must say this (§12). Jagex makes masked input fields unreadable to the plugin (their content reads as an empty string), so keys are typed in a visible field that's cleared on save; afterwards only `••••` plus the last 4 characters is shown (§5.6). Settings must include a **Forget keys** button that deletes `keys`. Who else can see a key is set out in §9.3.

---

## 8. AI integration

### 8.1 Transport

All three providers are called with `HTTPRequest:Post`. The Jagex HTTP API has no streaming, so the whole answer arrives in one go. While waiting, show a "Thinking…" line with a **Stop** button (`HTTPRequest:Cancel()`).

| | Claude (Anthropic) | Gemini | OpenAI |
|---|---|---|---|
| Manifest base URL | `claude = "https://api.anthropic.com/"` | `gemini = "https://generativelanguage.googleapis.com/"` | `openai = "https://api.openai.com/"` |
| Path | `v1/messages` | `v1beta/models/<model>:generateContent` | `v1/chat/completions` |
| Headers (`AddHeader`) | `Content-Type: application/json`, `x-api-key: <key>`, `anthropic-version: 2026-10-21`, `anthropic-beta: server-side-fallback-2026-07-01` | `Content-Type: application/json`, `x-goog-api-key: <key>` | `Content-Type: application/json`, `Authorization: Bearer <key>` |
| Body | `{ model = M, max_tokens = 16000, system = SYS, messages = { {role="user",content=...}, {role="assistant",content=...}, ... }, output_config = { effort = "medium" }, fallbacks = "default", cache_control = { type = "ephemeral" } }` | `{ systemInstruction = { parts = {{ text = SYS }} }, contents = { {role="user",parts={{text=...}}}, {role="model",...}, ... }, generationConfig = { maxOutputTokens = 8192 } }` | `{ model = M, reasoning_effort = E, max_completion_tokens = 8000, messages = { {role="system",content=SYS}, {role="user",...}, {role="assistant",...}, ... } }` |
| Answer | Join every `content[*]` block with `type == "text"`; skip `thinking` and `fallback` blocks | `candidates[1].content.parts[*].text` | `choices[1].message.content` |
| Errors | non-200 → `error.type` + `error.message` from the body (table below) | non-200 → show `error.message` from the body | same |

**Claude specifics** (Anthropic Messages API, `anthropic-version: 2026-10-21`)
- **Don't send `temperature`** (or `top_p` / `top_k`). On this API version every model rejects them with HTTP 400 (§8.1a).
- **Don't send `thinking`.** Claude Sonnet 5.5, Opus 5.5 and Haiku 5.5 think adaptively by default, and Sonnet 5.5 and Opus 5.5 reject `thinking: disabled`. Depth is set with `output_config.effort`: `medium` by default (sent explicitly), with `low` (fastest) and `high` in Settings.
- **`max_tokens = 16000`.** It caps thinking *and* answer together, so a small value cuts answers off. Answer length is controlled by the prompt (~250 words, §8.4). If `stop_reason == "max_tokens"`, show "The answer was cut off. Ask for a shorter answer."
- **Refusals:** for Sonnet 5.5 and Opus 5.5, `fallbacks = "default"` with the `server-side-fallback-2026-07-01` beta header lets the API retry a declined request on a suitable fallback model inside the same call. If `stop_reason == "refusal"` anyway, show "Claude declined this question. Try rephrasing it as planning advice." and don't retry.
- **History is plain text.** Earlier turns are sent as `{role, content = "<text>"}` only. Thinking blocks are never stored or sent back, and the system prompt never changes between requests. That keeps the plugin clear of the API's history-editing check on replayed thinking blocks, and the sliding window of the last 6 turns (§8.2) can drop old turns freely.
- **Caching:** top-level `cache_control = { type = "ephemeral" }` caches the fixed system prompt and earlier turns between questions, which makes follow-ups cheaper and faster.
- **Retries:** HTTP 429, 500 and 529 retry like the others (§6.13), waiting at least the `retry-after` header when present.

| Status | `error.type` | Message shown |
|---|---|---|
| 400 | `invalid_request_error` | "Request rejected: <message>" (a plugin bug; logged when debug is on) |
| 401 | `authentication_error` | "Your Claude API key was rejected. Check it in Settings." |
| 402 | `billing_error` | "Your Anthropic account has a billing problem." |
| 403 | `permission_error` | "This API key can't use that model." |
| 404 | `not_found_error` | "Model not found. Check the model ID in Settings." |
| 413 | `request_too_large` | "Question plus context is too long." (shouldn't happen at ~6 KB) |
| 429 | `rate_limit_error` | "Rate-limited. Retrying in N s…" |
| 500 / 529 | `api_error` / `overloaded_error` | "Claude is busy. Retrying…", then "Try again in a minute." |

**JSON.** The Jagex docs don't document any JSON library. The plugin ships its own small `lib/json.lua` (encode and decode, about 200 lines), written from scratch for this plugin and heavily commented. Don't paste in someone else's JSON library: its licence would have to allow uploading to AI tools, and it adds code a moderator has to review.

### 8.1a Model choice per provider (owner review, 2026-11-08)

Each provider keeps **its own model and effort setting**, chosen by the player in Settings. Switching provider keeps each one's choice.

| Provider | Default model | Default effort | Effort sent as | Other built-in choices |
|---|---|---|---|---|
| Claude | `claude-sonnet-5-5` (Claude Sonnet 5.5) | `medium` | `output_config.effort` (low / medium / high) | `claude-opus-5-5`, `claude-haiku-5-5` |
| Gemini | `gemini-3.8-flash` (Gemini 3.8 Flash) | the model's own default (medium) | not sent | none in v1 |
| OpenAI | `gpt-6.1-sol` (GPT-6.1 Sol) | `medium` | `reasoning_effort` (low / medium / high) | none in v1 |

- **Picker:** a `ui.ComboField` per provider listing:
  - the built-in choices above;
  - the models returned by that provider's model-list endpoint, loaded after **Check key** (Claude `GET v1/models`, Gemini `GET v1beta/models` filtered to models that support `generateContent`, OpenAI `GET v1/models`);
  - a **Custom model ID** field, so new models work without a plugin update.
- **Built-in models get every option.** Custom IDs get none: for a model ID not in `ai/providers/models.lua`, the plugin sends no effort or fallback options (they 400 on some models) and says "Advanced options off for custom models".
- **Claude refusal fallbacks** (`fallbacks = "default"` and its beta header) are sent only for `claude-sonnet-5-5` and `claude-opus-5-5`. Claude Haiku 5.5 has no server-side fallback.
- **No `temperature` for any provider.** The Claude API rejects it. GPT-6.1 Sol is a reasoning model, and its supported parameters are the reasoning settings above. Gemini 3-series models are tuned for their default temperature.
- **Output limits include reasoning.** Gemini's `maxOutputTokens` and OpenAI's `max_completion_tokens` count thinking or reasoning tokens as well as the answer. So the limits are set well above the answer size (8192 and 8000), and answer length is controlled by the prompt (~250 words). A cut-off answer shows the same "cut off" message as Claude's.
- **OpenAI uses Chat Completions**, which GPT-6.1 Sol supports for plain text. The plugin uses no tools, so the Responses API isn't needed.
- **Sources** (checked 2026-11-08): Google's Gemini 3.8 Flash model page (`gemini-3.8-flash`, stable, default thinking medium) and OpenAI's reasoning and latest-model guides (`gpt-6.1-sol`, default effort medium, `none` not supported, Chat Completions supported without tools). Re-check before release.

### 8.2 Context sent with each question

The order follows the app's context assembly (`app.py` 1535–1570), trimmed to the essentials. Target size is under about 6 KB per request. The app sent up to about 130 KB on the first message.

1. **Player summary** (from the client, §6.2): combat level, total level, every skill level, QP, members flag. The **character name is not sent**: the prompt says "the player".
2. **Active goals**: open To-Do items with priority (the app dropped priority).
3. **Favourite bosses** and **owned major items**.
4. **Quest state**: counts, plus the titles of STARTED quests and up to 15 ELIGIBLE, NOT_STARTED ones.
5. **Past session summaries** (≤ 3 × 300 chars).
6. **Wiki extract** (≤ 1,500 chars) for the page the user has open in the Explorer, or for the best wiki search hit on the question (§6.6). This replaces the app's 6-keyword match.
7. **GE prices**, only for items the user has pinned or asked about by exact name (§6.9).
8. **Conversation history**: the last 6 turns of this session. The app sent none, so every question started from scratch. This is a deliberate improvement.

**Where it goes:** for every provider, this context is attached to the **latest user message** (as the app did: `User Request: … Context: …`). Earlier turns keep only the player's question and the answer text. The system prompt stays fixed.

Dropped: the 3,000-URL "wiki links source block" (most of it was punctuation-only titles) and the raw profile text dump.

### 8.3 Answer post-processing

1. Convert the Markdown-ish answer into the game's text markup (§5.5): headings → bold/colour, bullets → `•`, tables → "Label: value" lines, links → citation chips.
2. **Wiki citation check** (replaces `verify_wiki_urls` and the 8.8 MB title cache). Collect every `runescape.wiki/w/<Title>` link and send **one** batched request: `api.php?action=query&format=json&formatversion=2&redirects=1&titles=A|B|C`, up to 50 titles. Pages with `missing = true` get a ⚠ marker. This was tested on 2026-11-08 and returns e.g. `("Fake page xyz", missing=true)`.
3. Citation chips open the page **inside the Explorer's Wiki tab** (an intro extract via the wiki API). The plugin can't open a web browser (§14 Q3).
4. **Facts vs suggestions.** The source line under each answer (§5.3) comes from step 2. If at least one cited page exists, the answer counts as wiki-sourced guidance. If none does, it's marked "No wiki source: treat this as a suggestion". Within the text, lines the model starts with `Suggestion:` (§8.4) are shown in the muted colour, so wiki facts and the advisor's own advice are easy to tell apart.

**Wiki licence.** RuneScape Wiki content is CC BY-NC-SA 3.0 (confirmed via the wiki API's `rightsinfo`, 2026-11-08). Requirements: always attribute (the page title and link, via the chips and reader line); keep the plugin non-commercial (it's free); and if wiki text is ever bundled inside the plugin files, that text stays under the same licence. v1 bundles none and only fetches it live.

### 8.4 System prompt

Based on `agent_instructions.md`, shipped as `ai/system_prompt.lua` so a moderator can read it. Changes from the app:

- **Removed:** "Format stat breakdowns using clean Markdown tables". The in-game text component can't draw tables.
- **Added, required by Jagex's guidelines:**
  - "You give planning and preparation advice only. Never give real-time combat instructions: no prayer switching, ability rotations for a fight in progress, timing calls, or where to stand or move."
  - "Never claim to know hidden game information, drop outcomes, or future boss mechanics."
  - "Only discuss the player described in the context. Don't speculate about other players."
- **Added, facts vs suggestions** (owner decision): "Information that comes from the RuneScape Wiki extracts in the context is fact: state it plainly as guidance and cite the page as a full https://runescape.wiki/w/ link. Start any recommendation of your own (what the player should do next, or a choice between options) with 'Suggestion:'. If the context has no wiki source for something, say it's from general knowledge and may be out of date."
- **Added, for the small window:** "Answer in at most ~250 words. Use short paragraphs and bullet points. Cite wiki pages as full https://runescape.wiki/w/ links."
- Custom instructions from Settings are appended under `PLAYER CUSTOM INSTRUCTIONS:` (max 2,000 chars), as in the app.

### 8.5 Session memory

When the window closes, or after 30 minutes idle, save a ≤ 300-character summary of the session's first question and the To-Do items touched to `<char>.memory`. Keep only the last 3. The app used the first 100 characters of the first question, with no AI summarising. Doing the same keeps it free and predictable.

---

## 9. Privacy and data protection

| Data | Where it goes | Why |
|---|---|---|
| Skill levels, QP, quest status, To-Do text, favourite bosses, owned items, question text, chat history (this session) | Claude (Anthropic), Gemini (Google) **or** OpenAI, whichever the player picks; all USA | To answer the question |
| Character display name | Jagex Adventurer's Log API (`secure.runescape.com`, UK) | To fetch the player's **own** recent events and quest eligibility |
| Search words and page titles | RuneScape Wiki API (`runescape.wiki`) | Wiki search, extracts, citation check |
| Item names | Weird Gloop GE API (`api.weirdgloop.org`) | GE prices |
| API keys | Stay on the device (PersistentDB), and are sent only to their own provider | Authentication |

- **Never sent anywhere:** chat messages from the game, other players' names or data, location, inventory contents beyond the major-items ticks.
- **Data protection case:** Case 3 (USA, no UK adequacy). Anthropic offers no EU or UK processing: its `inference_geo` setting only chooses `"global"` (the default) or `"us"`, so it doesn't change the case. Required: endpoints, security measures (HTTPS; keys held only on the device), a privacy notice (the ICO generator is fine), a public contact email (§12), and Jagex's adequacy exception form (password `RS3API`), which collects the developer's name, country and a data-protection email.
- **Bring-your-own-key means the player's own agreement applies.** Data goes from the player's game client straight to the AI provider account the player chose. RS Helper has no server, so the developer never receives questions, answers, stats or keys.
- **Offline mode:** without `httpAccess`, nothing leaves the device (Case 1 behaviour). Say this in the listing.

### 9.1 Who handles the data

| Party | What it sees | Under whose terms |
|---|---|---|
| The chosen AI provider (Anthropic, Google or OpenAI) | Questions, answers, the context summary, and the API key | **The player's own agreement with that provider**, including its usage policy: Anthropic's Usage Policy (anthropic.com/legal/aup), the Gemini API terms (ai.google.dev/gemini-api/terms), or OpenAI's usage policies (openai.com/policies/usage-policies). Confirm the URLs before release. |
| Jagex | Whatever passes through the game client (see §9.3) | The Jagex EULA |
| RS Helper's developer | Nothing: there is no RS Helper server | n/a |

### 9.2 Consent: explicit, signed and recorded (owner review, 2026-11-08)

Before **anything** is sent to an AI provider, the player completes this screen. It's step 2 of the setup panel (§5.3) and is also reachable from Settings.

```
Before the advisor sends anything, please confirm:

[ ] I choose to send my questions, this chat and a summary of my
    character's stats to Anthropic, using my own API key.
[ ] Anthropic handles this data under my own agreement with them and
    their Usage Policy (anthropic.com/legal/aup), not RS Helper's.
[ ] I understand my API key is stored as plain text on this device.
    Other plugins can see keystrokes while I type it, and Jagex may be
    able to see it (details in Settings → Privacy).

Sign by typing your character name: [ RozRaid            ]
                                               [ I agree ]
```

- **Explicit:** all three boxes must be ticked, and **I agree** stays disabled until they are.
- **Signed:** the typed name must match `Player.GetEntity().displayName` (ignoring case, and treating spaces and underscores as the same, as Jagex does).
- **Recorded:** accepting writes `<char>.consent.<provider>` with the notice version, the signed name, the time (if `os.time` exists, §14 Q1) and the plugin version, and appends an entry to `<char>.consentLog` (§7). The record stays on the player's device. With no server, the developer never receives it.
- **Shown and revocable:** Settings → Privacy shows "Consent given <date> for Anthropic (notice v1)" with a **Withdraw** button. Withdrawing stops all AI requests at once, logs a `withdrawn` event and brings back the setup panel.
- **Asked again when:** the player switches provider, the notice text changes (its version number goes up), or a different character logs in.
- `ai/chat.lua` checks for a valid consent record **before every request**, not only at setup.

### 9.3 Who can see the API key (checked against Jagex's docs, 2026-11-08)

| Who | Can they see the key? | Why |
|---|---|---|
| **Other plugins, reading storage** | **No** | "Records are isolated per plugin, preventing plugins from accessing or modifying eachother's data." (PersistentDB) |
| **Other plugins, while the key is typed** | **Yes** | `Event.KeyTyped` and `Event.KeyDown` reach every plugin. Jagex blocks them only while a *restricted* field is focused ("such as an InputField with hidden text"), and a restricted field's content can't be read by our own plugin either (§5.6). Whether pasting avoids these events is unknown (§14 Q14). |
| **Other plugins, reading our window** | Not documented | Whether one plugin can read another plugin's on-screen components isn't covered. The key field is cleared the moment it's saved. |
| **Plugins that depend on RS Helper** | **No** | RS Helper exports nothing, and "Allow dependents" stays off on mod.io. |
| **Jagex** | **Possibly** | The key is sent by the game client's own `HTTPRequest` system and stored in the client's data folder. Jagex's docs don't say whether the client logs plugin requests or storage, so it can't be ruled out. |
| **Anyone with access to the computer** | **Yes** | PersistentDB is a plain file on the device ("variables in the database are written to a file"). |
| **The chosen AI provider** | **Yes** | It needs the key to authenticate the request. |

**Advice shown to players** (in the consent screen, Settings → Privacy and the listing): create a **separate API key just for RS Helper**, set a **low spending limit** on it in the provider's console, and revoke it there if anything looks wrong. **Forget key** removes it from the device.

---

## 10. HTTP endpoints used (all base URLs go in the manifest)

| Var (`Plugin.urls.*`) | Base URL | Paths used |
|---|---|---|
| `wiki` | `https://runescape.wiki/` | `api.php?action=query&list=search…`, `…&prop=extracts&exintro=1&explaintext=1&redirects=1&titles=…`, `…&titles=A\|B` (existence), `…&list=categorymembers&cmtitle=Category:Quests\|Bosses\|Slayer_assignments&cmlimit=500&cmcontinue=…` |
| `advlog` | `https://secure.runescape.com/m=adventurers-log/` | `api/v1/playerEvents/<own name>`, `api/v1/playerData/<own name>?includeQuests=true` |
| `ge` | `https://api.weirdgloop.org/` | `exchange/history/rs/latest?name=A\|B` (the app's current source; the client API has no prices) |
| `claude` | `https://api.anthropic.com/` | `v1/messages` |
| `gemini` | `https://generativelanguage.googleapis.com/` | `v1beta/models/<model>:generateContent` |
| `openai` | `https://api.openai.com/` | `v1/chat/completions` |

- Every request sends a `User-Agent` such as `RS Helper plugin <version> (<contact email>)`. Jagex's Platform API best practices ask for this, and the wiki asks for the same.
- The Adventurer's Log caches answers for up to 10 minutes, so the plugin caches them for 10 minutes too.
- Wiki category lists are cached for 24 hours, like the app's `st.cache_data`. Also follow `cmcontinue`, which fixes the app's silent 500-item cut-off.

---

## 11. Development and testing

### 11.1 Where testing can happen

Jagex offers **no lite client** and **no developer options on a live account**. Unmoderated plugins only run in the **plugin beta world**, Jagex's developer environment. There are three places to test, each covering different things:

| Where | What it is | What it can test | Limits |
|---|---|---|---|
| **Your PC, outside the game** | A standard Lua 5.4 interpreter running `plugin/tests/` with small fake versions of the Jagex APIs (§11.3) | JSON, text formatting, the context builder, provider request and response mapping, error messages, storage rules, To-Do logic. The real wiki, Adventurer's Log and AI endpoints can be called with the same request shapes from a desktop script. | No UI and no game data. The fakes must follow Jagex's documented signatures. |
| **Plugin beta world** | A separate beta client and world, reached through the launcher link in Jagex's tutorial. **Import save** copies your live character in (once per hour). Plugins in `dev_plugins/` run there, and the console and cheats work. | Everything in-game: the UI, events, live stats, quests, items, permissions (granted with `ppe`), HTTP calls, crash safety. | Progress never transfers back to live. No Grand Exchange. Cheats are logged, and abusing them can get the account banned. PersistentDB data isn't shared with the live client. The console doesn't exist on mobile. |
| **Live game** | Only after Jagex approves the plugin, installed from the Plugin Hub | The real Plugin Hub install and permission prompt, and real players' setups | No cheats, no dev plugins. Every new version goes through moderation again. |

### 11.2 Beta world setup

From Jagex's "Accessing the API" tutorial:
1. Join the plugin beta world through the launcher link on the tutorial page. In the lobby, use **Import save** (allowed once per hour).
2. Put `plugin/rs-helper/` inside `<beta root>/dev_plugins/` (default `C:\ProgramData\Jagex\RuneScape-BETA\dev_plugins\`; Mac and Linux paths are on the tutorial page). A symlink or copy script in `plugin/tools/` keeps the repo as the source of truth.
3. Open the console with `ALT` + `` ` ``, then use `prf`, `plist`, `pon rs-helper`, and `prl rs-helper` after each edit.
4. Grant the optional permission with `ppe rs-helper httpAccess`, and test both with and without it (`ppd rs-helper httpAccess`).
5. To go back to live worlds, close both the game and the launcher, then relaunch normally.

### 11.3 Out-of-game test harness

- `plugin/tests/fake_api.lua` stands in for `Player`, `config.Quest`, `Inventory`, `HTTPRequest`, `PersistentDB`, `Event` and `Plugin`, with the same names and arguments as Jagex's docs. Each fake returns scripted data (e.g. a character with 85 Magic and 241 completed quests).
- `plugin/tests/run.lua` runs every `*_test.lua` file with plain `assert`s. There's no third-party test library to install or review.
- Run it with `lua5.4 plugin/tests/run.lua`, and in GitHub Actions on every push (`apt-get install lua5.4`).
- It covers most of the logic without opening the game. The beta world is then only needed for the UI and real game data.

### 11.4 What the beta world can't show

- **Adventurer's Log and Hiscores return your *live* character**, not the beta copy. After `!allinone` or `!setvar`, the client and the Adventurer's Log disagree. Test the quest-eligibility merge (§6.4) on a fresh **Import save** with no quest cheats.
- **Grand Exchange:** the beta is cut off from the GE. Price lookups still work, because they come from Weird Gloop's live data, and the plugin doesn't use GE offers.
- **Plugin Hub install and the live permission prompt:** in the beta, permissions are granted from the console. Jagex says the in-game plugin controls are "still in development", so check the setup panel's web-access step again after approval.
- **Mobile:** dev plugins can't be loaded there (no console). Test the mobile code paths (no hotkey, no mouse position) with the fakes, then check on a phone after approval.

### 11.5 Testing it all in one go

Almost everything for a milestone can be tested in **one beta session of about 45 minutes**, in this order:
1. Import save, enable the plugin with **no** permission: every Explorer tab works, and the setup panel shows step 1.
2. `ppe rs-helper httpAccess`: step 1 ticks itself. Accept the notice, save a key, then **Check key**.
3. Ask the test questions in test case 9 and the citation cases. AI calls use your own key and cost a little credit.
4. Work through the cheats table below.
5. Collapse and expand both panes and the quick actions, then reload (`prl`): the layout comes back as it was.
6. Crash test, then a second character, then `!resetsave` and re-import to finish.

The out-of-game tests (§11.3) run before every session, and the live-only checks (§11.4) wait for approval.

**Cheats for each feature** (beta only; Jagex logs cheat use)

| Feature | How to test |
|---|---|
| Profile refresh | `!skilladdlevel attack 1` triggers `SkillTransmit` (`!skillsetlevel` doesn't). |
| Quests | `!setvar <quest varplayer> <value>` moves a quest between states; `!allinone` completes everything. `!resetsave` resets afterwards. |
| Items | `!give <obj> 1` (backpack), `!give <obj> 1 bank`, `!clearinv`, `!clearworn`, `!listinv bank`. |
| Combat badges | `!skillsetlevel` on the combat skills, then check the Bosses tab. |

**Test cases** (each must pass before a milestone ships)
1. Fresh install, no permission: every Explorer tab works, and the setup panel replaces the chat pane at step 1.
2. Login, logout, world hop, and a second character on the same device: data stays separate per character.
3. Quest filters match the in-game quest list for the imported save (spot-check 10 quests).
4. Network errors: wrong API key (401), no credit (402/429), timeout, wiki down. For Claude, also a forced `max_tokens` cut-off and a refusal. Each shows a clear message and never freezes the window.
5. Cancel an AI request mid-flight.
6. Long answers: wrapping, scrolling, the 250-word guidance, citations with and without ⚠, and the source line.
7. Crash safety: change a To-Do, force-close the client, and check it's still there.
8. Windows, Mac and Linux (Bolt) clients.
9. Guardrails: ask "what prayer do I switch to on phase 3 right now?". The advisor must decline live combat calls and offer preparation advice.
10. Collapsing: each pane alone, both together, quick actions, and the setup panel. The open pane fills the space, and the states survive a reload.
11. Permission revoked mid-session (`ppd`): the setup panel returns and no request is sent.

---

## 12. Submission checklist (mod.io)

From Jagex's "Submission process" and "Example description" pages.

**Package**
- [ ] Zip named with the version, e.g. `rs-helper-0-1-0.zip`, with `main.lua` and `plugin.json` at the **top level** of the zip.
- [ ] Leave out `.git`, `.gitignore`, `.luarc.json`, `README.md` and dev notes.
- [ ] `plugin.json` has every field: name, version (same as on mod.io), `contactEmailAddress`, dependencies, permissions, urls.
- [ ] Platforms: Windows, Linux and Mac all ticked.
- [ ] Debug logging off by default.

**Listing**
- [ ] Name: 1–50 ASCII characters. Summary: 10–150 ASCII characters, without repeating the name or starting with "This plugin…".
- [ ] Listing image: 16:9, at least 512×288. Gallery screenshots taken in the beta world.
- [ ] Tags include the **httpAccess** permission tag.

**Required description sections**
- [ ] **Email**: a public contact address, separate from the mod.io login.
- [ ] **Feedback and collaboration**: e.g. GitHub issues on this repo, plus your stance on contributions.
- [ ] **EULA**: the exact statement: "This Plugin uses software licensed by Jagex to the developer under the terms of the Jagex End User Licence Agreement (EULA) found at https://legal.jagex.com/docs/terms/eula (and all terms incorporated into it by reference). The development and any use of the Plugin is at all times subject to the Jagex EULA."
- [ ] **How the advisor answers**: facts come from the RuneScape Wiki and are cited (CC BY-NC-SA 3.0), and the advisor's own suggestions are marked as such. It gives planning and preparation help only, never live combat calls.
- [ ] **Permissions**: one paragraph per URL: which data goes to which base URL, and why. Say that the plugin works without `httpAccess` in offline mode.
- [ ] **Data protection (Case 3)**: data used, endpoints, security measures, a link to the privacy notice, the bring-your-own-key model (data goes under the player's own agreement with their chosen provider), how consent is signed and recorded (§9.2), and who can see the API key (§9.3).

**After uploading**
- [ ] Fill in Jagex's adequacy exception form (data sent to the USA).
- [ ] Ask the moderator to confirm `httpAccess` to the Anthropic, Gemini and OpenAI hosts (assumption A1).
- [ ] During the moderation **code freeze**, make no mod.io edits.

**Licence note.** Under the Jagex EULA, submitting grants Jagex a royalty-free, perpetual, irrevocable licence to the plugin. A plugin can be treated as abandoned after 60 days without needed maintenance.

---

## 13. Milestones

Each milestone is small enough to review by hand and to moderate.

| Version | Scope | Permissions | Review risk |
|---|---|---|---|
| **0.0.1 "First build"** (beta world only, not submitted) | Window shell with collapsing panes, setup panel (web access, signed consent, API key), and chat with **one** provider (Claude). Plan: `PLUGIN_BUILD1_PLAN.md`. | `httpAccess` (claude) | Not submitted; tested in the beta world only |
| **0.1 "Explorer"** | Window shell (with collapsing panes), Profile, Quests (from the client), To-Do, Items (manual ticks), Bosses (preparation), Settings, and the out-of-game test harness. No network. | none | Low ("planning tools … using player-known data" are listed as Allowed) |
| **0.2 "Wiki"** | Wiki search and reader, category lists, GE prices, Adventurer's Log events and quest eligibility | `httpAccess` (wiki, advlog, ge) | Medium (any permission is "subject to review") |
| **0.3 "Advisor"** | AI chat (Claude/Gemini/OpenAI), context builder, citation check, session memory, prompt templates | `httpAccess` (+ claude, gemini, openai) | Higher ("interpreted or actionable gameplay recommendations"), Case 3 data protection |

The first build (0.0.1) proves the hardest unknowns early: key entry, consent, HTTP to an AI provider, and the chat UI. It stays in the beta world. For submission, 0.1 still goes first, so a plugin gets through moderation once, cheaply, before adding the parts that get the most scrutiny.

---

## 14. Open questions to check in the beta

| # | Question | Why it matters | Fallback |
|---|---|---|---|
| Q1 | Which Lua standard libraries exist (`os.time`, `os.date`, `utf8`)? | Cache TTLs across sessions, dates on memories | Session-only caches, and no dates on memories |
| Q2 | Do Adventurer's Log quest IDs equal `config.Quest.FromID` IDs? Does `FromID` return nil for unknown IDs? | Listing all quests | Bundled `data/quest_ids.lua` |
| Q3 | Can a plugin open a URL in the system browser? | Wiki links | In-game reader only |
| Q4 | What's the worn-equipment inventory's config name? Is the bank readable when it's closed? | Item auto-detect | Manual ticks |
| Q5 | Is `trackingAccess` worth requesting, so data survives name changes? | Per-character storage | Keyed by display name |
| Q6 | Is the Slayer task in an API-visible VarPlayer? | Auto-filling the Slayer form | Manual form |
| Q7 | PersistentDB size limits? | Memory, caches | Keep stored data under ~100 KB total |
| Q8 | HTTP timeout length, maximum response size, parallel request limit? | AI calls can take 10–30 s | One request at a time, through the `lib/http` queue |
| Q9 | Does `GetLevelUncapped` return virtual levels above 99/120? | Profile display | Show the XP alongside |
| Q10 | Can `ui.Model:SetModel` show a boss's NPC model? (Item icons by ID are documented.) | Boss pictures | Text only |
| Q11 | Does the game font render emoji? | Badges, catalog labels | Coloured text and game sprites |
| Q12 | Is the AI advisor acceptable to moderators (A1)? | The whole Chat half | Ship 0.1 / 0.2 without it |
| Q13 | Where is the Weird Gloop GE API hosted? | Data-protection case for that URL (only item names are sent) | Say so in the listing |
| Q14 | Can players paste (Ctrl+V) into a `ui.InputField`? Does a paste fire `Event.KeyTyped` for other plugins? | **API key entry**: typing 40–160 characters by hand is painful. Check this first. | Ask on the RS Plugin Discord / API Council |
| Q15 | Which containers scroll (`ComponentCollection.scrollable`)? Can a GroupBox be dragged with `ONDRAG` and `Mouse.GetPosition()`? | Chat log, moving the popup | Message pager; position presets |
| Q16 | Which modifier and key combinations are free of game keybinds? Key events can't be consumed. | Hotkey | Launcher button only |
| Q17 | Does `ui.Text` render `<col=…>` tags like chat does? | Coloured words inside one message | One Text component per colour |
| Q18 | Can a plugin re-ask the player for an optional permission from a button? Only `HasPermission` and `OptionalPermissionChanged` are documented. (The console's `plugins_permissions_request` exists, but the console is a dev tool and isn't on mobile.) | The setup panel's web-access step | Show where to allow it in the Plugin Hub. Ask the API Council. |

---

## Appendix A — Legacy desktop app: RuneMetrics shutdown (optional)

**Not planned work.** The desktop app is legacy (A4). This appendix only records what would fix it, in case it's ever revived. The same Platform API endpoints are what the plugin's `web/advlog.lua` uses (§10).

Jagex: "All endpoints under `apps.runescape.com/runemetrics/...` are going offline on the 10th November 2026." `fetch_runemetrics_profile` (`app.py` 323–399) uses two of them. The replacements below were tested on 2026-11-08 with the account `rozraid`: all returned HTTP 200.

| Old (RuneMetrics) | New (Platform API) | Format change |
|---|---|---|
| `profile/profile?user=N` → `skillvalues[{id, level, xp, rank}]` | `https://secure.runescape.com/m=hiscore/index_lite.json?player=N` → `skills[{id, name, rank, level, xp}]` | **`xp` is real XP here**: remove the `/10` at `app.py` 376. `id` 0 is now "Overall", and skills start at 1. |
| (same, faster updates) | `https://secure.runescape.com/m=adventurers-log/api/v1/playerData/N?includeSkills=true` → `skills{attack:{level, fine_xp}}` | `fine_xp` is XP × 10. The map is keyed by skill name (`hitpoints`, `runecraft`). |
| `profile/profile` → `activities` | `…/m=adventurers-log/api/v1/playerEvents/N` → `events[{type, date, text, details}]` | `date` is ISO 8601 |
| `quests?user=N` → `quests[]` | `…/api/v1/playerData/N?includeQuests=true` → `quests{<id>:{title, status, eligible, qp, members, difficulty}}`, plus `qp`, `qp_max` | Object keyed by quest id. `userEligible` → `eligible`. Count `questscomplete` and the other totals yourself. |
| `profile/profile` → `combatlevel`, `totalskill`, `totalxp`, `rank` | Overall row of `index_lite.json` gives total level, XP and rank | **Combat level is no longer provided.** Compute it from the skill levels. |
| `xp-monthly` | none | No replacement |

Bonus: `eligible` gives a real "quests you can start now" list (42 for `rozraid` today). That replaces the broken `get_available_quests` (`app.py` 507–524), which only checked "not completed" and had a case bug.

Also: send a descriptive `User-Agent` instead of `RSAgent/1.0`. Jagex lists generic agents under "Bad".

---

## Appendix B — Jagex documentation used

Client API (plugins), https://developer.runescape.com/rs/:
`structure.html` (manifest, permissions, dependencies) · `core/plugin.html` (permissions, resources) · `core/http.html` (HTTPRequest) · `core/persistentdb.html` · `core/events.html` · `core/string.html` (`formatStr`) · `core/keyboard.html` · `game/player.html` · `game/inventory.html` · `game/grandexchange.html` · `game/config/questtype.html` · `ui/*` · `tutorial/1helloworld.html`–`6cheats.html` · `cheats.html` · `managing.html` · `submission/guidelines.html` · `submission/process.html` · `submission/goodpractice.html` · `submission/adequacy.html` · `submission/example.html`

Platform API (web), https://developer.runescape.com/platform/:
`best-practices.html` · `concepts.html` · `modules/adventurers-log/player-data.html` · `player-events.html` · `migrating-from-runemetrics.html` · `modules/hiscores/index-lite.html`
