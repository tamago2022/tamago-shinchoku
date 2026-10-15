#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ポスト＝鍵の置き場（1か所）。2026-10-04・たまごさん指示「鍵はポストに入ってます、という仕組みを作ってくれ」。

選んだ方式：macOS キーチェーン（公式・標準・月0円）＋ この「玄関」（許可した相手だけ取り出せる）＋ 取り出し記録。
  ・鍵の本体は macOS のキーチェーンに暗号化して入る（service=tamago-post）。.env にも、GitHub にも、ログにも出ない。
  ・取り出しは必ずこの玄関を通る（kagi.get が自動で通る＝各スクリプトは今までの書き方のまま）。
  ・玄関は「誰が呼んだか」を親プロセスをたどって調べる。
      許可：工場(/Users/mac/tamago/)・joy-relief-station のスクリプト・Claude Code(Dispatch/子セッション)
      拒否：Codex / Gemini CLI / ChatGPT / Cursor / aider など（呼んだ道のどこかにいたら、許可の道があっても拒否）
  ・誰がいつ何を取り出したか（拒否も）は ~/.tamago/post_audit.jsonl に残す。★値は1文字も書かない。
  ・ChatGPT(Web)・GitHub上のAI・Jules・Codex(クラウド)は、そもそもこのMacの外にいるので、物理的に取れない。

★正直な限界：同じMacの同じユーザーで動くプログラムが、玄関を通らず直接 `security` コマンドを叩けば取れてしまう
  （macOS の仕様。別ユーザー化 or 外部の金庫(1Password/Bitwarden)にしない限り完全には遮れない）。
  この玄関は「うっかり・勝手に」を止めて、通った記録を残す層。完全遮断が要るなら月額の金庫（status/post_hikaku.md）。

使い方（CLI）:
    python3 tools/post.py get NAME          # 値を標準出力へ（許可された相手だけ）
    python3 tools/post.py set NAME          # 値は標準入力から（コマンドラインに値を書かない）
    python3 tools/post.py list              # 名前だけ
    python3 tools/post.py audit [N]         # 直近の取り出し記録
