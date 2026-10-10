#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# kakeibo: 課金なし（ファイルの時刻を数えるだけ・AIも外部APIも呼ばない）
"""Vault（Obsidian tamago_brain）への書き込みの関所（2026-10-11）

━━ なぜ作ったか（たまごさん原文）━━
  「Obsidian が重くならないことが第一。特にスマホで読み込みが遅くなっているのは確か。
   毎回書き込みが入るから、どうにかして」

━━ 実測（2026-10-11・status/vault_karuku/）━━
  直近7日、AIの Write/Edit だけで 372回（1日平均53回・最大107回）。上位は
  作業キュー.md 164回／隙間で拾う仕事.md 35回／留守中の作業ログ.md 28回／00_現在地.md 12回／仕入れノート多数。
  その上に Vault 側のフック（Stop のたびに いま走ってるセッション.md を全書き換え）と、
  工場の tools/（作業キュー.md への追記・留守中の判断待ち.md への追記）が乗っていた。
  書き込み1回ごとに iCloud が同期し、スマホが読み直す。

━━ 決めたこと ━━
  ① 頼まれていない自動の書き込み（台帳・ログ・走行盤・仕入れメモ）は Vault の外
     status/vault_soto/ に書く。MOVED に載っている場所へ AI が書こうとしたら関所が止めて、新しい場所を教える。
  ② 00_現在地.md は「作業ごと」に書かない。子は status/genzaichi_kouho.md に追記するだけ。
     Vault の 00_現在地.md は 1日1回だけ（tools/genzaichi_matome.py が夜に・変化があった時だけ）まとめて書く。
     AI が直接書けるのも 1日1回まで。
  ③ それ以外の Vault への AI の書き込み（たまごさんに頼まれたノート等）は通すが、1日 AI_CAP 回で止める。
  ④ 心臓から20分おきに Vault の更新時刻を数え、工場側の書き込みが 1日 KIKAI_CAP 件を超えたら
     進捗表を赤にする（status/public/vault_kanmon.json の aka）。

━━ 使い方 ━━
    python3 tools/vault_kanmon.py              # 見回り（数える・赤判定・JSONを書く）
    python3 tools/vault_kanmon.py --hook       # 関所（PreToolUse の入力を標準入力で受ける。止めるときは exit 2）
    python3 tools/vault_kanmon.py --self-test  # 逆テスト
  許可された書き手（Python）：tools/genzaichi_matome.py・entaku_kaigi.py・x_kiwa.py・gumroad_sales_sync.py・
    shared_brain_sync.py（いずれも頼まれた成果物か、低頻度）。それ以外の tools/ は Vault に書かない。
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
SOTO = os.path.join(REPO, "status", "vault_soto")
ST = os.path.join(REPO, "status", "vault_kanmon")
PUB = os.path.join(REPO, "status", "public", "vault_kanmon.json")
KOUHO = os.path.join(REPO, "status", "genzaichi_kouho.md")

AI_CAP = 20        # AI（Claude Code 等）が Vault に書いてよい回数／日（関所が数える）
KIKAI_CAP = 30     # 工場側の場所（AI出力/・.claude/・00_現在地.md）で更新されたファイル数／日（見回りが数える）
GENZAICHI_AI_CAP = 1

# Vault内の場所 → Vault外の新しい場所（status/vault_soto/ からの相対）
MOVED = {
    "AI出力/_ルール/作業キュー.md": "作業キュー.md",
    "AI出力/_ルール/隙間で拾う仕事.md": "隙間で拾う仕事.md",
    "AI出力/_ルール/留守中の作業ログ.md": "留守中の作業ログ.md",
    "AI出力/_ルール/留守中の判断待ち.md": "留守中の判断待ち.md",
    "AI出力/_ルール/いま走ってるセッション.md": "いま走ってるセッション.md",
    "AI出力/_ルール/判断待ち検査ログ.md": "判断待ち検査ログ.md",
    "AI出力/_ルール/反映されたのに報告が無い一覧.md": "反映されたのに報告が無い一覧.md",
}
MOVED_PREFIX = {
    "AI出力/仕入れ/": "仕入れ/",
    "AI出力/_ルール/司令塔/": "司令塔/",
}
GENZAICHI = "00_現在地.md"
KIKAI_PREFIX = ("AI出力/", ".claude/", GENZAICHI)


def soto(name):
    """Vault外の置き場の絶対パス（工場の tools/ はこれを使う）"""
    p = os.path.join(SOTO, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def rel_of(path):
    """絶対パス/文字列から Vault 内の相対パスを取る。Vault外なら None"""
    s = str(path or "")
    if "tamago_brain/" not in s:
        return None
    return s.split("tamago_brain/", 1)[1].strip().strip("\"'")


def kimari(rel):
    """その場所への AI の書き込みの扱い：('moved', 新しい場所) / ('genzaichi', None) / ('ok', None)"""
    if rel is None:
        return ("soto", None)
    if rel in MOVED:
        return ("moved", "status/vault_soto/" + MOVED[rel])
    for pre, to in MOVED_PREFIX.items():
        if rel.startswith(pre):
            return ("moved", "status/vault_soto/" + to + rel[len(pre):])
    if rel == GENZAICHI:
        return ("genzaichi", None)
    return ("ok", None)


def _today():
    return time.strftime("%Y-%m-%d")


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ───────────────────────── 関所（PreToolUse）
REDIR = re.compile(r"(?:>>?|\btee(?:\s+-a)?|\bsed\s+-i[^|;&]*?|\btouch\b[^|;&]*?)\s*[\"']?([^\"'|;&\n]*tamago_brain/[^\"'|;&\n]*)")
CPMV = re.compile(r"\b(?:cp|mv|rsync|ditto)\b([^|;&\n]*)")


def write_targets(tool, ti):
    """その道具呼び出しが Vault のどこへ書くか（相対パスの一覧）"""
    out = []
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        r = rel_of(ti.get("file_path") or ti.get("notebook_path"))
        if r is not None:
            out.append(r)
    elif tool in ("Bash", "mcp__workspace__bash"):
        cmd = str(ti.get("command") or "")
        if "tamago_brain/" in cmd:
            for m in REDIR.findall(cmd):
                r = rel_of(m.strip().split(" ")[0] if m.count("tamago_brain/") > 1 else m)
                if r is not None:
                    out.append(r.rstrip())
            # cp / mv は「最後の引数＝行き先」だけを見る（Vaultから読み出すコピーは止めない）
            import shlex
            for m in CPMV.findall(cmd):
                try:
                    args = [a for a in shlex.split(m) if not a.startswith("-")]
                except ValueError:
                    continue
                if len(args) >= 2:
                    r = rel_of(args[-1])
                    if r is not None:
                        out.append(r)
            # python3 -c / open(...,'w') で Vault に書く形
            if re.search(r"open\([^)]*tamago_brain/[^)]*,\s*['\"][wa]", cmd):
                for m in re.findall(r"tamago_brain/([^'\"]+)", cmd):
                    out.append(m)
    return out


def hantei(tool, ti, now_counts=None):
    """止めるなら理由の文字列、通すなら None。now_counts を渡すと数え直しはしない（テスト用）"""
    tg = write_targets(tool, ti)
    if not tg:
        return None, tg
    c = now_counts if now_counts is not None else _load(os.path.join(ST, "hook_%s.json" % _today()), {})
    for r in tg:
        k, to = kimari(r)
        if k == "moved":
            return ("Vault の「%s」は 2026-10-11 に Vault の外へ移した（スマホの Obsidian を重くしないため）。\n"
                    "　書く先：/Users/mac/tamago/tamago-shinchoku/%s（Vault には書かない）" % (r, to)), tg
        if k == "genzaichi" and c.get("genzaichi", 0) >= GENZAICHI_AI_CAP:
            return ("00_現在地.md は 1日1回だけ。今日はもう書かれている。\n"
                    "　更新したいことは /Users/mac/tamago/tamago-shinchoku/status/genzaichi_kouho.md に追記する"
                    "（夜に tools/genzaichi_matome.py が変化があった時だけ Vault へまとめて書く）"), tg
    if c.get("ai", 0) >= AI_CAP:
        return ("今日の Vault への AI の書き込みが上限 %d 回に達した。Vault には書かず、"
                "status/vault_soto/ に置いて報告に場所を書く。" % AI_CAP), tg
    return None, tg


def hook_main():
    raw = sys.stdin.read()
    try:
        inp = json.loads(raw or "{}")
    except Exception:
        return 0
    tool = str(inp.get("tool_name") or "")
    ti = inp.get("tool_input") or {}
    why, tg = hantei(tool, ti)
    if not tg:
        return 0
    p = os.path.join(ST, "hook_%s.json" % _today())
    c = _load(p, {})
    rec = {"at": time.strftime("%F %T"), "tool": tool, "n": len(tg), "kind": [kimari(r)[0] for r in tg]}
    if why:
        c["blocked"] = c.get("blocked", 0) + 1
        _save(p, c)
        _append(os.path.join(ST, "hook.jsonl"), dict(rec, blocked=True))
        sys.stderr.write("★Vault への書き込みを止めた（Vault の関所・2026-10-11）\n　" + why +
                         "\n点検：python3 tools/vault_kanmon.py／逆テスト：python3 tools/vault_kanmon.py --self-test\n")
        return 2
    c["ai"] = c.get("ai", 0) + 1
    if any(kimari(r)[0] == "genzaichi" for r in tg):
        c["genzaichi"] = c.get("genzaichi", 0) + 1
    _save(p, c)
    _append(os.path.join(ST, "hook.jsonl"), rec)
    return 0


def _append(p, d):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ───────────────────────── 見回り（心臓から20分おき）
def bunrui(rel):
    if rel.startswith(".obsidian/"):
        return "app"
    if rel.startswith(".trash/"):
        return "app"
    if rel.startswith(KIKAI_PREFIX):
        return "kikai"
    return "tamago"


def mimawari():
    snap_p = os.path.join(ST, "snapshot.json")
    snap = _load(snap_p, {})
    first = not snap
    new = {}
    n = 0
    tot = 0
    for r, ds, fs in os.walk(VAULT):
        ds[:] = [d for d in ds if d != ".git"]
        for f in fs:
            p = os.path.join(r, f)
            try:
                s = os.stat(p)
            except OSError:
                continue
            rel = os.path.relpath(p, VAULT)
            n += 1
            tot += s.st_size
            new[rel] = [int(s.st_mtime), s.st_size]
    days_p = os.path.join(ST, "days.json")
    days = _load(days_p, {})
    if not first:
        for rel, (mt, sz) in new.items():
            old = snap.get(rel)
            if old is None or old[0] != mt:
                d = time.strftime("%Y-%m-%d", time.localtime(mt))
                if old is not None and mt <= old[0]:
                    continue
                k = bunrui(rel)
                day = days.setdefault(d, {"kikai": 0, "tamago": 0, "app": 0, "kb": 0})
                day[k] += 1
                day["kb"] += sz // 1024
    _save(snap_p, new)
    keep = sorted(days)[-30:]
    days = {k: days[k] for k in keep}
    _save(days_p, days)
    today = _today()
    hk = _load(os.path.join(ST, "hook_%s.json" % today), {})
    td = days.get(today, {"kikai": 0, "tamago": 0, "app": 0, "kb": 0})
    aka = []
    if td["kikai"] > KIKAI_CAP:
        aka.append("Vault：工場側の書き込みが今日 %d 件（上限 %d）。止めて status/vault_soto/ へ" % (td["kikai"], KIKAI_CAP))
    if hk.get("ai", 0) >= AI_CAP:
        aka.append("Vault：AI の書き込みが今日 %d 回で上限（%d）に達し、関所が止めている" % (hk.get("ai", 0), AI_CAP))
    out = {
        "at": time.strftime("%F %H:%M"),
        "label": "Vaultへの書き込み（1日）",
        "today": {"kikai_files": td["kikai"], "tamago_files": td["tamago"], "obsidian_app": td["app"],
                  "ai_hook": hk.get("ai", 0), "ai_blocked": hk.get("blocked", 0)},
        "limit": {"kikai_files": KIKAI_CAP, "ai_hook": AI_CAP, "genzaichi": "1日1回"},
        "vault": {"files": n, "mb": round(tot / 1048576)},
        "days": [{"day": k, "kikai": v["kikai"], "tamago": v["tamago"], "app": v["app"]} for k, v in sorted(days.items())[-8:]],
        "aka": aka,
        "first_run": first,
    }
    _save(PUB, out)
    print(json.dumps(out, ensure_ascii=False))
    return out


# ───────────────────────── 逆テスト
def self_test():
    ng = 0
    V = VAULT + "/"
    cases = [
        ("Write", {"file_path": V + "AI出力/_ルール/作業キュー.md"}, {}, True),
        ("Edit", {"file_path": V + "AI出力/仕入れ/カバー・CM候補_2026-10-12.md"}, {}, True),
        ("Edit", {"file_path": V + "00_現在地.md"}, {}, False),
        ("Edit", {"file_path": V + "00_現在地.md"}, {"genzaichi": 1}, True),
        ("Write", {"file_path": V + "00 inbox/たまごさんに頼まれたノート.md"}, {}, False),
        ("Write", {"file_path": V + "00 inbox/x.md"}, {"ai": AI_CAP}, True),
        ("Write", {"file_path": "/Users/mac/tamago/tamago-shinchoku/status/vault_soto/作業キュー.md"}, {}, False),
        ("Bash", {"command": "echo hi >> \"%sAI出力/_ルール/留守中の作業ログ.md\"" % V}, {}, True),
        ("Bash", {"command": "cat \"%sAI出力/_ルール/作業キュー.md\" | head" % V}, {}, False),
        ("Bash", {"command": "cp \"%sAI出力/_ルール/作業キュー.md\" /tmp/q.md" % V}, {}, False),
        ("Bash", {"command": "cp /tmp/q.md \"%sAI出力/仕入れ/新しいメモ.md\"" % V}, {}, True),
        ("Bash", {"command": "python3 -c \"open('%sAI出力/_ルール/隙間で拾う仕事.md','a').write('x')\"" % V}, {}, True),
    ]
    for tool, ti, cnt, want in cases:
        why, _ = hantei(tool, ti, cnt)
        got = why is not None
        ok = got == want
        ng += 0 if ok else 1
        print("%s %s %s → %s" % ("OK" if ok else "NG", tool, (ti.get("file_path") or ti.get("command"))[-60:], "止める" if got else "通す"))
    print("逆テスト：%s（%d件中 %d件NG）" % ("合格" if ng == 0 else "不合格", len(cases), ng))
    return 0 if ng == 0 else 1


if __name__ == "__main__":
    if "--hook" in sys.argv:
        sys.exit(hook_main())
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    mimawari()
