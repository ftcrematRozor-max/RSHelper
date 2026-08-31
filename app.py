import time
import urllib.parse
import requests
import json
import os
import datetime
import re
import base64
import io
from google import genai
from google.genai import types
from openai import OpenAI
from playwright.sync_api import sync_playwright
import streamlit as st
import streamlit.components.v1 as components


import threading
import pathlib

USER_HOME = pathlib.Path.home()
APP_DIR = USER_HOME / ".rshelper"
APP_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = str(APP_DIR / "settings.json")
INSTRUCTIONS_FILE = "agent_instructions.md"
ARCHIVE_FILE = "account_profiles_archive.md"
WIKI_CACHE_FILE = "wiki_pages_cache.json"

WIKI_VALID_TITLES = set()
WIKI_CACHE_LOADED = False

RS3_SKILL_NAMES = {
    0: "Attack", 1: "Defence", 2: "Strength", 3: "Constitution", 4: "Ranged",
    5: "Prayer", 6: "Magic", 7: "Cooking", 8: "Woodcutting", 9: "Fletching",
    10: "Fishing", 11: "Firemaking", 12: "Crafting", 13: "Smithing", 14: "Mining",
    15: "Herblore", 16: "Agility", 17: "Thieving", 18: "Slayer", 19: "Farming",
    20: "Runecrafting", 21: "Hunter", 22: "Construction", 23: "Summoning", 24: "Dungeoneering",
    25: "Divination", 26: "Invention", 27: "Archaeology", 28: "Necromancy"
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            if "saved_accounts" not in data and "rs_username" in data and data["rs_username"]:
                data["saved_accounts"] = [data["rs_username"]]
            elif "saved_accounts" not in data:
                data["saved_accounts"] = []
            if "custom_prompts" not in data:
                data["custom_prompts"] = []
            if "custom_instructions" not in data:
                data["custom_instructions"] = ""
            if "owned_items" not in data:
                data["owned_items"] = []
            if "todo_tasks" not in data:
                data["todo_tasks"] = []
            if "favorite_bosses" not in data:
                data["favorite_bosses"] = []
            return data
    return {"gemini_api_key": "", "openai_api_key": "", "rs_username": "", "saved_accounts": [], "custom_prompts": [], "custom_instructions": "", "owned_items": [], "todo_tasks": [], "favorite_bosses": []}

def save_settings(gemini_key, openai_key, rs_username, saved_accounts, custom_prompts=None, custom_instructions=None, owned_items=None, todo_tasks=None, favorite_bosses=None):
    if custom_prompts is None: custom_prompts = settings.get("custom_prompts", [])
    if custom_instructions is None: custom_instructions = settings.get("custom_instructions", "")
    if owned_items is None: owned_items = settings.get("owned_items", [])
    if todo_tasks is None: todo_tasks = settings.get("todo_tasks", [])
    if favorite_bosses is None: favorite_bosses = settings.get("favorite_bosses", [])
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "gemini_api_key": gemini_key, 
            "openai_api_key": openai_key, 
            "rs_username": rs_username,
            "saved_accounts": saved_accounts,
            "custom_prompts": custom_prompts,
            "custom_instructions": custom_instructions,
            "owned_items": owned_items,
            "todo_tasks": todo_tasks,
            "favorite_bosses": favorite_bosses
        }, f, indent=4)

def load_agent_instructions(rs_username: str) -> str:
    """Loads system instructions from external agent_instructions.md file."""
    base_instructions = ""
    if os.path.exists(INSTRUCTIONS_FILE):
        with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
            base_instructions = f.read().strip()
    else:
        base_instructions = "You are an elite RuneScape Master Advisor, Strategist, and Profile Analyst."
        
    full_instruction = f"{base_instructions}\n\nThe active RuneScape username being assisted is: '{rs_username}'."
    
    custom_instr = settings.get("custom_instructions", "")
    if custom_instr.strip():
        full_instruction += f"\n\nUSER CUSTOM INSTRUCTIONS:\n{custom_instr.strip()}"
        
    return full_instruction

def save_account_to_archive(username: str, profile_text: str):
    """Saves or updates RuneMetrics account profile data into account_profiles_archive.md."""
    if not username or not profile_text:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"## Account: {username.lower().title()}"
    content_block = f"{header}\n*Last Updated via RuneMetrics: {timestamp}*\n{profile_text.strip()}\n"
    
    sections = {}
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            full_text = f.read()
        raw_sections = full_text.split("## Account: ")
        for sec in raw_sections[1:]:
            lines = sec.splitlines()
            if lines:
                uname = lines[0].strip().lower()
                sections[uname] = "## Account: " + sec.strip() + "\n"
            
    sections[username.lower()] = content_block
    
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        f.write("# 📜 Saved Account Profiles Archive\n\n" + "\n\n".join(sections.values()))

def load_account_from_archive(username: str) -> str | None:
    """Loads archived profile data for a username from account_profiles_archive.md."""
    if not os.path.exists(ARCHIVE_FILE) or not username:
        return None
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        full_text = f.read()
    raw_sections = full_text.split("## Account: ")
    for sec in raw_sections[1:]:
        lines = sec.splitlines()
        if lines:
            uname = lines[0].strip().lower()
            if uname == username.lower():
                return f"SOURCE: Archived Memory File (account_profiles_archive.md)\n{sec.strip()}"
    return None

RS3_BOSS_CATALOG = [
    {"name": "Giant Mole", "icon": "Giant_Mole", "rec_cb": 60, "tier": "Entry"},
    {"name": "King Black Dragon", "icon": "King_Black_Dragon", "rec_cb": 75, "tier": "Entry"},
    {"name": "Barrows Brothers", "icon": "Ahrim_the_Blighted", "rec_cb": 80, "tier": "Entry"},
    {"name": "Chaos Elemental", "icon": "Chaos_Elemental", "rec_cb": 85, "tier": "Entry"},
    {"name": "Dagannoth Kings", "icon": "Dagannoth_Rex", "rec_cb": 90, "tier": "Entry"},
    {"name": "Hermod, Spirit of War", "icon": "Hermod", "rec_cb": 90, "tier": "Mid-Tier"},
    {"name": "Arch-Glacor (0-5 Mechanics)", "icon": "Arch-Glacor", "rec_cb": 95, "tier": "Mid-Tier"},
    {"name": "Queen Black Dragon", "icon": "Queen_Black_Dragon", "rec_cb": 100, "tier": "Mid-Tier"},
    {"name": "General Graardor (Bandos GWD1)", "icon": "General_Graardor", "rec_cb": 100, "tier": "Mid-Tier"},
    {"name": "K'ril Tsutsaroth (Zamorak GWD1)", "icon": "K'ril_Tsutsaroth", "rec_cb": 100, "tier": "Mid-Tier"},
    {"name": "Commander Zilyana (Saradomin GWD1)", "icon": "Commander_Zilyana", "rec_cb": 100, "tier": "Mid-Tier"},
    {"name": "Kree'arra (Armadyl GWD1)", "icon": "Kree'arra", "rec_cb": 100, "tier": "Mid-Tier"},
    {"name": "Vindicta & Gorvek (GWD2)", "icon": "Vindicta", "rec_cb": 110, "tier": "Mid-Tier"},
    {"name": "Helwyr (GWD2)", "icon": "Helwyr", "rec_cb": 110, "tier": "Mid-Tier"},
    {"name": "Twin Furies (GWD2)", "icon": "Avaryss,_the_Unceasing", "rec_cb": 110, "tier": "Mid-Tier"},
    {"name": "Gregorovic (GWD2)", "icon": "Gregorovic", "rec_cb": 110, "tier": "Mid-Tier"},
    {"name": "Corporeal Beast", "icon": "Corporeal_Beast", "rec_cb": 115, "tier": "Mid-Tier"},
    {"name": "Nex", "icon": "Nex", "rec_cb": 120, "tier": "High-Tier"},
    {"name": "Araxxi / Araxxor", "icon": "Araxxi", "rec_cb": 120, "tier": "High-Tier"},
    {"name": "TzKal-Zuk", "icon": "Igneous_Kal-Zuk", "rec_cb": 125, "tier": "High-Tier"},
    {"name": "Telos, the Warden", "icon": "Telos,_the_Warden", "rec_cb": 125, "tier": "High-Tier"},
    {"name": "Kerapac, the Bound", "icon": "Kerapac", "rec_cb": 125, "tier": "High-Tier"},
    {"name": "Raksha, the Shadow Imperium", "icon": "Raksha", "rec_cb": 128, "tier": "High-Tier"},
    {"name": "Croesus (Skilling Boss)", "icon": "Croesus", "rec_cb": 90, "tier": "Skilling"},
    {"name": "Rasial, the First Necromancer", "icon": "Rasial,_the_First_Necromancer", "rec_cb": 130, "tier": "Endgame"},
    {"name": "Zamorak, Lord of Chaos", "icon": "Zamorak,_Lord_of_Chaos", "rec_cb": 135, "tier": "Endgame"},
    {"name": "Vorago", "icon": "Vorago", "rec_cb": 130, "tier": "Endgame"},
    {"name": "Solak", "icon": "Solak", "rec_cb": 135, "tier": "Endgame"},
    {"name": "Nex: Angel of Death (AoD)", "icon": "Nex", "rec_cb": 135, "tier": "Endgame"},
    {"name": "Beastmaster Durzag (Raids)", "icon": "Beastmaster_Durzag", "rec_cb": 130, "tier": "Endgame"},
    {"name": "Yakamaru (Raids)", "icon": "Yakamaru", "rec_cb": 135, "tier": "Endgame"},
    {"name": "Vorkath & Zemouregal", "icon": "Vorkath", "rec_cb": 135, "tier": "Endgame"}
]