Python から: import post; post.get("NAME")
"""
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
SERVICE = "tamago-post"
TAMAGO = os.path.join(HOME, ".tamago")
INDEX = os.path.join(TAMAGO, "post_index.json")
AUDIT = os.path.join(TAMAGO, "post_audit.jsonl")
POLICY = os.path.join(TAMAGO, "post_allow.json")

DEFAULT_POLICY = {
    # 呼んだ道（親プロセス）のどこかのコマンドにこの文字列があれば「許可の道」
    "allow_cmd_contains": [
        "/Users/mac/tamago/",
        "/Users/mac/Desktop/joy-relief-station/",
        "/Users/mac/.tamago/",
        "/.local/share/claude/versions/",       # Claude Code 本体
        "/Application Support/Claude/",         # Claude デスクトップ（Dispatch・子セッション）
        "/Applications/Claude.app/",
    ],
    # 呼んだ道のどこかの「実行ファイル名」がこれなら、許可の道があっても拒否
    "deny_exec_names": ["codex", "gemini", "gemini-cli", "chatgpt", "cursor", "aider", "jules",
                        "copilot", "windsurf", "goose", "opencode", "amp", "cline"],
    "deny_exec_path_contains": ["/ChatGPT.app/", "/Codex.app/", "/.codex/", "/Cursor.app/", "/Windsurf.app/"],
}

_SAFE = re.compile(r"^[A-Za-z0-9_\-\.=+/:~@]+$")
_cache = {}
_audited = set()


class PostDenied(PermissionError):
    pass


# ---------------------------------------------------------------- 誰が呼んだか
def _chain():
    """自分から親へたどった (pid, 実行ファイル, コマンド全体) の列。"""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return []
    table = {}
    for ln in out.splitlines():
        parts = ln.strip().split(None, 2)
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = (int(parts[1]), parts[2])
    chain, pid, seen = [], os.getpid(), set()
    while pid and pid in table and pid not in seen:
        seen.add(pid)
        ppid, cmd = table[pid]
        chain.append((pid, cmd.split(" ")[0], cmd))
        pid = ppid
    return chain


def _policy():
    try:
        p = json.load(open(POLICY, encoding="utf-8"))
        merged = dict(DEFAULT_POLICY)
        merged.update(p)
        return merged
    except Exception:
        return DEFAULT_POLICY


def decide(chain, pol=None):
    """(許可?, 理由, 呼び元の名札)。値は見ない。"""
    pol = pol or _policy()
    for _pid, exe, cmd in chain:
        base = os.path.basename(exe).lower()
        if base in pol["deny_exec_names"] or any(s in exe for s in pol["deny_exec_path_contains"]):
            return False, "拒否の相手が道にいる: %s" % os.path.basename(exe), base
    for _pid, exe, cmd in chain:
        for s in pol["allow_cmd_contains"]:
            if s in cmd:
                return True, "許可の道: %s" % s, _label(cmd, s)
    return False, "許可された道にいない", (_label(chain[1][2], "") if len(chain) > 1 else "?")


def _label(cmd, marker):
    m = re.search(r"(/Users/mac/[^\s\"']+\.(?:py|sh|mjs|js|command))", cmd)
    if m:
        return m.group(1).replace("/Users/mac/", "~/")
    if "/claude/versions/" in cmd or "Application Support/Claude" in cmd or "Claude.app" in cmd:
        return "claude(Dispatch/子セッション)"
    return (marker or cmd[:60]).strip()


def _audit(name, ok, why, who, op="get"):
    try:
        os.makedirs(TAMAGO, exist_ok=True)
        if os.path.exists(AUDIT) and os.path.getsize(AUDIT) > 5_000_000:
            os.replace(AUDIT, AUDIT + ".1")
        fd = os.open(AUDIT, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), "op": op, "key": name,
                                "ok": ok, "who": who, "why": why, "pid": os.getpid()}, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- キーチェーン
def _enc(v):
    return v if _SAFE.match(v) else "b64:" + base64.b64encode(v.encode()).decode()


def _dec(v):
    return base64.b64decode(v[4:]).decode() if v.startswith("b64:") else v


def _names():
    try:
        return sorted(json.load(open(INDEX, encoding="utf-8")))
    except Exception:
        return []


def _index_add(name):
    names = set(_names())
    names.add(name)
    os.makedirs(TAMAGO, exist_ok=True)
    tmp = INDEX + ".%d.tmp" % os.getpid()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(sorted(names), f)
    os.replace(tmp, INDEX)


def _check_name(name):
    if not re.match(r"^[A-Za-z0-9_\-\.]+$", name or ""):
        raise ValueError("名前に使えない文字があります")


def has(name):
    return name in _names()


def names():
    return _names()


def set(name, value):  # noqa: A001  （値はコマンドラインに出さず、security -i の標準入力で渡す）
    _check_name(name)
    if not value:
        raise ValueError("空の値は入れません")
    ok, why, who = decide(_chain())
    if not ok:
        _audit(name, False, why, who, "set")
        raise PostDenied("ポストに入れる権限がありません: " + why)
    cmd = "add-generic-password -U -s %s -a %s -l %s -w '%s'\n" % (SERVICE, name, "tamago-post/" + name, _enc(value))
    r = subprocess.run(["security", "-i"], input=cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or "error" in (r.stdout + r.stderr).lower():
        _audit(name, False, "キーチェーンに入らなかった", who, "set")
        raise RuntimeError("キーチェーンに入りませんでした（値は表示しません）")
    _index_add(name)
    _cache[name] = value
    _audit(name, True, why, who, "set")


def get(name, default=None):
    """玄関を通って取り出す。許可されていなければ PostDenied。無ければ default。"""
    _check_name(name)
    if name in _cache:
        return _cache[name]
    ok, why, who = decide(_chain())
    first = name not in _audited
    _audited.add(name)
    if not ok:
        _audit(name, False, why, who)
        raise PostDenied("関所：ポストから取り出せません（%s）" % why)
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", name, "-w"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        if first:
            _audit(name, True, "ポストに無い", who)
        return default
    v = _dec(r.stdout.rstrip("\n"))
    _cache[name] = v
    if first:
        _audit(name, True, why, who)
    return v


def fingerprint(value):
    """値そのものを出さずに同一確認するための短い指紋。"""
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def migrate():
    """api_keys.env の鍵をポストへ写し、1本ずつ読み戻して一致を確認する。値は表示しない（名前と本数だけ）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kagi
    src = kagi._parse(kagi.SEIHON)
    moved, bad = [], []
    for k, v in sorted(src.items()):
        if k in kagi.KAGI_DEWA_NAI:
            continue
        put(k, v)
        _cache.pop(k, None)
        if get(k) == v:
            moved.append(k)
        else:
            bad.append(k)
    print("ポストへ写した: %d本 / 一致しなかった: %d本 %s" % (len(moved), len(bad), bad or ""))
    return 0 if not bad else 1


def seal():
    """全部ポストで一致した後にだけ、平文の api_keys.env を鍵置き場の外の保管箱(700)へ『移す』（消さない）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kagi
    src = kagi._parse(kagi.SEIHON)
    miss = [k for k, v in src.items() if k not in kagi.KAGI_DEWA_NAI and get(k) != v]
    if miss:
        print("まだポストと一致しない鍵があるので移しません:", miss)
        return 1
    box = os.path.join(os.path.dirname(kagi.SEIHON), "_post_iko")
    os.makedirs(box, mode=0o700, exist_ok=True)
    os.chmod(box, 0o700)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for fn in os.listdir(os.path.dirname(kagi.SEIHON)):
        if fn.startswith("api_keys.env"):
            os.replace(os.path.join(os.path.dirname(kagi.SEIHON), fn), os.path.join(box, fn + "." + stamp))
    print("平文の api_keys.env を %s へ移しました（消していません。戻す時はここから mv）" % box.replace(HOME, "~"))
    return 0


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "list":
        for n in _names():
            print(n)
        return 0
    if cmd == "migrate":
        return migrate()
    if cmd == "seal":
        return seal()
    if cmd == "audit":
        n = int(argv[2]) if len(argv) > 2 else 20
        try:
            for ln in open(AUDIT, encoding="utf-8").read().splitlines()[-n:]:
                d = json.loads(ln)
                print("%s %s %-28s %s %s" % (d["at"], d["op"], d["key"], "OK" if d["ok"] else "拒否", d["who"]))
        except FileNotFoundError:
            print("記録なし")
        return 0
    if cmd in ("get", "set") and len(argv) > 2:
        try:
            if cmd == "get":
                v = get(argv[2])
                if v is None:
                    print("ポストに無い: " + argv[2], file=sys.stderr)
                    return 3
                sys.stdout.write(v)
                return 0
            set(argv[2], sys.stdin.read().strip())
            print("入れました: " + argv[2])
            return 0
        except PostDenied as e:
            print(str(e), file=sys.stderr)
            return 13
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
