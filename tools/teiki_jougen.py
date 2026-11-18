#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AIを呼ぶ定期は1日2回まで（2026-11-19 店主「1日2回でいい、週14回でいい」）の見張り。AIは呼ばない。

なぜ要るか（実測 11/12〜11/18 の会話ログ）：
  Claude Code の定期タスク「rusuban-mimawari-30min」（留守番の見回り）は 10/11 に中身を「停止済み」に
  書き換えただけで、予定は有効のまま。30分おきに Opus の会話を起こし「停止済み」と返すだけで 1日48回・週336回、
  1回あたり約4万トークンのキャッシュ書き込み。アプリは scheduled-tasks.json の enabled を自分で true に書き戻し、
  台帳から行を消しても戻す（11/19 実測）。止める確かな方法は「中身 SKILL.md が無い」＝アプリが
  start_failed / task_file_missing で会話を作らないこと。

やること（1日1回・心臓から）：
  1) ~/.claude/scheduled-tasks/<止めた名前>/SKILL.md と ~/Claude/Scheduled/<止めた名前>/SKILL.md が
     戻っていたら ~/.tamago/backup/teiki_jougen/ へ移す（消さない）。
  2) 直近24時間の会話ログ（~/.claude/projects・Cowork の会話）の頭だけ読み、定期の出どころ別に数える。
     2回を超えたものがあれば Dispatch へ1行（status/dispatch_outbox.jsonl）。
  結果 status/public/teiki_jougen.json。
使い方：python3 tools/teiki_jougen.py [--self-test]
作るもの：status/public/teiki_jougen.json（上書き）・控え ~/.tamago/backup/teiki_jougen/（移した時だけ）。
"""
import glob
import json
import os
import re
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "public", "teiki_jougen.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
HOME = os.path.expanduser("~")
BACKUP = os.path.join(HOME, ".tamago", "backup", "teiki_jougen")
TOMETA = ["rusuban-mimawari-30min"]          # 止めた定期タスク（中身を置かせない）
JOUGEN = 2                                    # 1日の上限
# 出どころ（会話の最初の依頼文の頭で見分ける）。仕事そのもの（工場の子・検品）はここに入れない。
TEIKI = [
    ("留守番の見回り", re.compile(r'scheduled-task name=\\?"rusuban')),
    ("ほかの定期タスク", re.compile(r'scheduled-task name=\\?"(?!rusuban|weekly-reset)')),
    ("週枠リセットの合図", re.compile(r'scheduled-task name=\\?"weekly-reset')),
    ("進捗表の見出し係(hyoudai)", re.compile(r"工場の進捗表の題名係")),
    ("ログイン確認(auth_keeper)", re.compile(r"^1\+1は？")),
    ("曲名ローマ字(1192)", re.compile(r"^You romanize")),
]


def skill_paths(name):
    return [os.path.join(HOME, ".claude", "scheduled-tasks", name, "SKILL.md"),
            os.path.join(HOME, "Claude", "Scheduled", name, "SKILL.md")]


def mamoru(home=None):
    """止めた定期タスクの中身が戻っていたら控えへ移す。移したパスの一覧を返す。"""
    moved = []
    for name in TOMETA:
        for p in skill_paths(name):
            if home:
                p = p.replace(HOME, home, 1)
            if os.path.isfile(p):
                d = os.path.join(BACKUP if not home else os.path.join(home, "bk"), name)
                os.makedirs(d, exist_ok=True)
                shutil.move(p, os.path.join(d, "SKILL.md.%s" % time.strftime("%Y%m%d%H%M")))
                moved.append(p)
    return moved


def atama(f):
    try:
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for i, l in enumerate(fh):
                if i > 30:
                    break
                if '"user"' not in l and "scheduled-task" not in l:
                    continue
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                c = d.get("content") if isinstance(d.get("content"), str) else None
                if c is None and d.get("type") == "user":
                    c = d.get("message", {}).get("content")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                if c:
                    return c.strip()[:400]
    except Exception:
        pass
    return ""


def kazoeru(roots, since):
    cnt = {k: 0 for k, _ in TEIKI}
    for r in roots:
        for f in glob.glob(os.path.join(r, "**", "*.jsonl"), recursive=True):
            if f.endswith("audit.jsonl") or "/subagents/" in f:
                continue
            try:
                if os.path.getctime(f) < since:
                    continue
            except Exception:
                continue
            h = atama(f)
            for k, rx in TEIKI:
                if rx.search(h):
                    cnt[k] += 1
                    break
    return cnt


def main():
    moved = mamoru()
    roots = [os.path.join(HOME, ".claude", "projects"),
             os.path.join(HOME, "Library", "Application Support", "Claude", "local-agent-mode-sessions")]
    cnt = kazoeru(roots, time.time() - 86400)
    over = {k: v for k, v in cnt.items() if v > JOUGEN}
    res = {"at": time.strftime("%Y-%m-%d %H:%M"), "jougen_1nichi": JOUGEN, "24jikan": cnt, "koeta": over,
           "modoshita_nakami": moved,
           "note": "AIを呼ぶ定期は1日2回まで（2026-11-19 店主）。超えたものは Dispatch へ1行。止めた定期の中身が戻っていたら控えへ移す。"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    if over or moved:
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": "teiki_jougen",
               "title": "AIを呼ぶ定期が1日2回を超えた" if over else "止めた定期の中身が戻っていた",
               "message": "超えた：%s／戻っていて控えへ移した：%s" % (over, moved),
               "urls": ["https://tamago2022.github.io/tamago-shinchoku/share/check/teiki.html"]}
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(res, ensure_ascii=False))


def selftest():
    import tempfile
    t = tempfile.mkdtemp(prefix="teiki_jougen_")
    try:
        sk = os.path.join(t, ".claude", "scheduled-tasks", "rusuban-mimawari-30min")
        os.makedirs(sk)
        open(os.path.join(sk, "SKILL.md"), "w").write("x")
        moved = mamoru(home=t)
        assert len(moved) == 1 and not os.path.exists(os.path.join(sk, "SKILL.md")), moved
        assert mamoru(home=t) == []
        p = os.path.join(t, "proj")
        os.makedirs(p)
        for i, txt in enumerate(['<scheduled-task name="rusuban-mimawari-30min">', "1+1は？数字だけ", "ふつうの仕事"]):
            with open(os.path.join(p, "%d.jsonl" % i), "w") as f:
                f.write(json.dumps({"type": "user", "message": {"content": txt}}) + "\n")
        c = kazoeru([p], time.time() - 60)
        assert c["留守番の見回り"] == 1 and c["ログイン確認(auth_keeper)"] == 1 and sum(c.values()) == 2, c
        print("teiki_jougen self-test OK")
    finally:
        shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    selftest() if "--self-test" in sys.argv else main()
