# Current Implementation Task for Roo: Player To-Do & Task Manager

This document contains the exact set of updates to implement in `app.py` and `settings.json`.

---

## 1. settings.json Schema Update
Add `"todo_tasks": []` to `load_settings()` and `save_settings()` in `app.py`.

Example `settings.json` structure:
```json
{
    "gemini_api_key": "",
    "openai_api_key": "",
    "rs_username": "rozraid",
    "saved_accounts": ["rozraid"],
    "custom_prompts": [],
    "custom_instructions": "",
    "owned_items": [],
    "todo_tasks": [
        {"id": "task_1", "text": "Reach 85 Mining for River of Blood", "completed": false},
        {"id": "task_2", "text": "Complete Desert Treasure II", "completed": true}
    ]
}
```

---

## 2. Helper Functions to Add in app.py

```python
def get_todo_memory(todo_tasks: list) -> str:
    """Formats active (uncompleted) player To-Do tasks for the LLM context."""
    active_tasks = [t["text"] for t in todo_tasks if not t.get("completed", False)]
    if not active_tasks:
        return "PLAYER ACTIVE TO-DO TASKS: No active tasks currently listed."
    return "PLAYER ACTIVE TO-DO TASKS & GOALS:\n" + "\n".join([f"- {t}" for t in active_tasks])
```

---

## 3. To-Do List UI Specification in app.py

### Side-by-Side / Overlay Panel in tab_chat
In `tab_chat`:
- At the top of `tab_chat`, place a prominent toggle/button:
  ```python
  show_todo = st.toggle("📋 To-Do & Task Manager", value=st.session_state.get("show_todo", False), key="show_todo_toggle")
  ```
- Layout conditional split:
  ```python
  if show_todo:
      col_chat, col_todo = st.columns([3, 2])
  else:
      col_chat = st.container()
      col_todo = None
  ```
- Render the chat UI inside `with col_chat:`.
- Render the To-Do panel inside `with col_todo:`:
  - Header: `st.subheader("📋 Player To-Do List")`
  - Filter checkbox: `show_completed = st.checkbox("Show completed tasks", value=False)`
  - New Task Input:
    ```python
    new_task_text = st.text_input("➕ Add New Task", placeholder="e.g. Reach 85 Mining")
    if st.button("Add Task") and new_task_text:
        tasks = settings.get("todo_tasks", [])
        tasks.append({"id": f"task_{int(time.time())}", "text": new_task_text, "completed": False})
        settings["todo_tasks"] = tasks
        save_settings(settings.get("gemini_api_key"), settings.get("openai_api_key"), settings.get("rs_username"), settings.get("saved_accounts", []), settings.get("custom_prompts", []), settings.get("custom_instructions", ""), settings.get("owned_items", []), tasks)
        st.rerun()
    ```
  - Display Task Items:
    Iterate over `settings.get("todo_tasks", [])`:
    - Filter: If `not show_completed` and `task["completed"]`, skip displaying.
    - Each task row uses 3 columns (`st.columns([1, 4, 1])`):
      - Col 1: Checkbox for completion (`task["completed"]`). Toggling saves `settings["todo_tasks"]` and calls `st.rerun()`.
      - Col 2: Text input allowing inline editing of task text.
      - Col 3: Delete button (`❌`) to remove task.

---

## 4. Context & System Instruction Integration
- Update `SYSTEM_INSTRUCTION` in `app.py`:
  Add rule: `"8. ALWAYS align your advice and strategies with the user's active To-Do list tasks and ongoing goals."`
- Inject To-Do memory into `context_blocks` inside chat handler:
  ```python
  context_blocks.append(get_todo_memory(settings.get("todo_tasks", [])))
  ```

---

## 5. Verification Plan
1. Run Python syntax compilation:
   ```powershell
   venv\Scripts\python.exe -m py_compile app.py
   ```
2. Launch Streamlit app (`streamlit run app.py`).
3. Toggle "📋 To-Do & Task Manager" -> verify side-by-side view appears next to chat.
4. Add, edit, check off, and filter tasks -> verify persistence in `settings.json` and inclusion in LLM prompt context.
