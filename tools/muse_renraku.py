#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Museとの往復（2026-11-18・店主「Museとつながって」）。

つなぎ方（既にMuse側で動いている道をそのまま使う・新しいコネクタは作らない）：
  行き：joy-relief-station に `muse` ラベルの Issue を立てる（Museは1時間ごとに開いている muse の Issue を見て作業する＝#1146）。
  帰り：Museは Issue にコメント＋`done` ラベル、成果物は Release（タグ指定）か Drive に置く。
  工場：この係が依頼の控え status/muse_renraku/irai_*.json を見て、
        Release の添付を status/muse_renraku/uketori/<tag>/ に落とし、Issue の新しいコメントを控え、
        届いたら Dispatch へ1行（status/dispatch_outbox.jsonl）。
  ※ github_watch.py は muse ラベルを工場の発車待ちに積まない（233213番）。帰りを拾うのはこの係だけ。

使い方：
  python3 tools/muse_renraku.py --tick       心臓から（中で10分に1回に間引く）
  python3 tools/muse_renraku.py --ima        今すぐ1回
  python3 tools/muse_renraku.py --self-test
作るもの：status/muse_renraku/uketori/<tag>/（受け取った画像）・status/muse_renraku/irai_*.json の更新
消す役：受け取ったものは完成品の素材。使い終わったら claude_nouhin で納品し、ここは youryou_jougen の上限で見張る。
"""
import json
import os
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(REPO, "status", "muse_renraku")
STAMP = os.path.join(DIR, ".tick_at")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
GH = "https://api.github.com/repos/tamago2022/joy-relief-station"
MAX_BYTES = 60 * 1024 * 1024   # 1ファイルの上限（暴走よけ）


def _token():
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import github_watch
    return github_watch.gh_token()


def _get(url, tok, raw=False):
    r = urllib.request.Request(url)
    r.add_header("Authorization", "Bearer " + tok)
    r.add_header("Accept", "application/octet-stream" if raw else "application/vnd.github+json")
    with urllib.request.urlopen(r, timeout=60) as f:
        return f.read() if raw else json.load(f)


def _dispatch(msg, kind="muse_uketori"):
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "type": kind, "message": msg},
                           ensure_ascii=False) + "\n")


def mitsukeru(irai, release, comments, labels):
    """純粋関数：受け取り状況を判定する（self-test 用）。"""
    assets = [a.get("name") for a in (release or {}).get("assets", [])] if release else []
    want = irai.get("files") or []
    nai = [w for w in want if w not in assets]
    new_c = [c for c in comments if c.get("id") not in set(irai.get("mita_comment", []))]
    return {"assets": assets, "nai": nai, "done": "done" in labels, "new_comments": new_c}


def ichido(tok):
    if not os.path.isdir(DIR):
        return
    for n in sorted(os.listdir(DIR)):
        if not (n.startswith("irai_") and n.endswith(".json")):
            continue
        p = os.path.join(DIR, n)
        irai = json.load(open(p, encoding="utf-8"))
        if irai.get("owari"):
            continue
        num, tag = irai["issue"], irai.get("tag")
        try:
            rel = _get("%s/releases/tags/%s" % (GH, tag), tok) if tag else None
        except Exception:
            rel = None
        iss = _get("%s/issues/%s" % (GH, num), tok)
        coms = _get("%s/issues/%s/comments?per_page=100" % (GH, num), tok)
        coms = [c for c in coms if "<!-- tamago-factory -->" not in (c.get("body") or "")]
        labels = [l["name"] for l in iss.get("labels", [])]
        r = mitsukeru(irai, rel, coms, labels)
        got = []
        if rel:
            out = os.path.join(DIR, "uketori", tag)
            os.makedirs(out, exist_ok=True)
            for a in rel.get("assets", []):
                dst = os.path.join(out, os.path.basename(a["name"]))
                if os.path.exists(dst) or a.get("size", 0) > MAX_BYTES:
                    continue
                data = _get(a["url"], tok, raw=True)
                open(dst, "wb").write(data)
                got.append(a["name"])
        for c in r["new_comments"]:
            irai.setdefault("mita_comment", []).append(c["id"])
            irai.setdefault("henji", []).append({"at": c["created_at"], "body": (c.get("body") or "")[:3000]})
        if got:
            irai.setdefault("uketotta", []).extend(got)
        if got or r["new_comments"]:
            _dispatch("Museから返事 #%s：%s%s｜%s" % (
                num, ("受け取り %d件 → status/muse_renraku/uketori/%s/ " % (len(got), tag)) if got else "",
                ("コメント %d件" % len(r["new_comments"])) if r["new_comments"] else "",
                irai.get("url", "")))
        if r["done"] and not r["nai"]:
            irai["owari"] = time.strftime("%F %T")
        irai["mita_at"] = time.strftime("%F %T")
        json.dump(irai, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def self_test():
    irai = {"files": ["a.png", "b.png"], "mita_comment": [1]}
    r = mitsukeru(irai, {"assets": [{"name": "a.png"}]}, [{"id": 1}, {"id": 2}], ["muse"])
    assert r["nai"] == ["b.png"] and not r["done"] and [c["id"] for c in r["new_comments"]] == [2]
    r = mitsukeru(irai, None, [], ["muse", "done"])
    assert r["nai"] == ["a.png", "b.png"] and r["done"]
    print("muse_renraku self-test OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        self_test()
        sys.exit(0)
    if "--tick" in a:
        try:
            if time.time() - os.path.getmtime(STAMP) < 600:
                sys.exit(0)
        except OSError:
            pass
        os.makedirs(DIR, exist_ok=True)
        open(STAMP, "w").write(time.strftime("%F %T"))
    ichido(_token())
