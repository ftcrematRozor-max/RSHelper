-- Smoke test for the RS Helper spike (dev only).
--
-- Runs rs-helper-spike/main.lua outside the game against small stand-ins
-- ("fakes") for the parts of Jagex's API it uses, presses every button,
-- fires every event, and fails if anything raises a Lua error or if the test
-- API key ever appears in the console log.
--
-- It only proves the spike's own code runs. The real answers come from the
-- beta world. Run from the repo root:  lua5.4 plugin/spike/smoke_test.lua

------------------------------------------------------------------------
-- Console log capture
------------------------------------------------------------------------

local logLines = {}
function log(message)
    table.insert(logLines, tostring(message))
end

------------------------------------------------------------------------
-- Fake events: Event.<Name>.Subscribe(ref, fn), plus fire() for the test
------------------------------------------------------------------------

local subscribers = {}
Event = setmetatable({}, {
    __index = function(events, name)
        local event = {
            Subscribe = function(ref, fn)
                subscribers[name] = subscribers[name] or {}
                subscribers[name][ref] = fn
            end,
            Unsubscribe = function(ref)
                if subscribers[name] then subscribers[name][ref] = nil end
            end,
        }
        rawset(events, name, event)
        return event
    end,
})

local function fire(name, payload)
    for _, fn in pairs(subscribers[name] or {}) do fn(payload) end
end

------------------------------------------------------------------------
-- Fake UI components
------------------------------------------------------------------------

local components = {}

local function newComponent(kind, parent)
    local component = {
        kind = kind, parent = parent, hooks = {},
        width = 300, height = 200, hidden = false,
        scrollable = true, scrollY = 0, scrollHeight = 0,
        content = "",
    }
    function component:SetPos() end
    function component:SetSize(width, height)
        if width and width > 0 then self.width = width end
        if height and height > 0 then self.height = height end
    end
    function component:Subscribe(hook, idOrFn, fn) self.hooks[hook] = fn or idOrFn end
    function component:Destroy() self.destroyed = true end
    function component:SetHeaderLayout() end
    function component:Setup(visibility) self.visibility = visibility end
    function component:SetScrollSize(_, height) self.scrollHeight = height end
    function component:SetScrollPos(_, y) self.scrollY = y end
    table.insert(components, component)
    return component
end

ui = {
    Hook = { ONBUTTONPRESSED = "ONBUTTONPRESSED", ONCONTENTCHANGED = "ONCONTENTCHANGED", ONSCROLLWHEEL = "ONSCROLLWHEEL" },
    InputFieldActionResult = { NONE = 0, ERROR = 1, CONTENT_CHANGE = 2, SUBMIT = 3 },
    TextContentVisibilityMode = { VISIBLE = 0, SHOW_LAST = 1, HIDDEN = 2 },
    InputFieldFilterMode = { NONE = 0 },
    Interfaces = {},
}
for _, kind in ipairs({ "GroupBox", "Text", "Button", "InputField", "Layer" }) do
    ui[kind] = {
        new = function(parent)
            assert(parent, kind .. ".new was called without a parent")
            return newComponent(kind, parent)
        end,
    }
end
function ui.Interfaces:GetComponent()
    return newComponent("BuildLayer", nil)
end

