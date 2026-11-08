-- RS Helper Spike (Step 0 of PLUGIN_BUILD1_PLAN.md, dev only, never submitted)
--
-- A throwaway plugin for the plugin beta world. It answers nine questions
-- (S1-S9 in the build plan) about Jagex's plugin API before the real plugin
-- is written. Every result is printed to the client console (ALT + `).
-- Press "Print summary" at the end and send the summary lines back.
--
-- Safety: the API key is only ever read from the key field when a request is
-- sent. It is never stored and never written to the console.

------------------------------------------------------------------------
-- Results and error handling
------------------------------------------------------------------------

-- One result line per test, printed together by "Print summary".
local results = {}
local SUMMARY_ORDER = { "S1", "S1b", "S2", "S2w", "S3", "S3L", "S3b", "S3c", "S4", "S5", "S6", "S7", "S8", "S9", "P" }

-- Record a result and echo it to the console straight away.
local function note(testId, text)
    results[testId] = text
    log(testId .. ": " .. text)
end

-- Run a test step, reporting any Lua error instead of stopping the plugin.
local function try(testId, fn)
    local ok, err = pcall(fn)
    if not ok then
        note(testId, "ERROR " .. tostring(err))
    end
end

------------------------------------------------------------------------
-- Tick counters (used for timing, and for S6)
------------------------------------------------------------------------

-- Event.Logic runs 50 times a second; ServerLogic about every 0.6 s.
local ticks = { logic = 0, server = 0 }

Event.Logic.Subscribe("spikeLogic", function()
    ticks.logic = ticks.logic + 1
end)

Event.ServerLogic.Subscribe("spikeServer", function()
    ticks.server = ticks.server + 1
end)

-- S6: count how many ticks arrive while the player sits in the lobby.
-- GameState values from Jagex's events page: LOBBY = 20, GAME = 30.
local LOBBY = 20
local GAME = 30
local lobbyStart = nil

-- S9 needs these, defined further down.
local windowAlive, rebuildWindow

Event.GameStateChanged.Subscribe("spikeState", function(event)
    try("S6", function()
        local name = tostring(event.newState)
        if GameState and GameState.FromID then
            name = tostring(GameState.FromID(event.newState))
        end
        log("S6: game state is now " .. name .. " (" .. tostring(event.newState) .. ")")

        if event.newState == LOBBY then
            lobbyStart = { logic = ticks.logic, server = ticks.server }
        elseif event.oldState == LOBBY and lobbyStart then
            note("S6", "while in the lobby, Logic fired " .. (ticks.logic - lobbyStart.logic)
                .. " times and ServerLogic " .. (ticks.server - lobbyStart.server) .. " times")
            lobbyStart = nil
        end
    end)

    -- S9: Jagex says components only live while their interface is loaded.
    -- Back in the game, check whether the window survived, and rebuild it if not.
    if event.newState == GAME then
        try("S9", function()
            local alive = windowAlive()
            note("S9", "back in the game: old window still usable=" .. tostring(alive)
                .. (alive and "" or " (rebuilt it)") .. ". Check by eye that the window is on screen.")
            if not alive then rebuildWindow() end
        end)
    end
end)

-- Log permission changes, to see whether this event fires after "ppe".
Event.OptionalPermissionChanged.Subscribe("spikePermission", function(event)
    note("P", "OptionalPermissionChanged fired: " .. tostring(event.permissionName)
        .. " is now " .. tostring(event.enabled))
end)

------------------------------------------------------------------------
-- Small UI helpers (all positions in interface units, inside the window)
------------------------------------------------------------------------

local FONT = id.Font.MUSEO_SANS_15PT_REGULAR

-- A text label.
local function addText(parent, x, y, width, height, content)
    local text = ui.Text.new(parent)
    text:SetPos(x, y)
    text:SetSize(width, height)
    text.font = FONT
    text.content = content
    return text
end

-- A button that runs onPress (inside try) when clicked.
local function addButton(parent, x, y, width, testId, label, onPress)
    local button = ui.Button.new(parent)
    button:SetPos(x, y)
    button:SetSize(width, 28)
    button.label = label
    button.stylesheetID = id.StyleSheet.BUTTON_DEFAULT
    button:Subscribe(ui.Hook.ONBUTTONPRESSED, function()
        try(testId, onPress)
    end)
    return button
end

-- A text input field.
local function addInput(parent, x, y, width, placeholder)
    local field = ui.InputField.new(parent)
    field.stylesheetID = id.StyleSheet.INPUT_DEFAULT
    field:SetPos(x, y)
    field:SetSize(width, 30)
    field.emptyText = placeholder
    return field
end

-- Turn an InputFieldActionResult value into its name, for readable logs.
local function reasonName(reason)
    local ok, name = pcall(function()
        for enumName, value in pairs(ui.InputFieldActionResult) do
            if value == reason then return enumName end
        end
    end)
    if ok and name then return name end
    return tostring(reason)
end

------------------------------------------------------------------------
-- The spike window
------------------------------------------------------------------------

local window = nil        -- the GroupBox holding everything, built once
local keyField = nil      -- visible field for the TEST API key (S1, S3)
local hiddenField = nil   -- restricted field (S1b)
local scrollLayer = nil   -- S2 test area
local sampleLayer = nil   -- S5 test area
local STAGE_Y = 236       -- top of the area where S2 and S5 draw
local lastKeyLength = 0   -- S1: key field length after the last change

------------------------------------------------------------------------
-- S1: typing and pasting into a visible field
------------------------------------------------------------------------

lastKeyLength = 0

-- Log how the key field changed, by length only (never the content).
local function onKeyFieldChanged(field, reason, newContent)
    try("S1", function()
        local length = #(newContent or "")
        local change = length - lastKeyLength
        log("S1: key field " .. reasonName(reason) .. ", length " .. length .. " (change " .. change .. ")")
        if change > 1 then
            note("S1", "paste works: one change added " .. change .. " characters at once")
        end
        lastKeyLength = length
    end)
end

-- S1b: can our own plugin read a hidden (restricted) field? Jagex says no.
local function readHiddenField()
    local content = hiddenField.content or ""
    note("S1b", "hidden field reads back as length " .. #content .. " (Jagex's docs say it should be 0)")
end

------------------------------------------------------------------------
-- S2: does a Layer scroll?
------------------------------------------------------------------------

local SCROLL_VIEW_HEIGHT = 220
local SCROLL_CONTENT_HEIGHT = 600

local function runScrollTest()
    if scrollLayer then scrollLayer:Destroy() end
    scrollLayer = ui.Layer.new(window)
    scrollLayer:SetPos(8, STAGE_Y)
    scrollLayer:SetSize(280, SCROLL_VIEW_HEIGHT)

    -- 30 lines of 20 units = 600 units of content in a 220-unit view.
    for line = 1, 30 do
        addText(scrollLayer, 4, (line - 1) * 20, 260, 20, "Scroll line " .. line)
    end
    scrollLayer:SetScrollSize(280, SCROLL_CONTENT_HEIGHT)

    note("S2", "layer scrollable=" .. tostring(scrollLayer.scrollable)
        .. ", scrollHeight=" .. tostring(scrollLayer.scrollHeight)
        .. ", window (GroupBox) scrollable=" .. tostring(window.scrollable)
        .. ". Now move the mouse wheel over the list.")

    scrollLayer:Subscribe(ui.Hook.ONSCROLLWHEEL, function(_, delta)
        try("S2w", function()
            local before = scrollLayer.scrollY or 0
            local target = before + (delta or 0) * 20
            target = math.max(0, math.min(SCROLL_CONTENT_HEIGHT - SCROLL_VIEW_HEIGHT, target))
            scrollLayer:SetScrollPos(0, target)
            note("S2w", "wheel delta " .. tostring(delta) .. ": scrollY " .. tostring(before)
                .. " -> " .. tostring(scrollLayer.scrollY))
        end)
    end)
end

------------------------------------------------------------------------
-- S3: HTTP requests to the Anthropic API
------------------------------------------------------------------------

local activeRequest = nil

-- Small fixed request bodies (JSON written by hand; no JSON library yet).
local PING_BODY = [[{"model":"claude-sonnet-5-5","max_tokens":1024,"output_config":{"effort":"low"},"messages":[{"role":"user","content":"Reply with the single word: pong"}]}]]
local LONG_BODY = [[{"model":"claude-sonnet-5-5","max_tokens":8000,"output_config":{"effort":"medium"},"messages":[{"role":"user","content":"Write about 1500 words on efficient Slayer training in RuneScape 3, as plain paragraphs."}]}]]

-- The key from the visible field, trimmed. Never logged.
local function currentKey()
    local key = (keyField and keyField.content) or ""
    key = key:gsub("^%s+", "")
    key = key:gsub("%s+$", "")
    return key
end

-- Seconds since startTick, measured with the 50-per-second Logic event.
local function secondsSince(startTick)
    return string.format("%.1f", (ticks.logic - startTick) / 50)
end

-- Describe a finished request in one line for the summary.
local function describeResult(request, startTick, progressCalls)
    local data = request.data or ""
    local parts = {
        "code " .. tostring(request.responseCode),
        "successful=" .. tostring(request.successful),
        "failed=" .. tostring(request.failed),
        "timedOut=" .. tostring(request.timedOut),
        "cancelled=" .. tostring(request.cancelled),
        "took " .. secondsSince(startTick) .. " s",
        "body " .. #data .. " bytes",
        "header " .. #(request.header or "") .. " bytes",
        "progress callbacks " .. progressCalls,
    }
    if request.failed then
        table.insert(parts, "errorCode " .. tostring(request.errorCode) .. " (" .. tostring(request.errorInfo) .. ")")
    end
    local stopReason = data:match('"stop_reason"%s*:%s*"([^"]+)"')
    if stopReason then table.insert(parts, "stop_reason " .. stopReason) end
    local answer = data:match('"type"%s*:%s*"text"%s*,%s*"text"%s*:%s*"(.-)"')
    if answer then table.insert(parts, 'answer starts "' .. answer:sub(1, 60) .. '"') end
    local errorMessage = data:match('"message"%s*:%s*"(.-)"')
    if errorMessage and not request.successful then table.insert(parts, 'error "' .. errorMessage .. '"') end
    return table.concat(parts, ", ")
end

-- Send one request to Anthropic and record what came back.
local function sendRequest(testId, method, path, body)
    if not Plugin.HasPermission(PluginPermissions.httpAccess) then
        note(testId, "blocked: run  ppe rs-helper-spike httpAccess  in the console first")
        return
    end
    local key = currentKey()
    if key == "" then
        note(testId, "paste a TEST API key into the key field first")
        return
    end
    if activeRequest then
        note(testId, "another request is still running; wait or press Cancel")
        return
    end

    local request = HTTPRequest.new(Plugin.urls.claude, path)
    request:AddHeader("x-api-key", key)
    request:AddHeader("anthropic-version", "2026-10-21")
    if body then
        request:AddHeader("Content-Type", "application/json")
    end

    local startTick = ticks.logic
    local progressCalls = 0
    local function onProgress()
        progressCalls = progressCalls + 1
    end
    local function onDone(finished)
        activeRequest = nil
        try(testId, function()
            note(testId, describeResult(finished, startTick, progressCalls))
        end)
    end

    activeRequest = request
    if method == "POST" then
        request:Post(body, onDone, onProgress)
    else
        request:Get(onDone, onProgress)
    end
    log(testId .. ": sent " .. method .. " " .. path .. ", waiting for the answer...")
end

-- Stop whatever request is running.
local function cancelRequest()
    if not activeRequest then
        log("S3c: nothing to cancel")
        return
    end
    activeRequest:Cancel()
    note("S3c", "Cancel() called; the S3 or S3L line should now say cancelled=true")
end

------------------------------------------------------------------------
-- S4: which Lua standard libraries exist?
------------------------------------------------------------------------

local function checkLuaLibraries()
    local names = { "os", "os.time", "os.date", "os.clock", "io", "utf8",
        "string.format", "table.concat", "math.floor", "require", "load", "coroutine", "debug" }
    local found = {}
    for _, name in ipairs(names) do
        local value = _G
        for part in name:gmatch("[^%.]+") do
            if type(value) == "table" then value = value[part] else value = nil end
        end
        table.insert(found, name .. "=" .. type(value))
    end
    local extra = ""
    if os and os.time then extra = extra .. " | os.time()=" .. tostring(os.time()) end
    if os and os.date then extra = extra .. " | os.date()=" .. tostring(os.date("!%Y-%m-%d %H:%M UTC")) end
    note("S4", table.concat(found, ", ") .. extra)
end

------------------------------------------------------------------------
-- S5: how does ui.Text show tags and special characters?
------------------------------------------------------------------------

local SAMPLES = {
    "Wrap test: this sentence is deliberately long, so it should wrap onto more than one line inside this box.",
    "Angle brackets: a < b > c, and <b>bold?</b>",
    "Line break: first line<br>second line",
    "Colour tag: <col=ff0000>red?</col> then normal",
    "Symbols: \u{2022} bullet, \u{2014} dash, \u{2018}single\u{2019}, \u{201C}double\u{201D}, \u{2026}, \u{00E9}, \u{00A3}",
}

local function showTextSamples()
    if sampleLayer then sampleLayer:Destroy() end
    sampleLayer = ui.Layer.new(window)
    sampleLayer:SetPos(300, STAGE_Y)
    sampleLayer:SetSize(290, SCROLL_VIEW_HEIGHT)

    local measure = config.Font.MUSEO_SANS_15PT_REGULAR
    local y = 0
    local heights = {}
    for index, sample in ipairs(SAMPLES) do
        local height, lines = measure:GetStringHeightAndLineCount(sample, 290, 18)
        local text = addText(sampleLayer, 0, y, 290, height, sample)
        text.maxLines = 0
        table.insert(heights, index .. ":" .. tostring(height) .. "px/" .. tostring(lines) .. " lines")
        y = y + height + 4
    end
    note("S5", "measured " .. table.concat(heights, ", ")
        .. ". Take a screenshot of the right-hand box and describe what each line shows.")
end

------------------------------------------------------------------------
-- Summary
------------------------------------------------------------------------

local function printSummary()
    log("===== RS Helper spike summary (copy from here) =====")
    log("ticks so far: Logic " .. ticks.logic .. ", ServerLogic " .. ticks.server)
    for _, testId in ipairs(SUMMARY_ORDER) do
        log(testId .. ": " .. (results[testId] or "not run"))
    end
    log("===== end of summary =====")
end

------------------------------------------------------------------------
-- Build the window (once) and show or hide it
------------------------------------------------------------------------

local function buildWindow()
    local buildLayer = ui.Interfaces:GetComponent(id.Component.TOPLEVEL_V2__PLUGIN_BUILD_LAYER_TOP)
    note("S8", "plugin build layer found=" .. tostring(buildLayer ~= nil)
        .. ". Check by eye: is this window above open interfaces, and do its buttons click?")

    window = ui.GroupBox.new(buildLayer)
    window.stylesheetID = id.StyleSheet.DEFAULT
    window:SetHeaderLayout(0, 0, 0, 0, 0)
    window:SetSize(600, 470)
    window:SetPos(0, 0, 0.5, 0.5, -0.5, -0.5)   -- centred on the game window

    addText(window, 8, 6, 584, 24, "RS Helper spike: results go to the console (ALT + `)")

    -- Row 1: the HTTP tests (S3)
    addButton(window, 8, 36, 140, "S3b", "S3 Check key", function()
        sendRequest("S3b", "GET", "v1/models", nil)
    end)
    addButton(window, 154, 36, 140, "S3", "S3 Ping Claude", function()
        sendRequest("S3", "POST", "v1/messages", PING_BODY)
    end)
    addButton(window, 300, 36, 140, "S3L", "S3 Long answer", function()
        sendRequest("S3L", "POST", "v1/messages", LONG_BODY)
    end)
    addButton(window, 446, 36, 140, "S3c", "S3 Cancel", cancelRequest)

    -- Row 2: the other tests
    addButton(window, 8, 70, 140, "S2", "S2 Scroll test", runScrollTest)
    addButton(window, 154, 70, 140, "S4", "S4 Lua libraries", checkLuaLibraries)
    addButton(window, 300, 70, 140, "S5", "S5 Text samples", showTextSamples)
    addButton(window, 446, 70, 140, "summary", "Print summary", printSummary)

    -- S1: the visible key field
    addText(window, 8, 108, 584, 20, "S1 / S3: paste a TEST API key here with Ctrl+V (it is never logged)")
    keyField = addInput(window, 8, 130, 584, "Paste your TEST key here")
    keyField:Setup(ui.TextContentVisibilityMode.VISIBLE, ui.InputFieldFilterMode.NONE, 256)
    keyField:Subscribe(ui.Hook.ONCONTENTCHANGED, onKeyFieldChanged)

    -- S1b: a hidden (restricted) field
    addText(window, 8, 168, 584, 20, "S1b: type a few letters in this hidden field, then press Read")
    hiddenField = addInput(window, 8, 190, 430, "Hidden field")
    hiddenField:Setup(ui.TextContentVisibilityMode.HIDDEN, ui.InputFieldFilterMode.NONE, 64)
    addButton(window, 446, 191, 140, "S1b", "S1b Read hidden", readHiddenField)
