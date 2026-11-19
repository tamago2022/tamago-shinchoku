#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1180号【関所の窓口】読んだ合言葉を置く／合格しているかを見る。2026-09-28

関所の本体は tools/stop_kanmon/1180_hikitsugi_kanmon.mjs（PreToolUseフック）。
こちらは「読んだ」と言うための窓口と、他の関所から呼ばれる --check。

  python3 tools/1180_hikitsugi_kanmon.py --yonda たまご     # 合言葉を置く
  python3 tools/1180_hikitsugi_kanmon.py --check            # 0=本日合格済み／1=未合格
  python3 tools/1180_hikitsugi_kanmon.py --aikotoba         # 今日の合言葉を表示（デバッグ用）
  python3 tools/1180_hikitsugi_kanmon.py --shiken           # 関所の逆テスト（止まるべき時に止まるか）

★逆テスト（--shiken）を必ず通すこと。
  「緑は無実の証明ではない。違反を仕込んで赤になるまで確認する」（既存の教訓）
"""
import argparse
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
AIKOTOBA = os.path.join(ST, "1180_aikotoba.json")
YONDA_DIR = os.path.join(ST, "1180_yonda")
PASSED = os.path.join(YONDA_DIR, "_passed.json")
HOOK = os.path.join(HERE, "stop_kanmon", "1180_hikitsugi_kanmon.mjs")
JST = datetime.timezone(datetime.timedelta(hours=9))


def kyou():
    return datetime.datetime.now(JST).date().isoformat()


def machi_aikotoba():
    try:
        with io.open(AIKOTOBA, encoding="utf-8") as f:
            a = json.load(f)
        if a.get("date") == kyou():
            return a.get("aikotoba")
    except Exception:
        pass
    return None


def sid():
    for k in ("CLAUDE_SESSION_ID", "SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        v = os.environ.get(k)
        if v:
            return v
    return "cli"


def cmd_yonda(word):
    want = machi_aikotoba()
    if not want:
        print("【1180】今日の合言葉がまだ作られていません（心臓が回っていない可能性）。"
              "先に `python3 tools/1180_hikitsugi_ima.py` を1回叩いてください。")
        return 1
    if (word or "").strip() != want:
        print("【1180】合言葉が違います。status/hikitsugi_ima.md の0章を読んでください。")
        return 1
    os.makedirs(YONDA_DIR, exist_ok=True)
    s = sid()
    data = {"sessions": {}}
    try:
        with io.open(PASSED, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    data.setdefault("sessions", {})[s] = {
        "date": kyou(), "aikotoba": want,
        "at": datetime.datetime.now(JST).isoformat(timespec="seconds"),
    }
    with io.open(PASSED, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    # 端末のsession_idが取れない環境（CLAUDE_SESSION_IDが無い）向けの当日札。
    # ★弱点：この札は当日中なら他のセッションも通してしまう。正直に status/1180_hikitsugi_shikumi.md に書いてある。
    with io.open(os.path.join(YONDA_DIR, "kyou.txt"), "w", encoding="utf-8") as f:
        f.write("%s %s\n" % (want, kyou()))
    print("【1180】合格。関所を通れます（session=%s）。" % s)
    return 0


def cmd_check():
    want = machi_aikotoba()
    if not want:
        print("1180_CHECK: OK(素通り) - 今日の合言葉が未生成なので判定しません")
        return 0
    try:
        with io.open(PASSED, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        print("1180_CHECK: NG - まだ誰も引き継ぎを読んでいません")
        return 1
    for s, r in (data.get("sessions") or {}).items():
        if r.get("date") == kyou() and r.get("aikotoba") == want:
            print("1180_CHECK: OK - 本日合格済み（%s / %s）" % (s, r.get("at")))
            return 0
    print("1180_CHECK: NG - 今日まだ合格していません")
    return 1


def _hook(tool, tool_input, session):
    p = subprocess.run(
        ["node", HOOK],
        input=json.dumps({"tool_name": tool, "tool_input": tool_input,
                          "session_id": session}),
        capture_output=True, text=True, timeout=20,
    )
    return p.returncode, (p.stderr or "").strip()


def cmd_shiken():
    """逆テスト：止まるべき時に止まり、通すべき道具は通るか。"""
    want = machi_aikotoba()
    if not want:
        print("【1180・逆テスト】今日の合言葉が無いので先に生成します")
        subprocess.run([sys.executable, os.path.join(HERE, "1180_hikitsugi_ima.py")])
        want = machi_aikotoba()
    ng = 0
    fake = "shiken-%s" % datetime.datetime.now(JST).strftime("%H%M%S")

    rc, err = _hook("Edit", {"file_path": "/tmp/x.txt"}, fake)
    ok = rc == 2
    print("① 読んでいない担当が Edit を使う → %s（rc=%d・止まるべき）" % ("赤で止まった OK" if ok else "★通ってしまった NG", rc))
    if not ok:
        ng += 1
    elif "合言葉" not in err:
        print("   ※理由文に合言葉の案内が出ていません")

    rc, _ = _hook("Read", {"file_path": "/tmp/x.txt"}, fake)
    ok = rc == 0
    print("② 読んでいない担当が Read を使う → %s（rc=%d・通すべき）" % ("通った OK" if ok else "★止まった NG", rc))
    if not ok:
        ng += 1

    rc, _ = _hook("Write", {"file_path": os.path.join(YONDA_DIR, fake + ".txt")}, fake)
    ok = rc == 0
    print("③ 合言葉の札を書く Write → %s（rc=%d・通すべき）" % ("通った OK" if ok else "★止まった NG", rc))
    if not ok:
        ng += 1

    # 合言葉を置いてから、同じ Edit をやり直す
    os.makedirs(YONDA_DIR, exist_ok=True)
    card = os.path.join(YONDA_DIR, fake + ".txt")
    with io.open(card, "w", encoding="utf-8") as f:
        f.write("%s\n" % want)
    rc, _ = _hook("Edit", {"file_path": "/tmp/x.txt"}, fake)
    ok = rc == 0
    print("④ 合言葉を置いた後の Edit → %s（rc=%d・通すべき）" % ("通った OK" if ok else "★止まった NG", rc))
    if not ok:
        ng += 1

    with io.open(card, "w", encoding="utf-8") as f:
        f.write("てきとうな言葉\n")
    rc, _ = _hook("Edit", {"file_path": "/tmp/x.txt"}, fake + "-b")
    ok = rc == 2
    print("⑤ でたらめな合言葉 → %s（rc=%d・止まるべき）" % ("赤で止まった OK" if ok else "★通ってしまった NG", rc))
    if not ok:
        ng += 1
    try:
        os.remove(card)
    except Exception:
        pass

    print("")
    print("1180_SHIKEN: %s（NG %d件）" % ("PASS" if ng == 0 else "FAIL", ng))
    return 0 if ng == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yonda")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--aikotoba", action="store_true")
    ap.add_argument("--shiken", action="store_true")
    a = ap.parse_args()
    if a.yonda:
        return cmd_yonda(a.yonda)
    if a.check:
        return cmd_check()
    if a.aikotoba:
        print(machi_aikotoba() or "（未生成）")
        return 0
    if a.shiken:
        return cmd_shiken()
    ap.error("--yonda / --check / --aikotoba / --shiken のいずれか")


if __name__ == "__main__":
    sys.exit(main())
