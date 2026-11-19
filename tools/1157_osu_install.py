#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1157番「代わりに押す係」を入れる係（0円・可逆・冪等）

たまごさんの手は **一生で1回だけ**（macOSのアクセシビリティの許可）。
そこだけはOSが人の指を要求するので機械では取れない。それ以外は全部この係がやる。

入れるもの（3段）:
  1段 Claude Code の auto mode（公式・0円）
      ・Anthropic公式が classifier で代わりに判断する仕組み。Pro/Max/Teamの既定モード。
        出典 https://code.claude.com/docs/en/permission-modes
             https://www.anthropic.com/engineering/claude-code-auto-mode
      ・ここで「絶対に通さないもの」を settings.json に書き足す。
  2段 Hammerspoon の押す係（tools/1157_osu_kakari.lua）
      ・デスクトップアプリの許可ダイアログを、ホワイトリスト＋禁止語で絞って押す。
      ・押した／押さなかったを status/1157/oshita.jsonl に必ず残す。
  3段 残った「本人しか押せない」ものを月1回の1画面へ（tools/1157_ketsusai.py）

使い方:
    python3 tools/1157_osu_install.py --check     # 今どうなっているか見るだけ
    python3 tools/1157_osu_install.py --install   # 入れる
    python3 tools/1157_osu_install.py --uninstall # 元に戻す
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_SETTINGS = os.path.join(HOME, ".claude", "settings.json")
HS_DIR = os.path.join(HOME, ".hammerspoon")
HS_INIT = os.path.join(HS_DIR, "init.lua")
HS_MINE = os.path.join(HS_DIR, "tamago_osu.lua")
SRC_LUA = os.path.join(REPO, "tools", "1157_osu_kakari.lua")
MARK = "-- 1157 tamago osu kakari"

# auto mode に渡す「絶対に通さない」＝不可逆な4つ。
# 公式の block rules に足す形（claude auto-mode defaults の既定に上書きではなく追記）。
NEVER = [
    "データの削除（rm -rf／ゴミ箱を空にする／リポジトリやテーブルの削除／force push）",
    "お金が動く操作（課金・購入・送金・サブスクの契約や解約）",
    "外部への公開（SNS投稿・サイトの公開・Gist・共有リンクの発行）",
    "パスワードや秘密鍵そのものの入力・送信・貼り付け",
]


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".1157.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def check():
    out = {}
    s = read_json(CLAUDE_SETTINGS)
    out["claude_settings_在る"] = os.path.exists(CLAUDE_SETTINGS)
    out["defaultMode"] = (s.get("permissions") or {}).get("defaultMode")
    out["1157の禁止ルールが入っている"] = bool(
        (s.get("autoMode") or {}).get("tamago1157"))
    out["Hammerspoon入っている"] = os.path.isdir("/Applications/Hammerspoon.app")
    out["押す係のluaが置かれている"] = os.path.exists(HS_MINE)
    out["init.luaから呼ばれている"] = (
        os.path.exists(HS_INIT) and MARK in open(HS_INIT, encoding="utf-8").read())
    log = os.path.join(REPO, "status", "1157", "oshita.jsonl")
    out["押した記録"] = sum(1 for _ in open(log, encoding="utf-8")) if os.path.exists(log) else 0
    return out


def install():
    done = []

    # 1段：Claude Code の auto mode に「絶対に通さない4つ」を足す
    s = read_json(CLAUDE_SETTINGS)
    perms = s.setdefault("permissions", {})
    if perms.get("defaultMode") != "auto":
        perms["defaultMode"] = "auto"
        done.append("settings.json の permissions.defaultMode を auto に")
    am = s.setdefault("autoMode", {})
    am["tamago1157"] = True
    rules = am.setdefault("blockRules", [])
    for r in NEVER:
        if r not in rules:
            rules.append(r)
    done.append("auto mode の block rules に不可逆な4つを追記（%d本）" % len(rules))
    write_json(CLAUDE_SETTINGS, s)

    # 2段：Hammerspoon の押す係
    if not os.path.isdir("/Applications/Hammerspoon.app"):
        if shutil.which("brew"):
            subprocess.run(["brew", "install", "--cask", "hammerspoon"],
                           capture_output=True, text=True, timeout=600)
            done.append("Hammerspoon を brew で入れた" if os.path.isdir(
                "/Applications/Hammerspoon.app") else "Hammerspoon の導入に失敗")
        else:
            done.append("brew が無いので Hammerspoon を入れられない")
    os.makedirs(HS_DIR, exist_ok=True)
    if os.path.exists(SRC_LUA):
        shutil.copyfile(SRC_LUA, HS_MINE)
        done.append("押す係の lua を ~/.hammerspoon/tamago_osu.lua に置いた")
    init = open(HS_INIT, encoding="utf-8").read() if os.path.exists(HS_INIT) else ""
    if MARK not in init:
        with open(HS_INIT, "a", encoding="utf-8") as f:
            f.write("\n%s\nrequire(\"tamago_osu\")\n" % MARK)
        done.append("init.lua から呼ぶ1行を足した")

    # 3段：記録の置き場
    os.makedirs(os.path.join(REPO, "status", "1157"), exist_ok=True)
    return done


def uninstall():
    done = []
    s = read_json(CLAUDE_SETTINGS)
    if (s.get("autoMode") or {}).get("tamago1157"):
        am = s["autoMode"]
        am.pop("tamago1157", None)
        am["blockRules"] = [r for r in am.get("blockRules", []) if r not in NEVER]
        if not am.get("blockRules"):
            am.pop("blockRules", None)
        if not am:
            s.pop("autoMode", None)
        write_json(CLAUDE_SETTINGS, s)
        done.append("settings.json から1157ぶんを外した（defaultModeは触らない）")
    if os.path.exists(HS_MINE):
        os.remove(HS_MINE)
        done.append("lua を消した")
    if os.path.exists(HS_INIT):
        t = open(HS_INIT, encoding="utf-8").read()
        if MARK in t:
            t = t.replace("\n%s\nrequire(\"tamago_osu\")\n" % MARK, "\n")
            open(HS_INIT, "w", encoding="utf-8").write(t)
            done.append("init.lua の呼び出しを外した")
    return done or ["入っていなかった"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    if a.install:
        for line in install():
            print("・" + line)
        print("\n残った本人の手：macOSの「設定→プライバシーとセキュリティ→アクセシビリティ」で")
        print("Hammerspoon をONにする。**これだけは一生で1回。**OSが人の指を要求する。")
    elif a.uninstall:
        for line in uninstall():
            print("・" + line)
    else:
        print(json.dumps(check(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