end

-- Jagex documents no "is valid" check for components, so read a property
-- and treat an error (or nothing at all) as "this window is gone".
windowAlive = function()
    if not window then return false end
    local ok, hidden = pcall(function() return window.hidden end)
    return ok and hidden ~= nil
end

-- Forget the old window (its interface was unloaded) and build a new one.
rebuildWindow = function()
    window, keyField, hiddenField, scrollLayer, sampleLayer = nil, nil, nil, nil, nil
    lastKeyLength = 0
    buildWindow()
end

local function toggleWindow()
    if not windowAlive() then
        rebuildWindow()
    else
        window.hidden = not window.hidden
    end
end

------------------------------------------------------------------------
-- S7: the ribbon icon's content layer
------------------------------------------------------------------------

Event.ContentLayerReady.Subscribe("spikeRibbon", function(event)
    try("S7", function()
        local layer = event.component
        note("S7", "ribbon content layer is " .. tostring(layer.width) .. " x " .. tostring(layer.height))
        addText(layer, 8, 8, 260, 24, "RS Helper spike")
        addButton(layer, 8, 40, 200, "S7", "Show / hide spike window", toggleWindow)
    end)
end)

------------------------------------------------------------------------
-- Start-up and shutdown
------------------------------------------------------------------------

try("S8", buildWindow)
log("spike loaded. httpAccess allowed=" .. tostring(Plugin.HasPermission(PluginPermissions.httpAccess))
    .. ", claude URL declared=" .. tostring(Plugin.urls.claude ~= nil))

-- Called by the client when the plugin is disabled or the client closes.
function PluginShutdown()
    if window then window:Destroy() end
end
