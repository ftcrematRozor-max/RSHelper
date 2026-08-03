# **⚔️ RS Helper: UI/UX Redesign & Feature Roadmap Canvas**

## **1\. Executive Summary & Design Vision**

**RS Helper** has evolved into a feature-packed gaming advisor hub. However, as features (RuneMetrics parsing, To-Do list, modal dialogs, multi-modal image attachments, and item tracking) were added, the user interface developed **visual clutter, container layout jumping, and state-refresh friction**.

### **Primary Goal**

Transform RS Helper from a dense developer prototype into an **ergonomic, responsive, and visually cohesive RuneScape 3 Command Center**.

## **2\. Key UI/UX Friction Points Identified**

### **🔴 1\. Chat & Input Bar Ergonomics (High Impact)**

> * **Visual Jumping on Rerun**: Quick Prompts sit above the chat window on a fresh start, but shift to a cramped column beside the file uploader once messages exist. This creates inconsistent layout positioning.  
> * **Attachment & Prompt Clutter**: Having the file uploader, staged attachment previews, and quick prompt expanders scattered *below* st.chat\_input disrupts standard chat ergonomics (like ChatGPT/Claude), where inputs and actions are unified in a single sticky bottom dock.

### **🔴 2\. Major Items Tracker Refresh Stutter (High Impact)**

> * **Immediate st.rerun() on Checkbox Toggles**: Checking or unchecking any item in the 🎒 Major Items tab immediately triggers save\_settings() and forces a full application rerun. Toggling 5 gear pieces causes 5 jarring screen refreshes.

### **🟡 3\. RuneApps Iframe Dependence (Medium Impact)**

> * **Iframe Reliability**: The 👤 My RuneScape Profile tab currently embeds runeapps.org via components.iframe(). External web pages often load slowly, contain third-party banner ads, or get blocked by cross-origin policies.  
> * **Missed Opportunity**: Since RS Helper already fetches clean JSON stat data via the **official RuneMetrics API**, embedding a third-party iframe feels redundant when a native visual skill matrix could be rendered directly.

### **🟡 4\. To-Do Manager Row Compression (Medium Impact)**

> * **Layout Compression in Side-Panel Mode**: When 📋 To-Do & Task Manager is toggled open (3:2 split), each task row splits into 4 columns (\[1, 4, 1, 1\]). On standard resolution monitors, the text box, "Ask AI" button (🤖), and delete button (❌) squeeze into illegible widths.  
> * **Lack of Categorization**: Tasks are listed linearly without priority tags (e.g., High / Med / Low) or category filters (Quests, Skilling, Bossing).

### **🟢 5\. Sidebar Overcrowding (Low Impact)**

> * **Redundant Inputs**: The sidebar contains account selection, model selection, refresh buttons, session logs, agent instructions, manual wiki search, clear chat, and logout. "Manual Wiki Search" in the sidebar duplicates the search functionality already present in the 🌐 Wiki Browser tab.

## **3\. UI/UX Action Plan & Blueprint**

### **Tab 1: 💬 Chat Agent (Unified Command Dock)**

#### **Key Structural Changes:**

> 1. **Unified Input Area**: Move image attachment previews and quick action buttons into a sticky, unified toolbar directly *above* the st.chat\_input prompt box.  
> 2. **Fixed Scroll Viewport**: Ensure the chat window maintains a clean flex scroll height (calc(100vh \- 220px)) without forcing scrollbars on the outer browser window.  
> 3. **Pill Action Badges**: Replace heavy rectangular buttons in Quick Prompts with compact action chips (\[🧭 Quest\], \[⚔️ Bossing\], \[🛡️ Slayer\], \[📋 To-Do\]).

┌─────────────────────────────────────────────────────────────────────────┐  
│                           CHAT CONVERSATION                             │  
│                                                                         │  
│  \[User\]: How do I prepare for 120 Necromancy?                           │  
│  \[Assistant\]: Here is a breakdown based on your current 107 Necro...    │  
│                                                                         │  
├─────────────────────────────────────────────────────────────────────────┤  
│ 💡 Quick Actions: \[🧭 Quest\] \[⚔️ Bossing\] \[🛡️ Slayer\] \[➕ Custom\]        │  
│ 📎 Attachments: \[📷 Inventory.png ❌\] \[📷 Stats.png ❌\]                 │  
│ \----------------------------------------------------------------------- │  
│ \[ 📎 Upload \]  | Ask about your stats, goals, gear...   \[ Send \]        │  
└─────────────────────────────────────────────────────────────────────────┘

### **Tab 2: 👤 My RuneScape Profile (Native Visual Dashboard)**

#### **Key Structural Changes:**

> 1. **Replace Iframe with Native Skill Matrix**: Construct a grid showing all 29 RS3 skills with current level, rank, and XP progress bars.  
> 2. **Account Summary Cards**:  
   * **Combat Level Card**: Large badge displaying combat level (e.g., 135\) with Necromancy status.  
   * **Quest Progress Ring**: Completion percentage (e.g., 240 / 363 Quests Complete).  
   * **Total XP Banner**: Total account experience formatted cleanly (119,815,027 XP).  
