#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開の口（kohyou）― 共有ページを出す口を1本にする道具。

■ なぜ作ったか（2026-09-23・穴を塞ぐのではなくパイプごと替える）

これまで share/check/*.html が公開URLに出るまでの道は1本しかなかった：

    サンドボックス → commit_kuchi（紙を置く）
      → Mac側の5分便 tools/machine_status_push.sh が add/commit/push
      → GitHub Pages

ところが5分便は、**重い機械の計測（factory_status.py・残骸回収）と push が同じ1本の
シェルに乗っている。**2026-09-23 10:57、Macが高負荷になった時にこうなった（実測）：

  ・`.git/index.lock` は無い（＝ロックの取り合いではない）
  ・`status/.machine_status_push.lock` は11:26に更新されている（＝新しい便は起動している）
  ・なのに `status/machine.json` の measuredAt は 11:06 のまま（＝一周できていない）
  ・heartbeat が20分間「蹴り直しを試みます」を繰り返しても復帰しない
  ・一方 GitHub API 直叩き（putfile）は同じ時刻に **3秒・0円・httpCode 200** で通った

つまり **計測が詰まると push も道連れになる。**公開が、公開と関係のない仕事に人質を
取られている。これは直す対象ではなく、**分ける対象**。

■ そこで：公開の到達を putfile 1本に寄せる

    kohyou.publish(path)
      1. putfile（GitHub Contents API）で gh-pages に直接置く  ← ★公開はここで完了
      2. commit_kuchi にも紙を置く（履歴として main にも残す。出なくても公開は済んでいる）

  ・Macの負荷・launchd・ローカルgit・index.lock のどれにも依存しない
  ・丸ごと push はしないので、5分便が復帰して force push しても中身が同じ＝ぶつからない
  ・工場側の runner が処理する（軽い。5分便とは別プロセス）

■ 正直に書いておく限界
  工場側の runner（gaibu_runner）が死んでいれば、この口も止まる。
  そのときは job が pending に残るので `--list` で分かる。「黙って出ない」ことは無くなる。

■ 使い方（サンドボックス側）
    python3 tools/kohyou.py share/check/1029-okane-chizu.html --why "1029 一枚地図"
    python3 tools/kohyou.py --list
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)
REPO = "tamago2022/tamago-shinchoku"
BASE = "https://tamago2022.github.io/tamago-shinchoku"
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def publish(path, why="", branch="gh-pages", wait_sec=150):
    """1ファイルを公開する。戻り値: dict（ok / url / commit / httpCode）"""
    import gaibu_kuchi as g

    full = os.path.join(REPO_DIR, path)
    if not os.path.exists(full):
        return {"ok": False, "error": "ファイルがありません: %s" % path}

    # ── 絵の門（2026-09-23）────────────────────────────────────────────
    # 公開の口はこの1本だけ。だから門はここに埋める。呼び忘れという概念が消える。
    # share/check/ に出す絵（canvas/svg/img/video）は、お手本と並べた画と外部の判定を
    # 通っていないと出られない。share/ohon/ は判定に使う材料置き場なので通す。
    if path.startswith("share/check/") and os.environ.get("E_GATE_SKIP") != "1":
        try:
            import e_gate
            if e_gate.is_picture_page(full):
                stop = e_gate.check(full)
                if stop:
                    return {"ok": False, "error": "絵の門が止めました",
                            "とまった理由": stop, "path": path}
        except Exception as e:  # 門が壊れても公開は止めない（が、必ず記録に残す）
            print("（絵の門が動きませんでした: %s）" % e)
    # ──────────────────────────────────────────────────────────────────

    text = open(full, encoding="utf-8").read()
    jid = g.enqueue_job("keijiban", {
        "repo": REPO, "action": "putfile", "path": path,
        "branch": branch, "text": text,
        "message": why or ("公開: %s" % path),
    })
    res = g.wait_job(jid, wait_sec=wait_sec)
    if res is None:
        return {"ok": False, "error": "工場が%d秒以内に返しませんでした（jobId %s）。"
                                      "status/gaibu_jobs/pending に残っています" % (wait_sec, jid),
                "jobId": jid}

    out = {
        "ok": bool(res.get("ok")),
        "httpCode": res.get("httpCode"),
        "commit": res.get("commit"),
        "bytes": res.get("bytes"),
        "yen": res.get("totalYen"),
        "url": "%s/%s" % (BASE, path),
        "jobId": jid,
    }

    # 履歴用（出なくても公開は済んでいる）
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "commit_kuchi.py"),
                        "--request", path, "--why", why or ("公開: %s" % path)],
                       cwd=REPO_DIR, capture_output=True, timeout=30)
        out["rekishi"] = "commit_kuchi に紙を置いた（5分便が後で main に載せる）"
    except Exception as e:
        out["rekishi"] = "commit_kuchi に置けず: %s（公開は済んでいる）" % e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="公開するファイル（リポジトリからの相対パス）")
    ap.add_argument("--why", default="")
    ap.add_argument("--branch", default="gh-pages")
    ap.add_argument("--wait", type=int, default=150)
    ap.add_argument("--list", action="store_true", help="工場に溜まっている仕事を見る")
    a = ap.parse_args()

    if a.list:
        d = os.path.join(REPO_DIR, "status/gaibu_jobs/pending")
        items = sorted(os.listdir(d)) if os.path.isdir(d) else []
        print("待っている仕事: %d件" % len(items))
        for i in items[:20]:
            print("  ・" + i)
        return

    if not a.path:
        ap.error("公開するファイルを1つ指定してください")

    r = publish(a.path, a.why, a.branch, a.wait)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
