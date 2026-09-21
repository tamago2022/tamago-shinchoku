#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""978番「予約閉栓」——セッションが途中で死んでも、孤児タブが溜まらない仕組み。

■ なぜ要るか（2026-09-21 実測）
  たまごさんの枷：**「最後にまとめて閉じる」は禁止。セッションは途中で死ぬ。**
  実際、今日の実測で claude-in-chrome 拡張は
    `tabs_context_mcp` がタブIDを返す → 次の1手で「このセッションのタブグループに無い」
  を **5回中5回** 出した。にもかかわらず recon はタブが 14枚→18枚 に増えたと記録している。
  = **タブは消えていない。消えているのは拡張側のタブグループ登録だけで、タブ本体は孤児として残る。**
  この状態では「セッションが自分で閉じる」は原理的に間に合わない（閉じる相手を見失っている）。

■ 考え方（デッドマン方式）
  タブを**開く前に**「この票の心拍が止まったら、このURLのタブを閉じてよい」と
  外側（Mac上で回り続ける工場）へ**先に**預けておく。
  セッションが生きている間は心拍を打ち続ける。落ちたら心拍が止まり、
  工場が期限切れを見つけて閉じる。**セッションの生死に依存しない。**

  票：status/chrome_reserve/<id>.json   （status/* は .gitignore 済み＝公開リポには入らない）
  掃除：tools/chrome_tab_sweeper.py が票を読んで閉じる（osascriptの口を増やさない）

■ 安全側（憲法は chrome_tab_sweeper.py と同じものを継承する）
  1. 前面タブ（active）は何があっても閉じない。
  2. ウィンドウの最後の1枚は閉じない。
  3. **たまごさんが一度でも前面に出したURLは閉じない**（chrome_tab_history.json の everActive）。
  4. 票に書いた枚数までしか閉じない（同じURLをたまごさんも開いていたら巻き添えにしない）。
  5. 閉じる直前に「そのindexのURLが今も票のURLと一致するか」を確認する（close_tab の SKIP_MOVED）。

■ 使い方（セッション側）
  開く前:  python3 tools/chrome_reserve.py take --id 978 --url "https://example.com" --ttl 120
  作業中:  python3 tools/chrome_reserve.py beat --id 978          # 心拍。ttlより短い間隔で打つ
  終わったら: python3 tools/chrome_reserve.py release --id 978    # 自分で閉じたので票を捨てる
  一覧:    python3 tools/chrome_reserve.py list
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DIR = os.path.join(REPO, "status", "chrome_reserve")
DEFAULT_TTL = 120  # 秒。心拍がこれだけ途切れたら「セッションは死んだ」と見なす


def _now():
    return time.time()


def _path(tid):
    safe = "".join(c for c in str(tid) if c.isalnum() or c in "-_")
    return os.path.join(DIR, safe + ".json")


def take(tid, urls, ttl=DEFAULT_TTL, note=""):
    """タブを開く**前**に呼ぶ。票を置く。"""
    os.makedirs(DIR, exist_ok=True)
    p = _path(tid)
    old = {}
    if os.path.exists(p):
        try:
            with open(p) as f:
                old = json.load(f)
        except Exception:
            old = {}
    merged = list(dict.fromkeys((old.get("urls") or []) + list(urls)))
    doc = {
        "id": str(tid),
        "urls": merged,
        "count": len(merged),
        "ttlSec": int(ttl),
        "createdAt": old.get("createdAt") or _now(),
        "heartbeatAt": _now(),
        "note": note or old.get("note", ""),
    }
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return doc


def beat(tid):
    """心拍。セッションが生きている限り ttl より短い間隔で打つ。"""
    p = _path(tid)
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            doc = json.load(f)
    except Exception:
        return None
    doc["heartbeatAt"] = _now()
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return doc


def release(tid):
    """自分でタブを閉じられたら票を捨てる。"""
    p = _path(tid)
    try:
        os.remove(p)
        return True
    except OSError:
        return False


def load_all():
    out = []
    if not os.path.isdir(DIR):
        return out
    for n in sorted(os.listdir(DIR)):
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(DIR, n)) as f:
                out.append(json.load(f))
        except Exception:
            continue
    return out


def expired_urls():
    """期限切れの票から {url: 閉じてよい最大枚数} を作る。票が無ければ空dict（＝何もしない）。"""
    now = _now()
    hit = {}
    for doc in load_all():
        ttl = int(doc.get("ttlSec") or DEFAULT_TTL)
        if now - float(doc.get("heartbeatAt") or 0) < ttl:
            continue  # まだ生きている
        for u in doc.get("urls") or []:
            u = (u or "").strip()
            if not u:
                continue
            hit.setdefault(u, {"count": 0, "ids": []})
            hit[u]["count"] += 1
            hit[u]["ids"].append(doc.get("id"))
    return hit


def sweep_state():
    """掃除機が「今すぐ走るべきか」を判断するための1行。"""
    docs = load_all()
    exp = expired_urls()
    return {"tickets": len(docs), "expiredUrls": len(exp),
            "urls": sorted(exp.keys())}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("take"); t.add_argument("--id", required=True)
    t.add_argument("--url", action="append", required=True)
    t.add_argument("--ttl", type=int, default=DEFAULT_TTL)
    t.add_argument("--note", default="")
    b = sub.add_parser("beat"); b.add_argument("--id", required=True)
    r = sub.add_parser("release"); r.add_argument("--id", required=True)
    sub.add_parser("list")
    sub.add_parser("state")
    a = ap.parse_args()

    if a.cmd == "take":
        print(json.dumps(take(a.id, a.url, a.ttl, a.note), ensure_ascii=False))
    elif a.cmd == "beat":
        d = beat(a.id)
        print(json.dumps(d, ensure_ascii=False) if d else "票がありません")
    elif a.cmd == "release":
        print("捨てました" if release(a.id) else "票がありません")
    elif a.cmd == "list":
        print(json.dumps(load_all(), ensure_ascii=False, indent=1))
    elif a.cmd == "state":
        print(json.dumps(sweep_state(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