> 3. **Recent Activity Stream**: Render the RuneMetrics activity log (\[02-Aug-2026\] Levelled up Summoning to 79\) in a clean visual timeline.

┌─────────────────────────────────────────────────────────────────────────┐  
│ 👤 RozRaid  |  Combat: 135  |  Total Skill: 2,351  |  Total XP: 119.8M  │  
├─────────────────────────────────────────────────────────────────────────┤  
│ SKILL MATRIX                                                            │  
│ ⚔️ Attack: 86     🛡️ Defence: 89     💪 Strength: 81   🏹 Ranged: 81   │  
│ 🔮 Magic: 81      💀 Necro: 107 \[MAX\] 📿 Prayer: 84     ❤️ Const: 93     │  
│ 🛠️ Invent: 48     📜 Arch: 86        ⛏️ Mining: 79     🪵 Woodcut: 76   │  
│ ... (Clean 4-column layout with RS skill icon badges)                  │  
└─────────────────────────────────────────────────────────────────────────┘

### **Tab 3: 🎒 Major Items & Upgrades Tracker (Staged Batch Saving)**

#### **Key Structural Changes:**

> 1. **Batch State Staging**: Store checkbox changes in st.session\_state locally and add a sticky bottom **"💾 Save Gear Setup"** button. This eliminates individual page reruns on every single checkbox click.  
> 2. **Account Progress Metric**: Add a visual progress indicator at the top of the tab:  
   * *Example*: Unlocks Tracker: 14 / 32 Major Items Owned (43%)  
> 3. **Visual Badge Status**: Highlight owned items with a subtle gold border glow; gray out unowned items for immediate visual feedback.

### **Tab 4: 📋 Player To-Do & Task Manager (Ergonomic Split)**

#### **Key Structural Changes:**

> 1. **Task Card Redesign**: Replace squeezed 4-column table rows with clean, self-contained task cards:  
   * Left side: Checkbox \+ Task Title \+ Priority Tag (🔴 High, 🟡 Med, 🟢 Low).  
   * Right side: Quick Action Buttons (\[🤖 Ask AI\] and \[❌ Delete\]).  
> 2. **Category Tabs**: Divide To-Do items into sub-filters: All Tasks, Active, Combat & Bossing, Quests, Skilling.  
> 3. **AI Auto-Suggest Button**: Add a **"✨ Auto-Generate Next Goals"** button that analyzes missing quest prerequisites and skill thresholds to suggest 3 high-value tasks.

### **Tab 5 (New): ⚔️ Combat & Bossing Hub**

#### **Key Structural Changes:**

> 1. **Dedicated Bossing Dashboard**: Elevate the Bossing Assistant from a small modal dialog to a standalone primary tab.  
> 2. **Interactive Boss Roster**: Browse bosses categorized by tier (*Entry*, *Mid-Tier*, *High-Tier*, *Endgame*).  
> 3. **Smart Gear Matcher**: Cross-reference the selected boss against owned\_items and player stats to generate:  
   * **Readiness Meter**: (e.g., 🟢 Ready, 🟡 Under-geared, 🔴 Need Upgrades).  
   * **Tailored Setup**: Suggest optimal weapon/armor combinations from items the user *actually owns*.

## **4\. Prioritized Developer Implementation Checklist**

### **Phase 1: Core Layout & Chat Ergonomics**

> * \[ \] Restructure tab\_chat layout so prompt chips and attachment previews sit cleanly above st.chat\_input.  
> * \[ \] Remove repetitive st.rerun() calls inside the Quick Prompts rendering loops.  
> * \[ \] Consolidate sidebar elements (remove redundant Wiki search text box).

### **Phase 2: Native Profile Dashboard & Gear Staging**

> * \[ \] Replace runeapps.org iframe in tab\_profile with a Streamlit grid component displaying the 29 RS3 skill levels and XP from RuneMetrics.  
> * \[ \] Refactor tab\_items to use staged session state and a single **"💾 Save Gear Setup"** commit button.  
> * \[ \] Add an item unlock completion progress bar (X / Y Items Unlocked).

### **Phase 3: To-Do List & Bossing Hub Enhancements**

> * \[ \] Implement priority tags (🔴 High, 🟡 Med, 🟢 Low) and category filters in col\_todo.  
> * \[ \] Expand the Bossing Assistant into a dedicated tab with readiness badges based on owned\_items.  
> * \[ \] Add an **"✨ Auto-Suggest Goals"** button to the To-Do Manager.

## **5\. Technical Specification & Context Contract**

{  
  "design\_system": {  
    "theme": "RuneScape Dark Fantasy",  
    "primary\_accent": "\#d4af37",  
    "background\_dark": "\#121212",  
    "card\_background": "\#1e1e1e",  
    "border\_gold": "\#b8860b"  
  },  
  "state\_management": {  
    "batch\_save\_items": true,  
    "unified\_input\_dock": true,  
    "native\_profile\_rendering": true  
  }  
}  