def load_wiki_cache():
    global WIKI_VALID_TITLES, WIKI_CACHE_LOADED
    try:
        if os.path.exists(WIKI_CACHE_FILE):
            with open(WIKI_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                WIKI_VALID_TITLES = set(data)
                WIKI_CACHE_LOADED = True
    except Exception as e:
        print(f"Error loading wiki cache: {e}")

def update_wiki_cache_background():
    """Fetches all valid Wiki titles in a background thread once a week."""
    global WIKI_VALID_TITLES, WIKI_CACHE_LOADED
    try:
        # Check if cache exists and is less than 7 days old
        if os.path.exists(WIKI_CACHE_FILE):
            file_mod_time = os.path.getmtime(WIKI_CACHE_FILE)
            age_seconds = time.time() - file_mod_time
            if age_seconds < (7 * 24 * 60 * 60):
                # Less than 7 days old, just load it
                if not WIKI_CACHE_LOADED:
                    load_wiki_cache()
                return
        
        # We need to fetch/update
        print("Starting weekly background update of RuneScape Wiki links cache...")
        pages = []
        apcontinue = ''
        while True:
            url = f'https://runescape.wiki/api.php?action=query&list=allpages&aplimit=500&apfilterredir=all&format=json'
            if apcontinue:
                url += f'&apcontinue={urllib.parse.quote(apcontinue)}'
            
            res = requests.get(url, headers={'User-Agent': 'RSAgent/1.0'}, timeout=10)
            if res.status_code == 429:
                print("Rate limited by Wiki API, sleeping for 5 seconds...")
                time.sleep(5)
                continue
            
            try:
                data = res.json()
            except ValueError:
                print(f"Failed to parse JSON (Status {res.status_code}). Stopping fetch.")
                break

            # Wiki titles replace underscores with spaces by default. 
            # We lowercase everything to make matching case-insensitive.
            pages.extend([p['title'].lower().replace('_', ' ') for p in data.get('query', {}).get('allpages', [])])
            
            if 'continue' in data:
                apcontinue = data['continue']['apcontinue']
                time.sleep(0.5)  # Be polite to the API
            else:
                break
        
        # Save cache
        with open(WIKI_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(pages, f)
        
        # Update memory
        WIKI_VALID_TITLES = set(pages)
        WIKI_CACHE_LOADED = True
        print(f"Wiki cache updated successfully. {len(pages)} valid links loaded.")
    except Exception as e:
        print(f"Failed to update wiki cache: {e}")
        # Try to load whatever we have
        if not WIKI_CACHE_LOADED:
            load_wiki_cache()

def start_wiki_cache_updater():
    """Starts the wiki cache updater in a background daemon thread."""
    t = threading.Thread(target=update_wiki_cache_background, daemon=True)
    t.start()

def get_most_recent_wiki_links_file() -> str | None:
    """Finds the path to the most recent wiki links / cache file in the working directory."""
    candidates = []
    if os.path.exists("."):
        for fname in os.listdir("."):
            fname_lower = fname.lower()
            if (fname_lower.startswith("wiki") or "wiki_links" in fname_lower or "wiki_cache" in fname_lower) and fname_lower.endswith((".json", ".txt", ".md")):
                candidates.append(fname)
    if not candidates:
        if os.path.exists(WIKI_CACHE_FILE):
            return WIKI_CACHE_FILE
        return None
    candidates.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return candidates[0]

def format_wiki_links_source_block(file_path: str, max_links: int = 3000) -> str:
    """Formats the most recent wiki links file into a structured source block for AI context."""
    if not file_path or not os.path.exists(file_path):
        return ""
    mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
    file_size_kb = os.path.getsize(file_path) / 1024
    
    header = f"ATTACHED WIKI LINKS SOURCE FILE: '{file_path}' (Last Modified: {mod_time}, Size: {file_size_kb:.1f} KB)\n"
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.endswith(".json"):
                data = json.load(f)
                if isinstance(data, list):
                    total_count = len(data)
                    sampled = data[:max_links]
                    links = [f"https://runescape.wiki/w/{urllib.parse.quote(t.replace(' ', '_'))}" for t in sampled if isinstance(t, str)]
                    return (
                        f"{header}"
                        f"Description: Official RuneScape Wiki link cache index containing {total_count:,} indexed wiki page URLs.\n"
                        f"Attached Wiki Link Sources (showing first {len(links):,} valid URLs):\n" +
                        "\n".join(links)
                    )
                elif isinstance(data, dict):
                    return f"{header}\nContent:\n{json.dumps(data, indent=2)[:50000]}"
            content = f.read()
            return f"{header}\nContent:\n{content[:50000]}"
    except Exception as e:
        return f"{header}\n(Error reading file: {e})"


@st.cache_data(ttl=86400)
def check_image_exists(url: str) -> bool:
    """Checks if an image URL exists and returns HTTP 200."""
    try:
        res = requests.head(url, headers={"User-Agent": "RSAgent/1.0"}, allow_redirects=True, timeout=2)
        return res.status_code == 200
    except Exception:
        return False

def extract_player_cb_level(profile_text: str) -> int:
    """Extracts player combat level from profile text (RuneMetrics or RuneApps)."""
    if not profile_text:
        return 100
    match = re.search(r'Combat level:?\s*(\d+)', profile_text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return 100

def get_combat_indicator(player_cb: int, rec_cb: int) -> tuple:
    """Returns (emoji, label) based on player CB vs recommended boss CB."""
    if player_cb >= rec_cb:
        return ("🟢", f"🟢 Fine (Rec. CB: {rec_cb} | Your CB: {player_cb})")
    elif player_cb >= rec_cb - 15:
        return ("🟡", f"🟡 Average / OK (Rec. CB: {rec_cb} | Your CB: {player_cb})")
    else:
        return ("🔴", f"🔴 Under-leveled / Struggle (Rec. CB: {rec_cb} | Your CB: {player_cb})")

def fetch_runemetrics_profile(username: str) -> str | None:
    """Fetches profile, skills, and quest data from official RuneMetrics JSON APIs."""
    if not username:
        return None
    headers = {"User-Agent": "RSAgent/1.0"}
    try:
        prof_url = f"https://apps.runescape.com/runemetrics/profile/profile?user={urllib.parse.quote(username)}&activities=20"
        p_res = requests.get(prof_url, headers=headers, timeout=5)
        if p_res.status_code != 200:
            return None
        p_data = p_res.json()
        if "error" in p_data or "skillvalues" not in p_data:
            return None

        # Fetch Quests via RuneMetrics Quests API
        q_completed = []
        q_started = []
        q_not_started = []
        try:
            quest_url = f"https://apps.runescape.com/runemetrics/quests?user={urllib.parse.quote(username)}"
            q_res = requests.get(quest_url, headers=headers, timeout=5)
            if q_res.status_code == 200:
                q_data = q_res.json()
                for q in q_data.get("quests", []):
                    st_val = q.get("status", "")
                    title = q.get("title", "")
                    if st_val == "COMPLETED":
                        q_completed.append(title)
                    elif st_val == "STARTED":
                        q_started.append(title)
                    elif st_val == "NOT_STARTED":
                        q_not_started.append(title)
        except Exception:
            pass

        # Build clean formatted context text payload
        lines = []
        lines.append(f"SOURCE: Official Jagex RuneMetrics API")
        lines.append(f"Player Name: {p_data.get('name', username)}")
        lines.append(f"Overall Rank: {p_data.get('rank', 'N/A')}")
        lines.append(f"Combat Level: {p_data.get('combatlevel', 100)}")
        lines.append(f"Total Skill: {p_data.get('totalskill', 0)}")
        lines.append(f"Total XP: {p_data.get('totalxp', 0):,}")
        lines.append(f"Quests Complete: {p_data.get('questscomplete', len(q_completed))}")
        lines.append(f"Quests Started: {p_data.get('questsstarted', len(q_started))}")
        lines.append(f"Quests Not Started: {p_data.get('questsnotstarted', len(q_not_started))}")
        lines.append("")
        
        lines.append("=== SKILL LEVELS & XP ===")
        for s in p_data.get("skillvalues", []):
            sid = s.get("id", -1)
            sname = RS3_SKILL_NAMES.get(sid, f"Skill_{sid}")
            lvl = s.get("level", 1)
            xp = int(s.get("xp", 0) / 10)
            rank = s.get("rank", 0)
            lines.append(f"{sname}: Level {lvl} | {xp:,} XP | Rank {rank:,}")
        lines.append("")

        activities = p_data.get("activities", [])
        if activities:
            lines.append("=== RECENT ACTIVITIES LOG ===")
            for act in activities:
                date = act.get("date", "")
                text = act.get("text", "")
                details = act.get("details", "")
                lines.append(f"[{date}] {text} ({details})")
            lines.append("")

        if q_completed:
            lines.append("=== COMPLETED QUESTS ===")
            for qn in q_completed:
                lines.append(f"Quest Complete: {qn}")
            lines.append("")

        return "\n".join(lines)
    except Exception:
        return None

def fetch_runeapps_profile(url: str) -> str:
    """Fallback profile scraper using Playwright on RuneApps."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        text = page.inner_text("body")
        browser.close()
    return f"SOURCE: RuneApps Web Scraper (Fallback 2)\n{text[:15000]}"

def fetch_player_profile(username: str, runeapps_url: str) -> tuple[str, str]:
    """Priority 1: Live RuneMetrics API; Priority 2: Archived Memory File; Priority 3: RuneApps Scraper."""
    # Priority 1: Live RuneMetrics API
    rm_text = fetch_runemetrics_profile(username)
    if rm_text:
        save_account_to_archive(username, rm_text)
        return rm_text, "RuneMetrics API (Priority 1 - Live)"
    
    # Priority 2: Archived Memory File (account_profiles_archive.md)
    archived_text = load_account_from_archive(username)
    if archived_text:
        return archived_text, "Archived Memory File (Priority 2 - Cached RuneMetrics)"
    
    # Priority 3: RuneApps Playwright Web Scraper
    try:
        ra_text = fetch_runeapps_profile(runeapps_url)
        return ra_text, "RuneApps Scraper (Priority 3 - Fallback)"
    except Exception as e:
        return f"Could not fetch profile automatically: {e}", "Error"

@st.cache_data(ttl=86400)
def fetch_slayer_monsters() -> list:
    try:
        url = "https://runescape.wiki/api.php?action=query&list=categorymembers&cmtitle=Category:Slayer_assignments&cmlimit=500&format=json"
        res = requests.get(url, headers={"User-Agent": "RSAgent/1.0"}).json()
        raw_members = [m['title'] for m in res.get('query', {}).get('categorymembers', [])]
        clean_list = []
        for name in raw_members:
            if not name.startswith("Category:"):
                clean_name = name.replace(" (Slayer assignment)", "").strip()
                if clean_name and clean_name not in clean_list:
                    clean_list.append(clean_name)
        return sorted(clean_list)
    except Exception:
        return ["Abyssal demons", "Dark beasts", "Gargoyles", "Airut", "Corrupted creatures", "Ripper demons"]

@st.cache_data(ttl=86400)
def fetch_rs_quests() -> list:
    try:
        url = "https://runescape.wiki/api.php?action=query&list=categorymembers&cmtitle=Category:Quests&cmlimit=500&format=json"
        res = requests.get(url, headers={"User-Agent": "RSAgent/1.0"}).json()
        raw_members = [m['title'] for m in res.get('query', {}).get('categorymembers', [])]
        ignore = {'Quest Overview', 'Quest points', 'QuestHelp', 'Quests', 'Seasonal quests', 'Special quest'}
        clean_list = []
        for name in raw_members:
            if '/' not in name and not name.startswith("Category:") and not name.startswith("List of") and name not in ignore:
                clean_name = name.replace(" (quest)", "").strip()
                if clean_name and clean_name not in clean_list:
                    clean_list.append(clean_name)
        return sorted(clean_list)
    except Exception:
        return ["Desert Treasure II", "Plague's End", "City of Senntisten", "Temple at Senntisten", "World Wakes"]

@st.cache_data(ttl=86400)
def fetch_rs_bosses() -> list:
    wiki_bosses = []
    try:
        url = "https://runescape.wiki/api.php?action=query&list=categorymembers&cmtitle=Category:Bosses&cmlimit=500&format=json"
        res = requests.get(url, headers={"User-Agent": "RSAgent/1.0"}).json()
        raw_members = [m['title'] for m in res.get('query', {}).get('categorymembers', [])]
        ignore = {'Bosses', 'Module:', 'User:', 'Category:'}
        for name in raw_members:
            if '/' not in name and not any(name.startswith(ig) for ig in ignore):
                clean_name = name.replace(" (boss)", "").strip()
                if clean_name and clean_name not in wiki_bosses:
                    wiki_bosses.append(clean_name)
    except Exception:
        pass

    # Merge wiki bosses with catalog
    catalog_names = {b["name"] for b in RS3_BOSS_CATALOG}
    for wb in wiki_bosses:
        if wb not in catalog_names:
            RS3_BOSS_CATALOG.append({"name": wb, "icon": wb.replace(" ", "_"), "rec_cb": 110, "tier": "General"})
            
    return RS3_BOSS_CATALOG

def extract_completed_quests(profile_text: str) -> set:
    """Extracts completed quest names from RuneMetrics, Archive, or RuneApps text."""
    if not profile_text:
        return set()
    
    completed = set()
    lines = profile_text.splitlines()
    for line in lines:
        line_clean = line.strip()
        if "quest complete:" in line_clean.lower():
            q_name = line_clean.split("Quest complete:", 1)[-1].strip()
            if q_name:
                completed.add(q_name.lower())
        elif "completed" in line_clean.lower():
            clean_title = line_clean.rsplit("(", 1)[0].replace("Completed:", "").strip()
            if clean_title:
                completed.add(clean_title.lower())
    return completed

def get_available_quests(all_quests: list, profile_text: str) -> list:
    """Returns only quests from all_quests that have NOT been completed by the player."""
    if not profile_text:
        return all_quests
        
    completed_set = extract_completed_quests(profile_text)
    profile_lower = profile_text.lower()
    
    uncompleted = []
    for q in all_quests:
        q_lower = q.lower()
        if q_lower in completed_set:
            continue
        if f"quest complete: {q_lower}" in profile_lower or f"{q_lower} (completed)" in profile_lower:
            continue
        uncompleted.append(q)
        
    return uncompleted if uncompleted else all_quests

MAJOR_ITEMS_CATALOG = {
    "⚔️ Slayer Helmets & Tier Upgrades": [
        {"id": "slayer_helm_1", "name": "Slayer Helmet", "icon": "Slayer_helmet.png"},
        {"id": "slayer_helm_2", "name": "Reinforced Slayer Helmet", "icon": "Reinforced_slayer_helmet.png"},
        {"id": "slayer_helm_3", "name": "Strong Slayer Helmet", "icon": "Strong_slayer_helmet.png"},
        {"id": "slayer_helm_4", "name": "Mighty Slayer Helmet", "icon": "Mighty_slayer_helmet.png"},
        {"id": "slayer_helm_5", "name": "Full Slayer Helmet", "icon": "Full_slayer_helmet.png"},
        {"id": "slayer_helm_6", "name": "Corrupted Slayer Helmet", "icon": "Corrupted_slayer_helmet.png"},
    ],
    "🛡️ Capes & Combat Milestones": [
        {"id": "cape_fire", "name": "Fire Cape", "icon": "Fire_cape.png"},
        {"id": "cape_kiln_melee", "name": "TokHaar-Kal-Ket (Melee)", "icon": "TokHaar-Kal-Ket.png"},
        {"id": "cape_kiln_range", "name": "TokHaar-Kal-Xil (Ranged)", "icon": "TokHaar-Kal-Xil.png"},
        {"id": "cape_kiln_mage", "name": "TokHaar-Kal-Mej (Magic)", "icon": "TokHaar-Kal-Mej.png"},
        {"id": "cape_zuk_melee", "name": "Igneous Kal-Ket", "icon": "Igneous_Kal-Ket.png"},
        {"id": "cape_zuk_range", "name": "Igneous Kal-Xil", "icon": "Igneous_Kal-Xil.png"},
        {"id": "cape_zuk_mage", "name": "Igneous Kal-Mej", "icon": "Igneous_Kal-Mej.png"},
        {"id": "cape_zuk_hybrid", "name": "Igneous Kal-Zuk", "icon": "Igneous_Kal-Zuk.png"},
    ],
    "💍 Jewelry & Pocket Relics": [
        {"id": "asylum_ring", "name": "Asylum Surgeon's Ring", "icon": "Asylum_surgeon's_ring.png"},
        {"id": "ring_vigour", "name": "Ring of Vigour", "icon": "Ring_of_vigour.png"},
        {"id": "ring_rod", "name": "Ring of Death", "icon": "Ring_of_death.png"},
        {"id": "ring_lotd", "name": "Luck of the Dwarves", "icon": "Luck_of_the_Dwarves.png"},
        {"id": "gote", "name": "Grace of the Elves", "icon": "Grace_of_the_elves.png"},
        {"id": "botg", "name": "Brooch of the Gods", "icon": "Brooch_of_the_Gods.png"},
        {"id": "eof", "name": "Essence of Finality Amulet", "icon": "Essence_of_Finality_amulet.png"},
        {"id": "ritual_shard", "name": "Ancient Elven Ritual Shard", "icon": "Ancient_elven_ritual_shard.png"},
        {"id": "enhanced_excalibur", "name": "Enhanced Excalibur", "icon": "Enhanced_Excalibur.png"},
    ],
    "🦴 Slayer & Skilling Untradeables": [
        {"id": "bonecrusher", "name": "Bonecrusher", "icon": "Bonecrusher.png"},
        {"id": "herbicide", "name": "Herbicide", "icon": "Herbicide.png"},
        {"id": "seedicide", "name": "Seedicide", "icon": "Seedicide.png"},
        {"id": "charming_imp", "name": "Charming Imp", "icon": "Charming_imp.png"},
        {"id": "silverhawk", "name": "Silverhawk Boots", "icon": "Silverhawk_boots.png"},
        {"id": "drakan_medallion", "name": "Drakan's Medallion", "icon": "Drakan's_medallion.png"},
        {"id": "sixth_age_circuit", "name": "Sixth-Age Circuit", "icon": "Sixth-Age_circuit.png"},
    ],
    "⛏️ BiS Tools & Endgame Gear": [
        {"id": "pickaxe_life_death", "name": "Pickaxe of Life and Death", "icon": "Pickaxe_of_Life_and_Death.png"},
        {"id": "mattock_time_space", "name": "Mattock of Time and Space", "icon": "Mattock_of_Time_and_Space.png"},
        {"id": "mw_spear", "name": "Masterwork Spear of Annihilation", "icon": "Masterwork_spear_of_annihilation.png"},
        {"id": "fsoa", "name": "Fractured Staff of Armadyl", "icon": "Fractured_Staff_of_Armadyl.png"},
        {"id": "botlg", "name": "Bow of the Last Guardian", "icon": "Bow_of_the_Last_Guardian.png"},
    ]
}

def get_owned_items_memory(owned_ids: list) -> str:
    if not owned_ids: return "PLAYER UNLOCKED ITEMS: None specified yet."
    owned_names = []
    for cat, items in MAJOR_ITEMS_CATALOG.items():
        for item in items:
            if item["id"] in owned_ids:
                owned_names.append(item["name"])
    return "PLAYER UNLOCKED MAJOR ITEMS:\nThe user currently owns the following major items & upgrades: " + ", ".join(owned_names)

def get_todo_memory(todo_tasks: list) -> str:
    """Formats active (uncompleted) player To-Do tasks for the LLM context."""
    active_tasks = [t["text"] for t in todo_tasks if not t.get("completed", False)]
    if not active_tasks:
        return "PLAYER ACTIVE TO-DO TASKS: No active tasks currently listed."
    return "PLAYER ACTIVE TO-DO TASKS & GOALS:\n" + "\n".join([f"- {t}" for t in active_tasks])

def get_favorite_bosses_memory(fav_bosses: list) -> str:
    """Formats favorite boss targets for the LLM context."""
    if not fav_bosses:
        return "PLAYER FAVORITE BOSSES: None specified yet."
    return "PLAYER FAVORITE BOSS TARGETS:\nThe user actively targets and bosses: " + ", ".join(fav_bosses)

def load_past_session_memories(max_sessions=3) -> str:
    if not os.path.exists("./sessions"): return ""
    files = sorted([f for f in os.listdir("./sessions") if f.startswith("session_") and f.endswith(".json")], reverse=True)
    recent_files = files[1:max_sessions+1] # Skip active session
    memories = []
    for fname in recent_files:
        try:
            with open(os.path.join("./sessions", fname), "r") as f:
                data = json.load(f)
                user_msgs = [m["content"] for m in data if m.get("role") == "user"]
                if user_msgs:
                    session_date = fname.replace("session_", "").replace(".json", "")
                    memories.append(f"- Session ({session_date}): Focused on '{user_msgs[0][:100]}...'")
        except Exception:
            pass
    return "\n".join(memories) if memories else ""

def fetch_rs_wiki_info(query: str) -> str:
    if not query.strip(): return ""
    formatted_query = urllib.parse.quote(query.strip())
    api_url = f"https://runescape.wiki/api.php?action=query&prop=extracts&exintro&explaintext&redirects=1&titles={formatted_query}&format=json"
    try:
        res = requests.get(api_url, headers={"User-Agent": "RSAgent/1.0"}).json()
        pages = res.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id != "-1":
                title = page_data.get("title", "")
                return f"WIKI DATA '{title}':\nURL: https://runescape.wiki/w/{urllib.parse.quote(title)}\nSummary: {page_data.get('extract', '')[:3000]}"
        return f"No exact Wiki entry found for '{query}'"
    except Exception as e:
        return f"Error querying Wiki: {e}"

@st.cache_data(ttl=300)
def fetch_ge_prices(items) -> dict:
    if isinstance(items, list):
        items = "|".join(items)
    
    encoded_query = urllib.parse.quote(items)
    url = f"https://api.weirdgloop.org/exchange/history/rs/latest?name={encoded_query}"
    
    try:
        res = requests.get(url, headers={"User-Agent": "RSAgent/1.0"}, timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {}

def extract_ge_context_from_prompt(user_prompt: str) -> str:
    common_items = [
        "necroplasm", "powerful necroplasm", "greater necroplasm", "lesser necroplasm",
        "pure essence", "rune essence", "water rune", "blood rune", "incandescent energy",
        "chronotes", "feather", "vulnerability bomb", "saradomin brew", "super restore",
        "overload", "herblore"
    ]
    
    found_items = [item for item in common_items if item in user_prompt.lower()]
    
    if found_items:
        prices_data = fetch_ge_prices(found_items)
        if prices_data:
            lines = ["LIVE GRAND EXCHANGE MARKET PRICES (REAL-TIME):"]
            for item, data in prices_data.items():
                if not isinstance(data, dict):
                    continue
                price = data.get("price", "Unknown")
                volume = data.get("volume", "Unknown")
                if isinstance(price, (int, float)):
                    price = f"{price:,}"
                if isinstance(volume, (int, float)):
                    volume = f"{volume:,}"
                lines.append(f"- {item}: {price} GP (Daily Volume: {volume})")
            if len(lines) > 1:
                return "\n".join(lines)
    
    return ""

def verify_wiki_urls(text: str) -> str:
    """Scans text for RuneScape wiki URLs and flags non-existent ones using the local cache."""
    urls = set(re.findall(r'https://runescape\.wiki/w/[^\s\"\'\]]+', text))
    for raw_url in urls:
        clean_url = raw_url
        while clean_url.endswith((')', '.', ',', '!', '?')):
            if clean_url.endswith(')'):
                if clean_url.count('(') >= clean_url.count(')'):
                    break
            clean_url = clean_url[:-1]
        
        # Extract title from URL (e.g. https://runescape.wiki/w/Noxious_scythe -> Noxious_scythe)
        title_part = clean_url.split('/w/')[-1]
        # Wiki URL decoding and normalisation
        title_decoded = urllib.parse.unquote(title_part)
        title_normalized = title_decoded.replace('_', ' ').lower()
        
        if WIKI_CACHE_LOADED and WIKI_VALID_TITLES:
            if title_normalized not in WIKI_VALID_TITLES:
                text = text.replace(clean_url, f"{clean_url} (⚠️ WARNING: This Wiki page does not exist)")
        else:
            # Fallback to HTTP if cache not loaded yet
            try:
                res = requests.get(clean_url, headers={"User-Agent": "RSAgent/1.0"}, timeout=3)
                if res.status_code == 404 or "Nothing interesting happens" in res.text:
                    text = text.replace(clean_url, f"{clean_url} (⚠️ WARNING: This Wiki page does not exist)")
            except Exception:
                pass
    return text

st.set_page_config(page_title="RS Helper", page_icon="⚔️", layout="wide")

if 'wiki_cache_started' not in st.session_state:
    start_wiki_cache_updater()
    st.session_state['wiki_cache_started'] = True

# Custom CSS for Collapsed Sidebar Protrusion, Full Screen Responsiveness & Dynamic Heights
st.markdown("""
<style>
/* Responsive layout adjustments - Maximize screen usage */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 99% !important;
}

/* Ensure container parent elements allow height expansion */
div[data-testid="stElementContainer"]:has(div[data-testid="stVerticalBlockBorderWrapper"]) {
    height: 100% !important;
    flex: 1 1 auto !important;
}

/* Dynamically size fixed-height scroll containers to fill user viewport height */
div[data-testid="stVerticalBlockBorderWrapper"] {
    height: calc(100vh - 240px) !important;
    min-height: 480px !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] > div,
div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"],
div[data-testid="stVerticalBlockBorderWrapper"] div[style*="height"] {
    height: 100% !important;
    min-height: 100% !important;
    max-height: calc(100vh - 240px) !important;
}

/* Smooth chat input margins */
[data-testid="stChatInput"] {
    margin-top: 0.5rem !important;
}

/* Sidebar Handle styling */
[data-testid="stSidebarCollapsedControl"] {
    background: linear-gradient(135deg, #d4af37 0%, #b8860b 100%) !important;
    border-radius: 0 12px 12px 0 !important;
    box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.5) !important;
    border: 1px solid #ffd700 !important;
    margin-left: -4px !important;
    transition: all 0.3s ease !important;
}
[data-testid="stSidebarCollapsedControl"]:hover {
    transform: scale(1.15) translateX(3px) !important;
    box-shadow: 3px 3px 15px rgba(212, 175, 55, 0.8) !important;
}
[data-testid="stSidebarCollapsedControl"] button {
    color: #000000 !important;
}
</style>
""", unsafe_allow_html=True)

# Live JS Window Resizer & Clipboard Image Paste Handler for Streamlit Containers
components.html("""
<script>
function resizeChatContainers() {
    try {
        const pDoc = window.parent.document;
        const containers = pDoc.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]');
        const viewHeight = window.parent.innerHeight;
        const targetHeight = Math.max(450, viewHeight - 240);
        
        containers.forEach(box => {
            box.style.height = targetHeight + 'px';
            box.style.maxHeight = targetHeight + 'px';
            const childDivs = box.querySelectorAll('div');
            childDivs.forEach(d => {
                if (d.style.height || d.style.maxHeight || d.getAttribute('data-testid') === 'stVerticalBlock') {
                    d.style.height = targetHeight + 'px';
                    d.style.maxHeight = targetHeight + 'px';
                }
            });
        });
    } catch(e) {}
}

function sendPastedFileToUploader(file) {
    try {
        const pDoc = window.parent.document;
        const fileInputs = pDoc.querySelectorAll('input[type="file"]');
        if (fileInputs && fileInputs.length > 0) {
            const fileInput = fileInputs[fileInputs.length - 1];
            const dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
    } catch(e) {}
    return false;
}

function sendPastedImageToStreamlit(dataUrl) {
    try {
        const pDoc = window.parent.document;
        const inputEl = pDoc.querySelector('input[aria-label="pasted_img"]');
        if (inputEl) {
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(inputEl, dataUrl);
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            inputEl.dispatchEvent(new Event('change', { bubbles: true }));
        }
    } catch(e) {}
}

function setupPasteListener() {
    try {
        const pDoc = window.parent.document;
        if (pDoc._rsPasteListenerAttached) return;
        pDoc._rsPasteListenerAttached = true;
        
        pDoc.addEventListener('paste', function(e) {
            const clipboardData = e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData);
            if (!clipboardData) return;
            const items = clipboardData.items;
            if (!items) return;
            for (let i = 0; i < items.length; i++) {
                if (items[i].type && items[i].type.indexOf('image') === 0) {
                    const blob = items[i].getAsFile();
                    if (!blob) continue;
                    
                    const ext = items[i].type.split('/')[1] || 'png';
                    const file = new File([blob], `Pasted_Image_${Date.now()}.${ext}`, { type: items[i].type });
                    
                    const injected = sendPastedFileToUploader(file);
                    if (!injected) {
                        const reader = new FileReader();
                        reader.onload = function(evt) {
                            sendPastedImageToStreamlit(evt.target.result);
                        };
                        reader.readAsDataURL(blob);
                    }
                    break;
                }
            }
        });
    } catch(e) {}
}

if (window.parent) {
    window.parent.addEventListener('resize', resizeChatContainers);
    setInterval(resizeChatContainers, 300);
    setupPasteListener();
    setInterval(setupPasteListener, 1000);
}
</script>
""", height=0, width=0)

settings = load_settings()

# Dialog Modals (guaranteed to close cleanly upon rerun)
@st.dialog("🧭 Quest Assistant")
def quest_dialog():
    all_quests = fetch_rs_quests()
    available_quests = get_available_quests(all_quests, st.session_state.get("profile_data", ""))
    st.caption(f"Showing {len(available_quests)} uncompleted quests for active profile.")
    quest_name = st.selectbox("Select Quest", available_quests)
    if st.button("Paste Quest Prompt", use_container_width=True):
        st.session_state.pending_chat_prompt = f"I am doing the '{quest_name}' quest, please assist me with prerequisites, step-by-step walkthrough, puzzle solutions, and recommended items."
        st.rerun()


@st.dialog("⚔️ Bossing Strategy Assistant")
def boss_dialog():
    all_boss_data = fetch_rs_bosses()
    fav_bosses = settings.get("favorite_bosses", [])
    player_cb = extract_player_cb_level(st.session_state.get("profile_data", ""))
    
    # Sort with favorites pinned at top
    fav_items = [b for b in all_boss_data if b["name"] in fav_bosses]
    other_items = [b for b in all_boss_data if b["name"] not in fav_bosses]
    sorted_catalog = fav_items + other_items
    
    options_map = {}
    options_labels = []
    for b in sorted_catalog:
        emoji, _ = get_combat_indicator(player_cb, b["rec_cb"])
        prefix = "⭐ " if b["name"] in fav_bosses else ""
        label = f"{prefix}{emoji} {b['name']} (Rec. CB: {b['rec_cb']})"
        options_labels.append(label)
        options_map[label] = b

    selected_label = st.selectbox("Select Boss (⭐ Pinned Favorites at top)", options_labels)
    selected_boss = options_map[selected_label]
    boss_name = selected_boss["name"]
    rec_cb = selected_boss["rec_cb"]
    
    col1, col2 = st.columns([1, 3])
    with col1:
        img_url = f"https://runescape.wiki/w/Special:Filepath/{selected_boss['icon']}.png"
        if check_image_exists(img_url):
            st.image(img_url, width=85)
        else:
            st.caption("[No image]")
    with col2:
        emoji, status_text = get_combat_indicator(player_cb, rec_cb)
        st.markdown(f"**Status**: {status_text}")
        
        is_fav = boss_name in fav_bosses
        fav_label = "⭐ Remove Favorite" if is_fav else "⭐ Mark as Favorite"
        if st.button(fav_label, use_container_width=True):
            if is_fav:
                fav_bosses.remove(boss_name)
            else:
                fav_bosses.append(boss_name)
            settings["favorite_bosses"] = fav_bosses
            save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), settings.get("custom_instructions", ""), settings.get("owned_items", []), settings.get("todo_tasks", []), fav_bosses)
            st.toast(f"Updated favorites for '{boss_name}'", icon="⭐")
            st.rerun()

    st.markdown("---")
    if st.button("Paste Bossing Prompt", use_container_width=True):
        st.session_state.pending_chat_prompt = f"I am planning to fight {boss_name}. Please provide a detailed boss guide including: 1. Minimum & recommended gear setup 2. Key mechanics & phase breakdowns 3. Inventory & supply setup 4. Tips for beginner/intermediate kills."
        st.rerun()

@st.dialog("⚔️ Slayer Task Helper")
def slayer_dialog():
    monsters = fetch_slayer_monsters()
    monster = st.selectbox("Select Slayer Monster", monsters)
    qty = st.number_input("Task Count", min_value=1, value=150, step=1)
    master = st.selectbox("Slayer Master", ["None", "Laniakea", "Kuradal", "Raptor", "Morvran", "Sumona", "Spria", "Mandrith"])
    if st.button("Paste Slayer Prompt", use_container_width=True):
        master_str = f" from {master}" if master != "None" else ""
        prompt_text = f"I have been assigned a Slayer task of {qty}x {monster}{master_str}. Please provide a detailed guide including: 1. Location & how to get there 2. Recommended gear & inventory setup 3. Special mechanics/weaknesses 4. Strategy to complete the task efficiently."
        st.session_state.pending_chat_prompt = prompt_text
        st.rerun()

@st.dialog("➕ Add Custom Prompt")
def custom_prompt_dialog():
    new_prompt_name = st.text_input("Button Label (e.g. 'Boss Guide')")
    new_prompt_text = st.text_area("Prompt Text")
    if st.button("Save Prompt", use_container_width=True) and new_prompt_name and new_prompt_text:
        custom_prompts = settings.get("custom_prompts", [])
        custom_prompts.append({"name": new_prompt_name, "text": new_prompt_text})
        settings["custom_prompts"] = custom_prompts
        save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), custom_prompts, settings.get("custom_instructions", ""), settings.get("owned_items", []), settings.get("todo_tasks", []), settings.get("favorite_bosses", []))
        st.toast("Prompt saved!", icon="✅")
        st.rerun()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = bool(settings.get("gemini_api_key") or settings.get("openai_api_key"))

if not st.session_state.logged_in:
    st.title("⚙️ Agent Setup & Login")
    st.write("Configure your credentials below (Provide at least one API key)")
    
    with st.form("login_form"):
        rs_input = st.text_input("RuneScape Username", value=settings.get("rs_username", ""))
        gemini_input = st.text_input("Gemini API Key", value=settings.get("gemini_api_key", ""), type="password")
        openai_input = st.text_input("ChatGPT (OpenAI) API Key", value=settings.get("openai_api_key", ""), type="password")
        
        if st.form_submit_button("Save & Launch Agent"):
            if gemini_input.strip() or openai_input.strip():
                rs_user = rs_input.strip()
                saved_accs = settings.get("saved_accounts", [])
                if rs_user and rs_user not in saved_accs:
                    saved_accs.append(rs_user)
                save_settings(gemini_input.strip(), openai_input.strip(), rs_user, saved_accs)
                st.session_state.logged_in = True
                if "profile_data" in st.session_state:
                    del st.session_state["profile_data"]
                st.rerun()
            else:
                st.error("At least one API Key (Gemini or OpenAI) is required")
else:
    st.title("⚔️ RS Helper")
    
    rs_username = settings.get("rs_username", "Unknown Player")
    default_url = f"https://runeapps.org/player/{rs_username}" if rs_username else "https://runeapps.org/player/rozraid"

    SYSTEM_INSTRUCTION = load_agent_instructions(rs_username)

    # Session Logging Initialization
    if "session_log_file" not in st.session_state:
        os.makedirs("./sessions", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        st.session_state.session_log_file = f"./sessions/session_{timestamp}.json"

    def log_interaction(role, content, model=None, images=None):
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "role": role,
            "content": content
        }
        if model:
            log_entry["model"] = model
        if images:
            log_entry["images"] = images

            
        log_data = []
        if os.path.exists(st.session_state.session_log_file):
            with open(st.session_state.session_log_file, "r") as f:
                try:
                    log_data = json.load(f)
                except json.JSONDecodeError:
                    pass
                
        log_data.append(log_entry)
        
        with open(st.session_state.session_log_file, "w") as f:
            json.dump(log_data, f, indent=4)

    # Startup auto-fetch (Priority 1: Live RuneMetrics API; Priority 2: Archived Memory File; Priority 3: RuneApps)
    if "profile_data" not in st.session_state or "profile_source" not in st.session_state:
        with st.spinner(f"Loading profile data for '{rs_username}'..."):
            prof_data, source_label = fetch_player_profile(rs_username, default_url)
            st.session_state.profile_data = prof_data
            st.session_state.profile_source = source_label
            if "Priority 1" in source_label:
                st.toast(f"Profile loaded via RuneMetrics API!", icon="⚔️")
            elif "Priority 2" in source_label:
                st.toast(f"Loaded via Archived Memory File", icon="📜")
            else:
                st.toast(f"Loaded via RuneApps (Fallback)", icon="🌐")

    with st.sidebar:
        st.header("Agent Configuration")
        
        # Multi-Account Selection & Management
        saved_accounts = settings.get("saved_accounts", [])
        if rs_username not in saved_accounts and rs_username:
            saved_accounts.append(rs_username)
            save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), rs_username, saved_accounts)
            
        selected_account = st.selectbox("Select Account", saved_accounts, index=saved_accounts.index(rs_username) if rs_username in saved_accounts else 0)
        
        if selected_account != rs_username:
            settings["rs_username"] = selected_account
            save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), selected_account, settings.get("saved_accounts", []))
            if "profile_data" in st.session_state:
                del st.session_state["profile_data"]
            if "profile_source" in st.session_state:
                del st.session_state["profile_source"]
            st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            with st.popover("➕ Add Account"):
                new_acc = st.text_input("New Username")
                if st.button("Add") and new_acc:
                    if new_acc not in saved_accounts:
                        saved_accounts.append(new_acc)
                        settings["saved_accounts"] = saved_accounts
                        settings["rs_username"] = new_acc
                        save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), new_acc, saved_accounts)
                        if "profile_data" in st.session_state:
                            del st.session_state["profile_data"]
                        if "profile_source" in st.session_state:
                            del st.session_state["profile_source"]
                        st.rerun()
        with col2:
            if st.button("❌ Forget") and selected_account:
                if selected_account in saved_accounts:
                    saved_accounts.remove(selected_account)
                    settings["saved_accounts"] = saved_accounts
                    new_active = saved_accounts[0] if saved_accounts else ""
                    settings["rs_username"] = new_active
                    save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), new_active, saved_accounts)
                    if "profile_data" in st.session_state:
                        del st.session_state["profile_data"]
                    if "profile_source" in st.session_state:
                        del st.session_state["profile_source"]
                    st.rerun()

        active_model = st.radio(
            "Select AI Model",
            ["Gemini 3.6 Flash", "ChatGPT (GPT-4o)"]
        )
        
        st.markdown("---")
        if st.button("🔄 Refresh Profile Data"):
            with st.spinner("Refreshing profile data..."):
                prof_data, source_label = fetch_player_profile(rs_username, default_url)
                st.session_state.profile_data = prof_data
                st.session_state.profile_source = source_label
                st.toast(f"Refreshed: {source_label}", icon="✅")
                st.rerun()

        with st.popover("📜 View Session Logs"):
            st.write("### Session History")
            log_files = [f for f in os.listdir("./sessions") if f.startswith("session_") and f.endswith(".json")]
            log_files.sort(reverse=True)
            if log_files:
                selected_log = st.selectbox("Select Session", log_files)
                if selected_log:
                    with open(os.path.join("./sessions", selected_log), "r") as f:
                        try:
                            log_content = json.load(f)
                            st.write(f"Messages: {len(log_content)}")
                            with st.expander("View Log Content"):
                                for entry in log_content:
                                    st.markdown(f"**{entry.get('role', 'unknown').title()}** ({entry.get('timestamp', '')})")
                                    st.markdown(entry.get('content', ''))
                                    st.markdown("---")
                            if st.button("Reload Session History"):
                                st.session_state.messages = log_content
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error loading log: {e}")
            else:
                st.info("No session logs found.")

        with st.popover("⚙️ Agent Instructions"):
            st.write("### Base System Instructions")
            st.caption("Editing updates `agent_instructions.md` directly.")
            current_base = ""
            if os.path.exists(INSTRUCTIONS_FILE):
                with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
                    current_base = f.read()
            base_inst_input = st.text_area("Base Instructions (agent_instructions.md)", value=current_base, height=200)
            
            st.write("### User Custom Instructions")
            st.caption("Personal guidelines (e.g. 'I am an Ironman account').")
            custom_inst_input = st.text_area("Custom Guidelines", value=settings.get("custom_instructions", ""), height=100)
            
            if st.button("Save All Instructions"):
                with open(INSTRUCTIONS_FILE, "w", encoding="utf-8") as f:
                    f.write(base_inst_input)
                settings["custom_instructions"] = custom_inst_input
                save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), custom_inst_input, settings.get("owned_items", []), settings.get("todo_tasks", []), settings.get("favorite_bosses", []))
                st.toast("Agent instructions saved!", icon="✅")
                st.rerun()

        
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
            
        if st.button("Logout / Edit Settings"):
            st.session_state.logged_in = False
            if "profile_data" in st.session_state:
                del st.session_state["profile_data"]
            if "profile_source" in st.session_state:
                del st.session_state["profile_source"]
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "attached_images" not in st.session_state:
        st.session_state.attached_images = []
    if "uploader_key_id" not in st.session_state:
        st.session_state.uploader_key_id = 0

    # --- UI TABS ---
    tab_chat, tab_profile, tab_wiki, tab_items = st.tabs(["💬 Chat Agent", "👤 My RuneScape Profile", "🌐 Wiki Browser", "🎒 Major Items"])

    
    with tab_profile:
        st.subheader(f"🌐 Live Profile View: {rs_username}")
        source_lbl = st.session_state.get("profile_source", "Unknown Source")
        if "Priority 1" in source_lbl:
            st.success(f"📊 Active Profile Data: **{source_lbl}**")
        elif "Priority 2" in source_lbl:
            st.info(f"📊 Active Profile Data: **{source_lbl}**")
        else:
            st.warning(f"📊 Active Profile Data: **{source_lbl}**")
            
        prof_text = st.session_state.get("profile_data", "")
        if prof_text:
            import re
            
            # Extract summary data
            cb_match = re.search(r"Combat Level:\s*(\d+)", prof_text)
            total_sk_match = re.search(r"Total Skill:\s*(\d+)", prof_text)
            total_xp_match = re.search(r"Total XP:\s*([\d,]+)", prof_text)
            quests_match = re.search(r"Quests Complete:\s*(\d+)", prof_text)
            
            cb = cb_match.group(1) if cb_match else "N/A"
            total_sk = total_sk_match.group(1) if total_sk_match else "N/A"
            total_xp = total_xp_match.group(1) if total_xp_match else "N/A"
            quests = quests_match.group(1) if quests_match else "N/A"
            
            # Summary Cards
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("⚔️ Combat Level", cb)
            col2.metric("🏆 Total Skill", total_sk)
            col3.metric("✨ Total XP", total_xp)
            col4.metric("📜 Quests Complete", quests)
            
            st.markdown("---")
            st.subheader("🎯 Skill Matrix")
            
            # Extract Skills
            skills_section = re.search(r"=== SKILL LEVELS & XP ===\n(.*?)(?:\n\n===|$)", prof_text, re.DOTALL)
            if skills_section:
                skills_lines = skills_section.group(1).strip().split("\n")
                skill_cols = st.columns(4)
                for idx, sl in enumerate(skills_lines):
                    if ":" in sl:
                        sname, sdata = sl.split(":", 1)
                        with skill_cols[idx % 4]:
                            st.markdown(f"**{sname.strip()}**: {sdata.strip().split('|')[0].strip()}")
            
            # Extract Activities
            acts_section = re.search(r"=== RECENT ACTIVITIES LOG ===\n(.*?)(?:\n\n===|$)", prof_text, re.DOTALL)
            if acts_section:
                st.markdown("---")
                st.subheader("📅 Recent Activity")
                acts_lines = acts_section.group(1).strip().split("\n")
                for al in acts_lines[:10]: # show top 10
                    st.text(al)
                    
        with st.expander("🔍 Inspect Active AI Profile Context Payload"):
            st.caption("This is the exact profile context provided to Gemini/ChatGPT during chat")
            st.text_area("Profile Text Data", prof_text or "No data loaded yet.", height=350)

    with tab_wiki:
        st.subheader("🌐 Interactive Wiki Explorer")
        
        wiki_query = st.text_input("Search RuneScape Wiki (Press Enter to search)", placeholder="e.g. Abyssal demon, Noxious scythe...")
        
        if wiki_query:
            with st.spinner("Searching Wiki API..."):
                result = fetch_rs_wiki_info(wiki_query)
                if result.startswith("WIKI DATA"):
                    try:
                        lines = result.split("\n", 2)
                        title = lines[0].replace("WIKI DATA '", "").rstrip("':")
                        wiki_url = lines[1].replace("URL: ", "").strip()
                        summary = lines[2].replace("Summary: ", "").strip()
                        
                        st.markdown(f"### {title}")
                        st.info(summary)
                        st.link_button(f"↗️ Open '{title}' on RuneScape Wiki", wiki_url)
                    except Exception as e:
                        st.error("Failed to parse wiki data.")
                else:
                    st.warning(result)
                    
        st.markdown("---")
        with st.expander("💰 Live GE Price Lookup", expanded=False):
            ge_search = st.text_input("Enter item name(s) separated by pipe (e.g. Water rune|Pure essence)")
            if ge_search:
                with st.spinner("Fetching live prices..."):
                    ge_data = fetch_ge_prices(ge_search)
                    if ge_data:
                        for item_name, info in ge_data.items():
                            price = info.get('price', 0)
                            volume = info.get('volume', 0)
                            timestamp = info.get('timestamp', 'Unknown')
                            st.markdown(f"**{item_name}**")
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Price", f"{price:,} GP" if isinstance(price, int) else price)
                            c2.metric("Volume", f"{volume:,}" if isinstance(volume, int) else volume)
                            c3.metric("Last Updated", timestamp)
                            st.divider()
                    else:
                        st.warning("No price data found for the given item(s).")

        st.markdown("---")
        st.subheader("⚡ Quick Links Hub")
        
        # Popular Wiki hubs
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.link_button("📜 Quests", "https://runescape.wiki/w/Quests", use_container_width=True)
        with col2:
            st.link_button("💰 Money Making", "https://runescape.wiki/w/Money_making_guide", use_container_width=True)
        with col3:
            st.link_button("🎯 Skill Guides", "https://runescape.wiki/w/Skill_training_guides", use_container_width=True)
        with col4:
            st.link_button("📈 GE Prices", "https://runescape.wiki/w/Grand_Exchange", use_container_width=True)
        with col5:
            st.link_button("📅 Daily Distractions", "https://runescape.wiki/w/Distractions_and_Diversions", use_container_width=True)

    with tab_items:
        st.subheader("🎒 Major Items & Upgrades Tracker")
        st.write("Track your major account unlocks. This helps the AI suggest strategies tailored to your gear.")
        
        if "staged_owned_items" not in st.session_state:
            st.session_state.staged_owned_items = list(settings.get("owned_items", []))
            
        staged_items = st.session_state.staged_owned_items
        total_items = sum(len(items) for items in MAJOR_ITEMS_CATALOG.values())
        owned_count = len(staged_items)
        progress = (owned_count / total_items) if total_items > 0 else 0.0
        
        st.progress(progress, text=f"Unlocks Tracker: {owned_count} / {total_items} Major Items Owned ({int(progress*100)}%)")
        
        for category, items in MAJOR_ITEMS_CATALOG.items():
            st.markdown(f"#### {category}")
            item_cols = st.columns(len(items) if len(items) > 0 else 1)
            for idx, item in enumerate(items):
                with item_cols[idx % len(item_cols)]:
                    img_url = f"https://runescape.wiki/w/Special:Filepath/{item['icon']}"
                    if check_image_exists(img_url):
                        st.image(img_url, width=40)
                    else:
                        st.caption("[No image]")
                    
                    is_owned = st.checkbox(item["name"], value=(item["id"] in staged_items), key=f"item_stage_{item['id']}")
                    if is_owned and item["id"] not in staged_items:
                        staged_items.append(item["id"])
                    elif not is_owned and item["id"] in staged_items:
                        staged_items.remove(item["id"])

        st.markdown("---")
        if st.button("💾 Save Gear Setup", use_container_width=True, type="primary"):
            settings["owned_items"] = list(staged_items)
            save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), settings.get("custom_instructions", ""), list(staged_items), settings.get("todo_tasks", []), settings.get("favorite_bosses", []))
            st.success("Gear setup saved successfully!")
            st.rerun()
        st.markdown("---")

    with tab_chat:
        show_todo = st.toggle("📋 To-Do & Task Manager", value=st.session_state.get("show_todo", False), key="show_todo_toggle")
        
        if show_todo:
            col_chat, col_todo = st.columns([3, 2])
        else:
            col_chat = st.container()
            col_todo = None
            
        with col_chat:
            # Custom CSS to hide background fallback sync input
            st.markdown("""
            <style>
            div[data-testid="stTextInput"]:has(input[aria-label="pasted_img"]) {
                display: none !important;
            }
            div[data-testid="stFileUploader"] {
                padding: 0 !important;
            }
            div[data-testid="stFileUploader"] section {
                padding: 0.4rem 0.8rem !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # Hidden input field for capturing Javascript-pasted images from clipboard (Fallback)
            pasted_img_val = st.text_input("pasted_img", key="pasted_img_data", label_visibility="collapsed")

            if pasted_img_val:
                try:
                    if "," in pasted_img_val:
                        header, b64_str = pasted_img_val.split(",", 1)
                        mime = header.split(";")[0].replace("data:", "")
                    else:
                        mime = "image/png"
                        b64_str = pasted_img_val
                    img_bytes = base64.b64decode(b64_str)
                    st.session_state.attached_images.append({
                        "bytes": img_bytes,
                        "mime": mime,
                        "name": f"Pasted_Image_{len(st.session_state.attached_images)+1}.png"
                    })
                    st.toast("Clipboard image attached!", icon="📋")
                except Exception as e:
                    st.error(f"Failed to process pasted image: {e}")
                st.session_state.pasted_img_data = ""
                st.rerun()

            # 1. Chat Conversation History
            if not st.session_state.messages:
                with st.container(height=680):
                    st.info("👋 Welcome to RS Helper! Type a message below or use a Quick Prompt to start.")
            else:
                with st.container(height=680):
                    for idx, message in enumerate(st.session_state.messages):
                        if idx == len(st.session_state.messages) - 1 and message["role"] == "assistant":
                            st.markdown("<div id='latest-assistant-response'></div>", unsafe_allow_html=True)
                        with st.chat_message(message["role"]):
                            st.markdown(message["content"])
                            if message.get("images"):
                                img_cols = st.columns(min(len(message["images"]), 4))
                                for img_idx, img_info in enumerate(message["images"]):
                                    with img_cols[img_idx % 4]:
                                        try:
                                            b64 = img_info.get("bytes_b64", "")
                                            if b64:
                                                st.image(base64.b64decode(b64), caption=img_info.get("name", "Attachment"), use_container_width=True)
                                        except Exception:
                                            pass
                
                if st.session_state.get("just_responded", False):
                    components.html(
                        """
                        <script>
                            setTimeout(() => {
                                const target = window.parent.document.getElementById('latest-assistant-response');
                                if (target) {
                                    target.scrollIntoView({behavior: 'smooth', block: 'start'});
                                }
                            }, 150);
                        </script>
                        """, height=0, width=0
                    )
                    st.session_state.just_responded = False

            # 2. Unified Command Dock (Above Chat Input)
            st.markdown("---")
            
            st.markdown("""
            <style>
            /* Hide the file uploader limits text and slim down the container */
            [data-testid="stFileUploadDropzone"] small {
                display: none !important;
            }
            [data-testid="stFileUploaderDropzoneInstructions"] {
                display: none !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            def render_uploader_widget():
                active_uploader_key = f"file_uploader_key_{st.session_state.uploader_key_id}"
                uploaded_files = st.file_uploader(
                    "📎 Upload Image(s)", 
                    type=["png", "jpg", "jpeg", "webp"], 
                    accept_multiple_files=True, 
                    key=active_uploader_key,
                    label_visibility="collapsed"
                )
                if uploaded_files:
                    new_added = False
                    for uf in uploaded_files:
                        img_bytes = uf.read()
                        if not any(img["name"] == uf.name and len(img["bytes"]) == len(img_bytes) for img in st.session_state.attached_images):
                            st.session_state.attached_images.append({
                                "bytes": img_bytes,
                                "mime": uf.type or "image/png",
                                "name": uf.name
                            })
                            new_added = True
                    if new_added:
                        st.toast("Image attachment(s) added!", icon="📎")

            # Action Chips & Upload in a single row
            # Upload column is slightly wider (1.5) to make it distinct and larger
            action_cols = st.columns([1.5, 1, 1, 1, 1, 1, 1])
            
            with action_cols[0]:
                render_uploader_widget()
                
            with action_cols[1]:
                if st.button("🎯 Goal", use_container_width=True): 
                    st.session_state.pending_chat_prompt = "In today's session, I am focusing on: "
            with action_cols[2]:
                if st.button("🧭 Quest", use_container_width=True):
                    quest_dialog()
            with action_cols[3]:
                if st.button("⚔️ Bossing", use_container_width=True): 
                    boss_dialog()
            with action_cols[4]:
                if st.button("🛡️ Slayer", use_container_width=True):
                    slayer_dialog()
            with action_cols[5]:
                if st.button("➕ Custom", use_container_width=True):
                    custom_prompt_dialog()
            
            custom_prompts = settings.get("custom_prompts", [])
            if custom_prompts:
                with action_cols[6]:
                    with st.popover("🔖 Saved", use_container_width=True):
                        for idx, cp in enumerate(custom_prompts):
                            if st.button(cp["name"], key=f"cp_{idx}", use_container_width=True):
                                st.session_state.pending_chat_prompt = cp["text"]
                                st.rerun()
                            if st.button("❌ Delete", key=f"del_cp_{idx}"):
                                custom_prompts.pop(idx)
                                settings["custom_prompts"] = custom_prompts
                                save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), custom_prompts, settings.get("custom_instructions", ""), settings.get("owned_items", []), settings.get("todo_tasks", []), settings.get("favorite_bosses", []))
                                st.rerun()

            # Attachments Preview Section
            if st.session_state.attached_images:
                st.write("📎 **Attachments:**")
                preview_cols = st.columns(min(len(st.session_state.attached_images), 6))
                for idx, img in enumerate(list(st.session_state.attached_images)):
                    with preview_cols[idx % 6]:
                        st.image(img["bytes"], caption=img["name"][:12], width=65)
                        if st.button("❌", key=f"del_img_{idx}", help=f"Remove '{img['name']}'"):
                            st.session_state.attached_images.pop(idx)
                            st.rerun()

            # Check for any pending prompt before chat_input instantiation
            if "pending_chat_prompt" in st.session_state and st.session_state.pending_chat_prompt:
                st.session_state.chat_input_val = st.session_state.pending_chat_prompt
                del st.session_state["pending_chat_prompt"]

            prompt = st.chat_input("Ask about your stats, quest goals, training advice, or gear...", key="chat_input_val")

            if prompt:
                current_images = list(st.session_state.attached_images)
                st.session_state.attached_images = []

                # Reset File Uploader state and widget cache
                old_uploader_key = f"file_uploader_key_{st.session_state.uploader_key_id}"
                st.session_state.uploader_key_id += 1
                if old_uploader_key in st.session_state:
                    del st.session_state[old_uploader_key]


                image_payloads = [
                    {
                        "bytes_b64": base64.b64encode(img["bytes"]).decode("utf-8"),
                        "mime": img["mime"],
                        "name": img["name"]
                    }
                    for img in current_images
                ]

                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "images": image_payloads
                })
                
                log_interaction("user", prompt, images=[{"mime": img["mime"], "name": img["name"]} for img in current_images] if current_images else None)

                with st.chat_message("user"):
                    st.markdown(prompt)
                    if image_payloads:
                        p_cols = st.columns(min(len(image_payloads), 4))
                        for idx, img_p in enumerate(image_payloads):
                            with p_cols[idx % 4]:
                                st.image(base64.b64decode(img_p["bytes_b64"]), caption=img_p["name"], use_container_width=True)

                with st.chat_message("assistant"):
                    with st.spinner(f"{active_model} is analyzing..."):
                        try:
                            context_blocks = []
                            if st.session_state.get("profile_data"):
                                context_blocks.append(f"CURRENT USER PROFILE:\n{st.session_state.profile_data}")

                            past_memories = load_past_session_memories()
                            if past_memories:
                                context_blocks.append(f"PAST SESSION MEMORIES:\n{past_memories}")

                            context_blocks.append(get_owned_items_memory(settings.get("owned_items", [])))
                            context_blocks.append(get_todo_memory(settings.get("todo_tasks", [])))
                            context_blocks.append(get_favorite_bosses_memory(settings.get("favorite_bosses", [])))

                            search_term = None
                            if not search_term:
                                for keyword in ["slayer", "invention", "archaeology", "necromancy", "quest", "combat"]:
                                    if keyword in prompt.lower(): 
                                        search_term = keyword; break
                            if search_term:
                                context_blocks.append(f"WIKI KNOWLEDGE:\n{fetch_rs_wiki_info(search_term)}")

                            ge_context = extract_ge_context_from_prompt(prompt)
                            if ge_context:
                                context_blocks.append(ge_context)

                            # Attach most recent wiki links file as source on the first user prompt of the session
                            user_msgs = [m for m in st.session_state.messages if m.get("role") == "user"]
                            if len(user_msgs) == 1:
                                wiki_file = get_most_recent_wiki_links_file()
                                if wiki_file:
                                    wiki_source_block = format_wiki_links_source_block(wiki_file)
                                    if wiki_source_block:
                                        context_blocks.append(wiki_source_block)
                                        st.toast(f"Attached source file: '{wiki_file}'", icon="📎")

                            full_context = "\n\n".join(context_blocks)
                            final_prompt = f"User Request: {prompt}\n\nContext:\n{full_context}"

                            answer = ""
                            
                            if active_model == "Gemini 3.6 Flash":
                                if not settings.get("gemini_api_key"):
                                    st.error("Missing Gemini API Key. Please log out and update settings.")
                                    st.stop()
                                    
                                client = genai.Client(api_key=settings.get("gemini_api_key"))
                                config = types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.4)
                                
                                gemini_contents = [final_prompt]
                                for img in current_images:
                                    gemini_contents.append(types.Part.from_bytes(data=img["bytes"], mime_type=img["mime"]))

                                for attempt in range(3):
                                    try:
                                        response = client.models.generate_content(model="gemini-3.6-flash", contents=gemini_contents, config=config)
                                        answer = response.text
                                        break
                                    except Exception as api_err:
                                        if "503" in str(api_err) and attempt < 2: 
                                            time.sleep(3); continue
                                        raise api_err

                            elif active_model == "ChatGPT (GPT-4o)":
                                if not settings.get("openai_api_key"):
                                    st.error("Missing OpenAI API Key. Please log out and update settings.")
                                    st.stop()
                                    
                                openai_client = OpenAI(api_key=settings.get("openai_api_key"))

                                if current_images:
                                    gpt_user_content = [{"type": "text", "text": final_prompt}]
                                    for img in current_images:
                                        b64_str = base64.b64encode(img["bytes"]).decode("utf-8")
                                        gpt_user_content.append({
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:{img['mime']};base64,{b64_str}"
                                            }
                                        })
                                else:
                                    gpt_user_content = final_prompt

                                response = openai_client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=[
                                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                                        {"role": "user", "content": gpt_user_content}
                                    ],
                                    temperature=0.4
                                )
                                answer = response.choices[0].message.content

                            answer = verify_wiki_urls(answer)
                            st.markdown(answer)
                            st.session_state.messages.append({"role": "assistant", "content": answer})
                            log_interaction("assistant", answer, active_model)
                            st.session_state.just_responded = True
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error: {e}")


        if col_todo:
            with col_todo:
                with st.container(height=680):
                    st.subheader("📋 Player To-Do List")
                    col_filter, col_auto = st.columns([1, 1])
                    with col_filter:
                        filter_cat = st.selectbox("Filter", ["All Tasks", "Active", "Combat & Bossing", "Quests", "Skilling"], label_visibility="collapsed")
                    with col_auto:
                        if st.button("✨ Auto-Generate Next Goals", use_container_width=True):
                            st.session_state.pending_chat_prompt = "Based on my current stats, quests, and gear, suggest 3 high-value tasks I should focus on next."
                            st.toast("Prompt added! Please go to Chat Agent tab.", icon="✅")
                            
                    with st.form("add_task_form", clear_on_submit=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            new_task_text = st.text_input("➕ Add New Task", placeholder="e.g. Reach 85 Mining", label_visibility="collapsed")
                        with c2:
                            new_task_priority = st.selectbox("Priority", ["🔴 High", "🟡 Med", "🟢 Low"], label_visibility="collapsed")
                        submit_task = st.form_submit_button("Add Task", use_container_width=True)
                        if submit_task and new_task_text.strip():
                            tasks = settings.get("todo_tasks", [])
                            tasks.append({"id": f"task_{int(time.time())}", "text": new_task_text.strip(), "completed": False, "priority": new_task_priority, "category": "All Tasks"})
                            settings["todo_tasks"] = tasks
                            save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), settings.get("custom_instructions", ""), settings.get("owned_items", []), tasks, settings.get("favorite_bosses", []))
                            st.rerun()

                    tasks = settings.get("todo_tasks", [])
                    for idx, task in enumerate(tasks):
                        if filter_cat == "Active" and task.get("completed", False): continue
                        
                        with st.container(border=True):
                            t_c1, t_c2 = st.columns([7, 3])
                            with t_c1:
                                is_done = st.checkbox(f"{task.get('priority', '🟢 Low')} | {task['text']}", value=task.get("completed", False), key=f"todo_done_{task['id']}")
                                if is_done != task.get("completed", False):
                                    task["completed"] = is_done
                                    settings["todo_tasks"] = tasks
                                    save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), settings.get("custom_instructions", ""), settings.get("owned_items", []), tasks, settings.get("favorite_bosses", []))
                                    st.rerun()
                            with t_c2:
                                if st.button("🤖 AI", key=f"todo_ask_{task['id']}", help=f"Ask AI for help with '{task['text']}'", use_container_width=True):
                                    st.session_state.pending_chat_prompt = f"I am currently working on my goal: '{task['text']}'. Please provide a detailed strategy, prerequisites, and step-by-step guidance on how to achieve this efficiently."
                                    st.rerun()
                                if st.button("❌ Del", key=f"todo_del_{task['id']}", use_container_width=True):
                                    tasks.remove(task)
                                    settings["todo_tasks"] = tasks
                                    save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), settings.get("custom_instructions", ""), settings.get("owned_items", []), tasks, settings.get("favorite_bosses", []))
                                    st.rerun()
