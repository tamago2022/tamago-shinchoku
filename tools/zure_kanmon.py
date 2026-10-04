#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ズレ関所（2026-10-04・たまごさん指示）：カードの「測れば分かるズレ」を公開の前に実測し、1つでもあれば止める。

たまごさん：「バッジのサイズとか直らなかったんだ。あれはもう苦手とか関係ないでしょ。
             サムネイルの高さが違うだとか、そういうのはいくつもあるよ」
→ 見た目の好みではなく、サムネの高さ・黒帯・バッジ/♡/▶の大きさと余白（上＝左）を px で測る。
   測る本体は joy-relief-station の scripts/measure-card-geometry.mjs（Playwright・ヘッドレス専用ブラウザ。
   たまごさんの Chrome・画面には一切触れない）。ここはそれを「公開の流れ」に差し込む係。

使い方:
  python3 zure_kanmon.py pre  <作業フォルダ|コミットSHA>   公開前：その版を手元で動かして測る（開発サーバ）
  python3 zure_kanmon.py prod                                公開後：本番を測る
終了コード: 0=ズレ0 / 1=ズレあり（公開しない）/ 2=測れなかった（関所の故障。止めずに記録だけ残す）
結果: status/zure_kanmon/<名前>.json に必ず残す（verdict: ok / ng / inconclusive）。
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "zure_kanmon")
SITE = "/Users/mac/Desktop/joy-relief-station"
WT_ROOT = "/Users/mac/.tamago/wt"
PROD = "https://joy-relief-station.lovable.app"
# 手元の開発サーバで安定して描けるページ（検索・DB由来のバッジは手元では出ないので本番側で測る）
LOCAL_PAGES = ",".join([
    "/", "/world/music", "/world/food", "/world/cute", "/shelf/music/summer",
    "/cover-guide", "/cover-guide?artist=prince", "/cover-guide?artist=hybs&song=go-higher",
    "/room/card/prince-morning-papers", "/food-radar", "/watch",
])
ENV_PATH = "/opt/homebrew/bin:/usr/local/bin:" + os.path.expanduser("~/.bun/bin") + ":" + os.environ.get("PATH", "")


def _now():
    return time.strftime("%F %T")


def _write(name, doc):
    os.makedirs(OUT, exist_ok=True)
    doc["at"] = _now()
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _git(*a, cwd=SITE, check=True):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=check)


