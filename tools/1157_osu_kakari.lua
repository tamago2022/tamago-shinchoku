-- 1157番「代わりに押す係」（Hammerspoon版・0円）
-- たまごさんの代わりに押す。ただし押してよい画面だけ。
--
-- 設計の肝：**押してよいボタンの名前の表（ホワイトリスト）**と
--           **同じ画面に1語でもあったら絶対に押さない語（ブラックリスト）**の二重。
--           片方だけだと事故る。両方通って初めて押す。
--
-- 押した記録は status/1157/oshita.jsonl に1行ずつ残す。
-- ＝「本人操作の回数」が置きではなく実測になる。
--
-- 元ネタ（世界の実例）：
--   noa「Claude Codeの許可ボタンを自動でクリックする方法」note, 2026-04
--   https://note.com/noa_saruta/n/ncf67fc0d279b
--   Hammerspoon hs.axuielement（macOSアクセシビリティAPI）
--   https://www.hammerspoon.org/docs/hs.axuielement.html
-- 変えた点：元ネタは「許可」なら何でも押す。こちらはホワイトリスト＋禁止語で絞り、
--           押した記録を必ず残す。

local REPO   = os.getenv("HOME") .. "/Desktop/tamago-shinchoku"
local LOGJSON = REPO .. "/status/1157/oshita.jsonl"
local CLAUDE_LOG = os.getenv("HOME") .. "/Library/Logs/Claude/main.log"

-- 押してよいボタンの名前だけ（完全一致に近い部分一致）
local OK_BUTTONS = {
  "常に許可", "一度だけ許可", "許可", "Allow once", "Always allow",
  "Allow for session", "Allow", "承認", "Approve", "Authorize",
  "続ける", "Continue", "OK",
}

-- 同じ窓の文字のどこかに1語でもあったら、何があっても押さない
-- （不可逆な4つ＝データ削除・課金・外部公開・パスワード入力）
local NEVER = {
  "削除", "消去", "ゴミ箱", "Delete", "Remove", "Erase", "Trash", "Destroy",
  "支払", "課金", "購入", "請求", "カード", "Purchase", "Pay", "Subscribe", "Billing", "Card",
  "公開", "投稿", "送信", "Publish", "Post", "Send", "Tweet", "Share publicly",
  "パスワード", "Password", "秘密鍵", "Private key", "Secret",
  "権限", "Permission settings", "Admin", "管理者",
  "同意", "利用規約", "Terms", "Agree",       -- 規約同意は本人だけ
  "本人確認", "Verify your identity", "2段階", "Two-factor",
}

local enabled = true

local function nowStr() return os.date("%Y-%m-%dT%H:%M:%S") end

local function note(kind, app, button, why)
  local line = string.format(
    '{"at":"%s","kind":"%s","app":"%s","button":"%s","why":"%s"}\n',
    nowStr(), kind, app or "", (button or ""):gsub('"', "'"), why or "")
  os.execute('mkdir -p "' .. REPO .. '/status/1157"')
  local f = io.open(LOGJSON, "a")
  if f then f:write(line); f:close() end
  print(kind .. " " .. (button or "") .. " " .. (why or ""))
end

-- 窓の中の文字を全部集める（禁止語の判定に使う）
local function collectText(el, acc, depth)
  if depth > 12 then return end
  for _, k in ipairs({ "AXTitle", "AXValue", "AXDescription", "AXHelp" }) do
    local v = el:attributeValue(k)
    if type(v) == "string" then acc[#acc + 1] = v end
  end
  for _, c in ipairs(el:attributeValue("AXChildren") or {}) do
    collectText(c, acc, depth + 1)
  end
end

local function hasNever(text)
  for _, w in ipairs(NEVER) do
    if text:lower():find(w:lower(), 1, true) then return w end
  end
  return nil
end

local function findButton(el, depth)
  if depth > 12 then return nil end
  local role = el:attributeValue("AXRole")
  local title = el:attributeValue("AXTitle") or ""
  if role == "AXButton" then
    for _, w in ipairs(OK_BUTTONS) do
      if title:find(w, 1, true) then return el, title end
    end
  end
  for _, c in ipairs(el:attributeValue("AXChildren") or {}) do
    local b, t = findButton(c, depth + 1)
    if b then return b, t end
  end
  return nil
end

local function tryPress(appName)
  local app = hs.application.find(appName)
  if not app then return false end
  local axApp = hs.axuielement.applicationElement(app)
  if axApp then axApp:setAttributeValue("AXManualAccessibility", true) end
  local win = app:mainWindow()
  if not win then return false end
  local axWin = hs.axuielement.windowElement(win)
  if not axWin then return false end

  local acc = {}
  collectText(axWin, acc, 0)
  local whole = table.concat(acc, " / ")

  local btn, title = findButton(axWin, 0)
  if not btn then return false end

  local bad = hasNever(whole)
  if bad then
    note("押さなかった", appName, title, "禁止語:" .. bad)
    return false
  end

  btn:performAction("AXPress")
  note("押した", appName, title, "ホワイトリスト通過")
  return true
end

-- Claudeアプリのログに「未応答の許可要求」が出たら押しに行く
local lastSize = 0
local f = io.open(CLAUDE_LOG, "rb")
if f then lastSize = f:seek("end"); f:close() end

if _G.osuTimer then _G.osuTimer:stop() end
_G.osuTimer = hs.timer.doEvery(2, function()
  if not enabled then return end
  local fh = io.open(CLAUDE_LOG, "rb")
  if not fh then return end
  local size = fh:seek("end")
  if size <= lastSize then fh:close(); return end
  fh:seek("set", lastSize)
  local new = fh:read("*a") or ""
  fh:close()
  lastSize = size
  if new:find("tool permission request") then
    hs.timer.doAfter(0.4, function() tryPress("Claude") end)
  end
end)

if _G.osuMenu then _G.osuMenu:delete() end
_G.osuMenu = hs.menubar.new(true, "TamagoOsuKakari")
_G.osuMenu:setClickCallback(function()
  enabled = not enabled
  _G.osuMenu:setTitle(enabled and "🥚" or "🔴")
  note(enabled and "係ON" or "係OFF", "", "", "メニューバーから切替")
end)
_G.osuMenu:setTitle("🥚")
note("係が立った", "", "", "1157番・ホワイトリスト" .. #OK_BUTTONS .. "語／禁止語" .. #NEVER .. "語")
print("✅ 1157 押す係 起動: " .. nowStr())