id = {
    Font = { MUSEO_SANS_15PT_REGULAR = 30 },
    StyleSheet = { DEFAULT = 1, BUTTON_DEFAULT = 2, INPUT_DEFAULT = 3 },
    Component = { TOPLEVEL_V2__PLUGIN_BUILD_LAYER_TOP = 999 },
}
config = {
    Font = {
        MUSEO_SANS_15PT_REGULAR = {
            GetStringHeightAndLineCount = function(_, text, wrapWidth, lineSpacing)
                local lines = math.max(1, math.ceil(#text * 7 / wrapWidth))
                return lines * lineSpacing + 10, lines
            end,
        },
    },
}
GameState = { FromID = function(value) return ({ [20] = "LOBBY", [30] = "GAME" })[value] or "OTHER" end }

------------------------------------------------------------------------
-- Fake plugin permissions and HTTP
------------------------------------------------------------------------

local permissionGranted = false
PluginPermissions = { httpAccess = "httpAccess" }
Plugin = {
    urls = { claude = "https://api.anthropic.com/" },
    HasPermission = function() return permissionGranted end,
}

local lastRequest = nil
HTTPRequest = {
    new = function(baseURL, path)
        local request = { baseURL = baseURL, path = path, headers = {} }
        function request:AddHeader(key, value) self.headers[key] = value end
        function request:Post(data, done, progress)
            self.method, self.body, self.done, self.progress = "POST", data, done, progress
            lastRequest = self
        end
        function request:Get(done, progress)
            self.method, self.done, self.progress = "GET", done, progress
            lastRequest = self
        end
        function request:Cancel()
            self.cancelled = true
            self.done(self)
        end
        return request
    end,
}

-- Finish the last request with a scripted response.
local function respond(code, data)
    local request = lastRequest
    request.responseCode = code
    request.successful = (code == 200)
    request.failed = false
    request.timedOut = false
    request.cancelled = false
    request.data = data
    request.header = "request-id: req_test"
    request.progress(request)
    request.done(request)
end

------------------------------------------------------------------------
-- Helpers to find and use components
------------------------------------------------------------------------

-- Components "killed" by the S9 simulation raise errors when read, so the
-- helpers below read fields with rawget and skip anything destroyed.
local function usable(component, kind)
    return rawget(component, "kind") == kind and not rawget(component, "destroyed")
end

local function findButton(label)
    for _, component in ipairs(components) do
        if usable(component, "Button") and component.label == label then
            return component
        end
    end
    error("no button labelled " .. label)
end

local function press(label)
    findButton(label).hooks.ONBUTTONPRESSED()
end

local function inputFields()
    local fields = {}
    for _, component in ipairs(components) do
        if usable(component, "InputField") then table.insert(fields, component) end
    end
    return fields
end

local function lastLayerWithWheel()
    for index = #components, 1, -1 do
        local component = components[index]
        if usable(component, "Layer") and component.hooks.ONSCROLLWHEEL then
            return component
        end
    end
    error("no scrollable layer")
end

local function logContains(text)
    for _, line in ipairs(logLines) do
        if line:find(text, 1, true) then return true end
    end
    return false
end

------------------------------------------------------------------------
-- Run the spike and drive every test
------------------------------------------------------------------------

local SECRET = "sk-test-NEVER-LOG-THIS"

local spike = assert(loadfile("plugin/spike/rs-helper-spike/main.lua"))
spike()

-- S7: ribbon layer, then the toggle button it adds
fire("ContentLayerReady", { component = newComponent("RibbonLayer", nil) })
press("Show / hide spike window")
press("Show / hide spike window")

-- S6: ticks, then a trip to the lobby and back
for _ = 1, 100 do fire("Logic", { logicTick = 1 }) end
fire("GameStateChanged", { oldState = 30, newState = 20 })
for _ = 1, 50 do fire("Logic", { logicTick = 1 }) end
for _ = 1, 5 do fire("ServerLogic") end
-- S9: pretend the lobby unloaded the interface, so the old window is dead
local oldWindow
for _, component in ipairs(components) do
    if component.kind == "GroupBox" then oldWindow = component end
end
-- Its children went with it.
local function markChildrenDestroyed(parent)
    for _, component in ipairs(components) do
        if rawget(component, "parent") == parent and not rawget(component, "destroyed") then
            component.destroyed = true
            markChildrenDestroyed(component)
        end
    end
end
markChildrenDestroyed(oldWindow)
for key in pairs(oldWindow) do oldWindow[key] = nil end
setmetatable(oldWindow, { __index = function() error("component no longer exists") end })
fire("GameStateChanged", { oldState = 20, newState = 30 })

-- S4, S5, S2 (including a mouse-wheel move)
press("S4 Lua libraries")
press("S5 Text samples")
press("S5 Text samples")          -- running it twice must replace, not stack
press("S2 Scroll test")
lastLayerWithWheel().hooks.ONSCROLLWHEEL(nil, 3)

-- S3 before permission, then permission granted
press("S3 Ping Claude")
fire("OptionalPermissionChanged", { permissionName = "httpAccess", enabled = true })
permissionGranted = true

-- S3 with no key yet
press("S3 Ping Claude")

-- S1: type two characters, then paste the rest of the key
local keyField, hiddenField = inputFields()[1], inputFields()[2]
keyField.hooks.ONCONTENTCHANGED(keyField, 2, "sk")
keyField.hooks.ONCONTENTCHANGED(keyField, 2, SECRET)
keyField.content = SECRET

-- S1b: a hidden field reads back empty
press("S1b Read hidden")

-- S3b: check key (GET), then a successful ping (POST)
press("S3 Check key")
assert(lastRequest.method == "GET" and lastRequest.path == "v1/models", "check key should GET v1/models")
assert(lastRequest.headers["x-api-key"] == SECRET, "key header missing")
assert(lastRequest.headers["anthropic-version"] == "2026-10-21", "version header missing")
respond(200, '{"data":[{"id":"claude-sonnet-5-5"},{"id":"claude-opus-5-5"}]}')

press("S3 Ping Claude")
assert(lastRequest.method == "POST" and lastRequest.path == "v1/messages", "ping should POST v1/messages")
assert(lastRequest.headers["Content-Type"] == "application/json", "content type missing")
assert(not lastRequest.body:find("temperature"), "the body must not send temperature")
press("S3 Ping Claude")           -- second press while running must be refused
respond(200, '{"content":[{"type":"thinking","thinking":""},{"type":"text","text":"pong"}],"stop_reason":"end_turn"}')

-- S3: an error response, then a cancelled long request
press("S3 Ping Claude")
respond(401, '{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}')
press("S3 Long answer")
press("S3 Cancel")
press("S3 Cancel")                -- nothing left to cancel

-- Summary and shutdown
press("Print summary")
PluginShutdown()

------------------------------------------------------------------------
-- Checks
------------------------------------------------------------------------

local failures = {}
local function check(condition, message)
    if not condition then table.insert(failures, message) end
end

check(not logContains("ERROR"), "a step raised a Lua error")
check(not logContains(SECRET), "the API key appeared in the log")
check(logContains("S1: paste works"), "S1 paste detection")
check(logContains("hidden field reads back as length 0"), "S1b")
check(logContains("S2w: wheel delta 3"), "S2 wheel")
check(logContains("S3: blocked"), "S3 permission check")
check(logContains("paste a TEST API key"), "S3 empty key check")
check(logContains("another request is still running"), "S3 one request at a time")
check(logContains('answer starts "pong"'), "S3 answer parsing")
check(logContains('error "invalid x-api-key"'), "S3 error parsing")
check(logContains("S3L: code nil, successful=nil, failed=nil, timedOut=nil, cancelled=true"), "S3 cancel")
check(logContains("S9: back in the game: old window still usable=false (rebuilt it)"), "S9 rebuild")
check(logContains("S4: os="), "S4")
check(logContains("S5: measured"), "S5")
check(logContains("while in the lobby, Logic fired 50 times and ServerLogic 5 times"), "S6")
check(logContains("S7: ribbon content layer is"), "S7")
check(logContains("S8: plugin build layer found=true"), "S8")
check(logContains("P: OptionalPermissionChanged fired"), "P")
check(logContains("===== end of summary ====="), "summary")

print(table.concat(logLines, "\n"))
print("")
if #failures > 0 then
    print("SMOKE TEST FAILED: " .. table.concat(failures, "; "))
    os.exit(1)
end
print("SMOKE TEST PASSED (" .. #logLines .. " log lines)")