def _measure(base, workdir, pages, extra_env=None, timeout=1500):
    """測る本体を走らせて (rc, 出力) を返す。測る本体は常に origin/main の最新版を使う（古い版でも新しい物差しで測る）。"""
    script = os.path.join(workdir, ".zure_measure.mjs")
    cfg = os.path.join(workdir, "scripts")
    os.makedirs(cfg, exist_ok=True)
    try:
        _git("fetch", "-q", "origin", check=False)
        src = _git("show", "origin/main:scripts/measure-card-geometry.mjs").stdout
        allow = _git("show", "origin/main:scripts/geometry-gate-allow.json", check=False).stdout or "[]"
    except Exception:
        src, allow = "", "[]"
    if not src:
        sp = os.path.join(workdir, "scripts", "measure-card-geometry.mjs")
        if not os.path.exists(sp):
            return 2, "測る本体が見つかりません"
        src = open(sp, encoding="utf-8").read()
    # 測る本体と許可台帳は workdir/scripts に置いて走らせる（台帳は本体の隣を読む）
    sd = os.path.join(workdir, ".zure_scripts")
    os.makedirs(sd, exist_ok=True)
    script = os.path.join(sd, "measure-card-geometry.mjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write(src)
    with open(os.path.join(sd, "geometry-gate-allow.json"), "w", encoding="utf-8") as f:
        f.write(allow)
    env = dict(os.environ, PATH=ENV_PATH, PAGES=pages)
    env.update(extra_env or {})
    p = subprocess.run(["node", script, base], cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _summarize(rc, out):
    m = re.search(r"RESULT ズレ=(\d+) 件.*", out)
    viol = [l for l in out.splitlines() if l.startswith("✗")]
    return {
        "verdict": "ok" if rc == 0 else ("ng" if rc == 1 else "inconclusive"),
        "violations": int(m.group(1)) if m else None,
        "result": m.group(0) if m else out.strip().splitlines()[-1:] or "",
        "detail": viol[:40],
    }


def pre(target):
    """公開前：手元で開発サーバを立てて測る。target はフォルダ（そのまま使う）かコミットSHA（一時の作業フォルダを作って使う）。"""
    made = None
    if os.path.isdir(target):
        wd = os.path.abspath(target)
        label = "pre_" + (_git("rev-parse", "--short=8", "HEAD", cwd=wd, check=False).stdout.strip() or "dir")
    else:
        sha = target
        label = "pre_" + sha[:8]
        wd = os.path.join(WT_ROOT, "zure-" + sha[:8])
        os.makedirs(WT_ROOT, exist_ok=True)
        _git("fetch", "-q", "origin", check=False)
        if os.path.isdir(wd):
            _git("worktree", "remove", "--force", wd, check=False)
            shutil.rmtree(wd, ignore_errors=True)
        r = _git("worktree", "add", "--detach", wd, sha, check=False)
        if r.returncode != 0:
            _write(label, {"verdict": "inconclusive", "reason": "作業フォルダが作れません: " + (r.stderr or "")[:200]})
            return 2
        made = wd
    nm = os.path.join(wd, "node_modules")
    if not os.path.exists(nm):
        os.symlink(os.path.join(SITE, "node_modules"), nm)
    port = _free_port()
    logf = open(os.path.join(wd, ".zure_vite.log"), "w")
    srv = subprocess.Popen(["npx", "vite", "dev", "--port", str(port), "--host", "127.0.0.1", "--strictPort"],
                           cwd=wd, env=dict(os.environ, PATH=ENV_PATH), stdout=logf, stderr=subprocess.STDOUT,
                           start_new_session=True)
    rc = 2
    out = ""
    try:
        ok = False
        t0 = time.time()
        while time.time() - t0 < 150:
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=60) as r:
                    if r.status == 200:
                        ok = True
                        break
            except Exception:
                time.sleep(2)
        if not ok:
            _write(label, {"verdict": "inconclusive", "reason": "開発サーバが立ち上がりません"})
            return 2
        rc, out = _measure("http://127.0.0.1:%d" % port, wd, LOCAL_PAGES,
                           {"SETTLE_MS": "4000", "SCROLL_MS": "250"})
    except subprocess.TimeoutExpired:
        rc, out = 2, "測定がタイムアウト"
    finally:
        try:
            os.killpg(os.getpgid(srv.pid), signal.SIGTERM)
        except Exception:
            pass
        logf.close()
        if made:
            _git("worktree", "remove", "--force", made, check=False)
            shutil.rmtree(made, ignore_errors=True)
    doc = _summarize(rc, out)
    doc["target"] = target
    _write(label, doc)
    try:
        os.remove(os.path.join(OUT, label + ".running"))
    except OSError:
        pass
    print(doc.get("result"), "→", doc["verdict"])
    for l in doc["detail"][:10]:
        print(l)
    return rc if rc in (0, 1) else 2


def prod():
    """公開後：本番を測る。"""
    wd = os.path.join(WT_ROOT, "zure-prod")
    os.makedirs(wd, exist_ok=True)
    try:
        rc, out = _measure(PROD, wd, os.environ.get("PAGES", ""), {})
    except subprocess.TimeoutExpired:
        rc, out = 2, "測定がタイムアウト"
    doc = _summarize(rc, out)
    doc["target"] = PROD
    _write("prod", doc)
    print(doc.get("result"), "→", doc["verdict"])
    for l in doc["detail"][:10]:
        print(l)
    return rc if rc in (0, 1) else 2


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pre" and len(sys.argv) > 2:
        sys.exit(pre(sys.argv[2]))
    if cmd == "prod":
        sys.exit(prod())
    print(__doc__)
    sys.exit(2)
