# Comprehensive Implementation Plan: RuneScape Advisor Feature Upgrades

This implementation plan outlines the full set of refactorings and new features logged for `app.py`, `agent_instructions.md`, `account_profiles_archive.md`, and `settings.json`.

---

## 1. Feature Specifications

### A. 📜 3-Tier Priority Chain & Account Profiles Memory File (`account_profiles_archive.md`)
- **New Archive File**: Created [account_profiles_archive.md](file:///e:/Projects/gemini-scraper/account_profiles_archive.md) to store archived RuneMetrics profile, skill, and quest data for all saved accounts.
- **Auto-Update Mechanism**: Whenever a successful scrape/fetch occurs via RuneMetrics, `save_account_to_archive(username, profile_text)` updates or appends that account's entry in `account_profiles_archive.md` with an updated timestamp, always favoring fresh RuneMetrics data.
- **3-Tier Priority Execution**:
  1. **Priority 1: Live RuneMetrics API** (`https://apps.runescape.com/runemetrics/...`)
     - On success: Returns live data and saves/updates `account_profiles_archive.md`.
  2. **Priority 2: Archived Memory File** ([account_profiles_archive.md](file:///e:/Projects/gemini-scraper/account_profiles_archive.md))
     - If live RuneMetrics is private or fails, loads the latest archived RuneMetrics data from memory file.
  3. **Priority 3: RuneApps Playwright Web Scraper** (Fallback)
     - Used if neither live RuneMetrics nor archived memory data exist for the account.
- **UI Status Badge**: Displays status badge in Tab 2 and toast notification indicating the active priority source.

### B. 📜 External Agent Instructions (`agent_instructions.md`)
- Extracted base system instructions into a dedicated [agent_instructions.md](file:///e:/Projects/gemini-scraper/agent_instructions.md) instruction file in the project root.

### C. 🤖 To-Do Task Prompt Quick Assistant Button
- Positioned `🤖` icon button in task rows (`st.columns([1, 4, 1, 1])`) to safely pre-fill strategy prompts into `st.chat_input`.

### D. 🖼️ Image Existence Fallback (`[No image]`)
- Performs HTTP HEAD check to render `[No image]` for 404 images.

### E. ⚔️ Bossing Strategy Assistant (Combat Indicators & Persistent Favorites)
- Persistent pinned favorites with combat readiness indicators (🟢 Fine, 🟡 Average/OK, 🔴 Under-leveled/Struggle).

---

## 2. File Architecture & Schemas
- [agent_instructions.md](file:///e:/Projects/gemini-scraper/agent_instructions.md): Master system instruction prompt file.
- [account_profiles_archive.md](file:///e:/Projects/gemini-scraper/account_profiles_archive.md): Archived profile memory file for saved accounts.
- `settings.json`: Configuration, custom prompts, custom guidelines, owned items, To-Do tasks, and favorite bosses.

---

## 3. Verification Plan
- Python syntax compilation: `python -m py_compile app.py` (Passed with 0 errors).
- Test Priority 1 -> Priority 2 -> Priority 3 fallback chain and [account_profiles_archive.md](file:///e:/Projects/gemini-scraper/account_profiles_archive.md) updating in Streamlit GUI.
