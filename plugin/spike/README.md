# RS Helper spike: beta-world test guide

Step 0 of `PLUGIN_BUILD1_PLAN.md`. Two throwaway dev plugins that answer nine questions about Jagex's plugin API before the real plugin is written. Neither is ever submitted to mod.io.

| Folder | What it is |
|---|---|
| `rs-helper-spike/` | The test plugin: a window with test buttons. Results go to the client console. |
| `rs-helper-keywatch/` | Plays "some other plugin" for test S1. It counts keyboard events, never the keys themselves. |
| `smoke_test.lua` | Runs the spike against fake versions of Jagex's API, to catch code errors before you run it: `lua5.4 plugin/spike/smoke_test.lua` |

Allow about 30 minutes. It costs a few cents of API credit.

---

## Before you start

1. **Make a test API key.** In the Anthropic Console, create a new key called `rs-helper-spike` and give it a **low spending limit**. Don't use your main key. You can delete the test key afterwards.
2. **Get the files onto your PC.** Download this branch as a zip from GitHub (`ccr-ff43c70c-ajx82l`, under Code → Download ZIP) and unzip it.
3. **Join the plugin beta world.** Use the launcher link on Jagex's [Accessing the API](https://developer.runescape.com/rs/tutorial/1helloworld.html) page. In the lobby, press **Import save**.
4. **Copy both folders** (`rs-helper-spike` and `rs-helper-keywatch`) into `dev_plugins` inside the beta folder. On Windows the default is `C:\ProgramData\Jagex\RuneScape-BETA\dev_plugins\` (create `dev_plugins` if it's missing). The Mac and Linux paths are on the same Jagex page.

## Start the plugins

Log in to a world. Open the console with **ALT + `** (the key under Esc). Type:

```
prf
plist
pon rs-helper-keywatch
pon rs-helper-spike
```

`plist` should list both plugins. The spike window opens in the middle of the screen, and the console shows `spike loaded. httpAccess allowed=false`.

---

## The tests (in this order)

**S8: window.** Open your backpack or another interface, and drag it under the spike window if you can. Is the spike window on top? Do its buttons respond to clicks?

**S7: ribbon icon.** Open the game's **Plugins** window and click the RS Helper Spike icon. The console logs the size of that area. Click **Show / hide spike window** twice: the window should hide, then come back.

**S4: Lua.** Press **S4 Lua libraries**.

**S5: text.** Press **S5 Text samples**. **Take a screenshot** of the right-hand box. For each of the five lines, note whether it wrapped, whether `<b>`, `<br>` and `<col=…>` showed as text or took effect, and whether the symbols (•, —, quotes, …, é, £) look right.

**S2: scrolling.** Press **S2 Scroll test**. A list of 30 lines appears on the left. Does it stop at the box's edge, or spill out? Move the mouse wheel over it. Does the list move?

**S1: key visibility.** Watch the console as you go.
1. Click the key field and **type** five letters, such as `abcde`. The spike logs five changes, and **keywatch** should log five `saw KeyTyped` lines. That means other plugins can see typing.
2. Delete those letters. Copy `TESTPASTE1234567890` from somewhere (Notepad, say), click the key field and press **Ctrl+V**. Did the text appear? Does the spike log `paste works`? How many `KeyTyped` lines did keywatch log for the paste?
3. Type five letters in the **hidden** field, then press **S1b Read hidden**. It should report length 0. Did keywatch log anything while you typed there?

**Permission.** Clear the key field. In the console type:

```
ppe rs-helper-spike httpAccess
```

A `P:` line should appear, showing that the permission event fired.

**S3: talking to Claude.** Paste your **test** key into the key field. It's never logged.
1. Press **S3 Check key**. Expect `code 200`.
2. Press **S3 Ping Claude**. Expect `code 200`, `answer starts "pong"`, and how many seconds it took.
3. Press **S3 Long answer**. This takes longer: note the seconds, the body size, and whether `timedOut` is ever true.
4. Press **S3 Long answer** again, then **S3 Cancel** straight away. The result should say `cancelled=true`.

**S6 and S9: the lobby.** Log out to the lobby, wait about **10 seconds**, then log back in to a world. The console shows how many ticks fired in the lobby (S6), and whether the window survived the trip (S9). If it didn't, the spike rebuilds it. Is the window on screen afterwards?

## Send the results back

1. Press **Print summary**. Copy or screenshot everything between `===== RS Helper spike summary` and `===== end of summary =====`.
2. Also send the **keywatch** lines from test S1, your **S5 screenshot**, and your by-eye answers for S2, S5, S7, S8 and S9.

## Clean up

```
poff rs-helper-spike
poff rs-helper-keywatch
```

Delete the test key in the Anthropic Console if you won't need it again. Close the game and the launcher to go back to the live worlds.
