#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
コミットの口（commit_kuchi） ― 「コミットする口を1本だけにする」道具。

■ なぜ作ったか（2026-09-22・穴を塞ぐのではなくパイプごと替える）

Cowork（サンドボックス）のセッションが、マウント越しに自分で `git add` / `git commit` を
叩いていた。ところが Mac 側では5分便（tools/machine_status_push.sh）が同じリポジトリで
常に add/commit している。2つが同時に走ると `.git/index.lock` の取り合いになり、
さらに悪いことに **サンドボックスからは残った index.lock を unlink できない**
（Operation not permitted）。結果、工場のgitが丸ごと止まる。

これまでは「残ったロックを後から消す」（git_lock_reaper.py／5分便の find -delete）で
穴を塞いでいた。だが2026-09-22だけで何度も再発した。**塞ぎ方が間違っている。**
ロックが残るのは、**gitを叩く口が2つある**からであって、消し方の問題ではない。

そこで口を1本にする：

    サンドボックス側 : git を一切叩かない。「これを載せてください」と紙を置くだけ
                       （status/commit_inbox/*.json ＝ ただのファイル書き込み）
    Mac側の5分便     : その紙を回収して `git add -f` する。commit / push は
                       いままで通り5分便が1本だけ持つ

これで .git に触るプロセスは **Mac側の5分便ただ1つ** になる。ロックの取り合いは
「起きたら消す」ではなく「起きようがない」になる。

■ 使い方

  サンドボックス側（紙を置くだけ・gitを叩かない）:
      python3 tools/commit_kuchi.py --request status/oni_baseline.json --why "鬼監督の借金台帳"

  Mac側（5分便が自動で呼ぶ。人が叩くことは基本ない）:
      python3 tools/commit_kuchi.py --drain

  いま何枚たまっているか見るだけ:
      python3 tools/commit_kuchi.py --list

  自己試験:
      python3 tools/commit_kuchi.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INBOX = REPO / "status" / "commit_inbox"
DONE = INBOX / "done"
REJECT = INBOX / "rejected"
LOG = REPO / "status" / "commit_kuchi.log"

# 1MB超は公開に載せない（5分便の既存ルールと同じ顔ぶれ）
MAX_BYTES = 1024 * 1024

# 置いてはいけない場所。ここに当たる紙は回収せず rejected へ落とす。
FORBIDDEN_PREFIXES = (
    ".git/",
    ".git",
    "joy-relief-station",   # ★公開リポジトリにしない約束のもの
    "node_modules/",
    ".env",
)
FORBIDDEN_SUFFIXES = (".pyc", ".lock", ".key", ".pem")


def _now() -> str:
    return datetime.now().strftime("%F %T")


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{_now()} {msg}\n")
    except Exception:
        pass


def _rel(p: str) -> str:
    """リポジトリからの相対パスに正規化する。外に出ていたら空文字を返す。"""
    try:
        ap = Path(p)
        if not ap.is_absolute():
            ap = REPO / ap
        ap = ap.resolve()
        return str(ap.relative_to(REPO))
    except Exception:
        return ""


def judge(rel: str) -> tuple[bool, str]:
    """1本のパスを載せてよいか判定する。（載せてよいか, 理由）"""
    if not rel:
        return False, "リポジトリの外を指している"
    for bad in FORBIDDEN_PREFIXES:
        if rel == bad.rstrip("/") or rel.startswith(bad):
            return False, f"触ってはいけない場所（{bad}）"
    for bad in FORBIDDEN_SUFFIXES:
        if rel.endswith(bad):
            return False, f"載せない種類のファイル（{bad}）"
    ap = REPO / rel
    if not ap.exists():
        return False, "そのファイルが無い"
    if ap.is_file() and ap.stat().st_size > MAX_BYTES:
        return False, f"大きすぎる（{ap.stat().st_size}バイト・1MB超）"
    return True, "ok"


# ---------------------------------------------------------------- request

def cmd_request(paths: list[str], why: str, who: str) -> int:
    INBOX.mkdir(parents=True, exist_ok=True)
    rels, rejected = [], []
    for p in paths:
        r = _rel(p)
        ok, reason = judge(r)
        (rels if ok else rejected).append(r or p if ok else f"{p}（{reason}）")
    if not rels:
        print("載せられるファイルが1本もありませんでした：")
        for r in rejected:
            print("  ×", r)
        return 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    salt = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    req = {
        "askedAt": _now(),
        "from": who,
        "why": why,
        "paths": rels,
    }
    out = INBOX / f"{stamp}-{salt}.json"
    out.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"紙を置きました：{out.relative_to(REPO)}")
    for r in rels:
        print("  ・", r)
    for r in rejected:
        print("  ×（載せません）", r)
    print("Mac側の5分便が次に回ったときに載ります。gitはこちらから叩きません。")
    _log(f"📥 受付 {out.name} {len(rels)}本 from={who} why={why}")
    return 0


# ------------------------------------------------------------------ drain

def _git(args: list[str]) -> tuple[int, str]:
    pr = subprocess.run(["git"] + args, cwd=str(REPO),
                        capture_output=True, text=True)
    return pr.returncode, (pr.stdout + pr.stderr).strip()


def cmd_drain(quiet: bool = False) -> int:
    """Mac側だけで走る。紙を回収して git add -f する。commit は5分便に任せる。"""
    if not INBOX.exists():
        return 0
    papers = sorted(q for q in INBOX.glob("*.json") if q.is_file())
    if not papers:
        return 0

    DONE.mkdir(parents=True, exist_ok=True)
    REJECT.mkdir(parents=True, exist_ok=True)

    staged_total = 0
    for paper in papers:
        try:
            req = json.loads(paper.read_text(encoding="utf-8"))
        except Exception as e:
            paper.rename(REJECT / paper.name)
            _log(f"🛑 読めない紙 {paper.name}: {e}")
            continue

        good, bad = [], []
        for p in req.get("paths", []):
            r = _rel(p)
            ok, reason = judge(r)
            (good if ok else bad).append(r if ok else f"{p}（{reason}）")

        added = []
        for r in good:
            rc, out = _git(["add", "-f", "--", r])
            if rc == 0:
                added.append(r)
            else:
                bad.append(f"{r}（git addが失敗: {out[:120]}）")

        req["drainedAt"] = _now()
        req["added"] = added
        req["rejected"] = bad
        dest = (DONE if added else REJECT) / paper.name
        dest.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
        paper.unlink(missing_ok=True)

        staged_total += len(added)
        _log(f"✅ 回収 {paper.name} 載せた{len(added)}本 断った{len(bad)}本 why={req.get('why','')}")
        if not quiet:
            print(f"{paper.name}: 載せた {len(added)} / 断った {len(bad)}")
            for r in bad:
                print("   ×", r)

    if not quiet and staged_total:
        print(f"合計 {staged_total} 本をステージしました。commitは5分便が1本だけ持ちます。")
    return 0


# ------------------------------------------------------------------- list

def cmd_list() -> int:
    papers = sorted(INBOX.glob("*.json")) if INBOX.exists() else []
    if not papers:
        print("待っている紙はありません。")
        return 0
    print(f"待っている紙 {len(papers)} 枚：")
    for p in papers:
        try:
            req = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            print(f"  ・{p.name}（読めない）")
            continue
        print(f"  ・{p.name}  {req.get('askedAt','')}  {req.get('why','')}")
        for r in req.get("paths", []):
            print(f"      {r}")
    return 0


# -------------------------------------------------------------- self-test

def cmd_self_test() -> int:
    cases = [
        (".git/config", False, "gitの中身"),
        (".git/index.lock", False, "ロックそのもの"),
        ("joy-relief-station/index.html", False, "公開しない約束のもの"),
        ("tools/__pycache__/x.cpython-310.pyc", False, "pyc"),
        ("../etc/passwd", False, "リポジトリの外"),
        ("/etc/passwd", False, "絶対パスで外"),
        ("tools/commit_kuchi.py", True, "自分自身は載せてよい"),
        ("tools/oni_gate.py", True, "ふつうの道具"),
        ("status/no_such_file_zzz.json", False, "無いファイル"),
    ]
    ng = 0
    for path, want, name in cases:
        rel = _rel(path)
        got, reason = judge(rel)
        mark = "○" if got == want else "×"
        if got != want:
            ng += 1
        print(f"{mark} {name}: 期待={'載せる' if want else '断る'} 実際={'載せる' if got else '断る'}（{reason}）")
    print()
    if ng:
        print(f"{len(cases)}問中 {len(cases)-ng}問 合格 ― ★{ng}問おちました")
        return 1
    print(f"{len(cases)}問中 {len(cases)}問 合格")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="コミットの口。gitを叩く口を1本にする。")
    ap.add_argument("--request", nargs="+", metavar="PATH", help="載せてほしいファイル（紙を置くだけ）")
    ap.add_argument("--why", default="", help="なぜ載せるのか（1行）")
    ap.add_argument("--from", dest="who", default=os.environ.get("TAMAGO_SESSION", "cowork"), help="誰が頼んだか")
    ap.add_argument("--drain", action="store_true", help="【Mac側専用】紙を回収して git add -f する")
    ap.add_argument("--list", action="store_true", help="待っている紙を見る")
    ap.add_argument("--self-test", action="store_true", help="判定の自己試験")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return cmd_self_test()
    if a.list:
        return cmd_list()
    if a.drain:
        return cmd_drain(a.quiet)
    if a.request:
        return cmd_request(a.request, a.why, a.who)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
