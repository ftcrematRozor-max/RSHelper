-- RS Helper Keywatch (dev only, never submitted)
--
-- Plays the part of "some other plugin" for spike test S1. It counts the
-- keyboard events Jagex's API delivers to every plugin, so we can see
-- whether another plugin could watch an API key being typed or pasted.
--
-- It only counts events. It never logs which keys were pressed.

local typedCount = 0   -- KeyTyped events seen so far
local downCount = 0    -- KeyDown events seen so far

-- Count every key press the client reports to this plugin.
Event.KeyDown.Subscribe("keywatchDown", function()
    downCount = downCount + 1
end)

-- Log a running count for every typed character (but not the character).
Event.KeyTyped.Subscribe("keywatchTyped", function()
    typedCount = typedCount + 1
    log("keywatch: saw KeyTyped #" .. typedCount .. " (KeyDown so far: " .. downCount .. ")")
end)

log("keywatch: listening for keyboard events (counts only, never the keys)")
