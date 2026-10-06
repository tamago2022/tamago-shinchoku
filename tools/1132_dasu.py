#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1132番【出す口】完成の関所を、ごきげん補給所(joy-relief-station)の main に1コミットで入れる。

■ なぜこの形か（2026-09-25 実測）

  ・サンドボックス（Cowork）からは GitHub に**回線が出ない**（ssh も https も届かない）。
    → だからコードを書くのはサンドボックス、**出すのは工場（Mac）**。この1本がその窓口。
  ・Mac の /Users/mac/Desktop/joy-relief-station は
    **9/14で止まった横道のブランチ**（claude/taste-entry-cover-guide）に居て、
    未コミットが359ファイルある。ここで git を叩くと、たまごさんの手元を壊す。
    → **作業ツリーに一切触らない。** GitHub の API だけで、main の上に直接1コミット作る。
  ・全文を上書きすると、15分便が同じ時間に入れた変更を巻き戻す事故が起きる。
    → 送るのは**差分（1132.patch）だけ**。
      実行のたびに「そのときの main の中身」を取ってきて、その上に当てる。
      既に当たっていれば何もしない（何度走らせても同じ結果）。

■ 使い方

    python3 tools/1132_dasu.py            # 本番の main に入れる
    python3 tools/1132_dasu.py --dry-run  # 当ててみるだけ。GitHubには書かない

  代行係（tools/gaibu_runner.py）からは kind="kansei" で呼ばれる。

■ 使う鍵

  tools/github_watch.py の gh_token()（既にある読み書き用のGitHubトークン）だけ。
  新しい鍵を作らない。課金は0円。
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OKIBA = os.path.join(REPO, "status", "1132_kansei")
PATCH = os.path.join(OKIBA, "1132.patch")
NEWDIR = os.path.join(OKIBA, "new")

GH_REPO = "tamago2022/joy-relief-station"
BRANCH = "main"
MESSAGE = (
    "1132番【完成の関所】完成したものだけを表に出す\n\n"
    "動画が無い/消えている曲を、検索・棚・おすすめ・「この流れで、もう一本」・\n"
    "サイトマップの全部から出さない。判定は src/lib/kansei.ts の1か所だけ。\n"
    "データは1件も消していない（隠しているだけ）。戻し方は KANSEI_GATE = false。"
)
API = "https://api.github.com"


def _token():
    import github_watch
    return github_watch.gh_token()


def _req(method, url, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer %s" % token)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "tamago-1132")
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _patched_paths():
    """1132.patch が触るファイルの一覧（+++ b/... の行から拾う）。"""
    out = []
    for line in io.open(PATCH, encoding="utf-8"):
        if line.startswith("+++ b/"):
            # diff -u は「パス<TAB>更新時刻」を書く。時刻を落としてパスだけにする。
            out.append(line[6:].split("\t")[0].rstrip("\n").strip())
    return out


def _new_files():
    out = {}
    for root, _dirs, files in os.walk(NEWDIR):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, NEWDIR)
            out[rel] = io.open(full, encoding="utf-8").read()
    return out


def run_job(payload=None):
    payload = payload or {}
    dry = bool(payload.get("dryRun"))
    log = []

    # ★1140番【全曲検査】payload に kensa:true が来たら、押す前に
    #   ①実測（oEmbedで全動画IDを1件ずつ叩く。回線があるのは工場側だけ）
    #   ②全曲検査（隠す表 kanseiHidden.generated.ts を作り直す）
    #   を先にやる。これで「毎日流し直す常駐」がこの1本で足りる。
    if payload.get("kensa"):
        for name, args in (("1140_jissoku.py", ["--limit", str(payload.get("limit", 40000))]),
                           ("1140_kensa.py", [])):
            r = subprocess.run([sys.executable, os.path.join(HERE, name)] + args,
                               capture_output=True, text=True, timeout=3600)
            log.append("%s → rc=%d %s" % (name, r.returncode, (r.stdout or "")[-700:]))
            if r.returncode != 0:
                log.append((r.stderr or "")[-500:])

    if not os.path.exists(PATCH):
        return {"ok": False, "log": ["差分が置いてありません: %s" % PATCH], "totalYen": 0.0}

    token = _token()
    if not token:
        return {"ok": False, "log": ["GitHubの鍵が取れませんでした"], "totalYen": 0.0}

    head = _req("GET", "%s/repos/%s/git/ref/heads/%s" % (API, GH_REPO, BRANCH), token)
    base_sha = head["object"]["sha"]
    log.append("いまの main = %s" % base_sha[:8])

    work = tempfile.mkdtemp(prefix="1132_")
    try:
        # ① いまの main から、差分が触るファイルだけを取ってくる
        # ★Contents API は 1MB を超えるファイルを返せない（coverGuide.ts は約6.5MB）。
        #   なので木（tree）からSHAを引いて、blob を直接読む（100MBまで平気）。
        paths = _patched_paths()
        tree_all = _req("GET", "%s/repos/%s/git/trees/%s?recursive=1" % (API, GH_REPO, base_sha),
                        token)
        sha_of = {e["path"]: e["sha"] for e in tree_all.get("tree", []) if e.get("type") == "blob"}
        missing = [p for p in paths if p not in sha_of]
        if missing:
            log.append("mainに無いファイル: %s" % ", ".join(missing))
            return {"ok": False, "log": log, "totalYen": 0.0}
        for p in paths:
            got = _req("GET", "%s/repos/%s/git/blobs/%s" % (API, GH_REPO, sha_of[p]), token)
            raw = base64.b64decode(got["content"])
            dst = os.path.join(work, p)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            io.open(dst, "wb").write(raw)
        log.append("main から %d本 取ってきました" % len(paths))

        # ② 当ててみる（もう当たっているなら何もしない＝何度走らせても同じ）
        chk = subprocess.run(["patch", "-p1", "--dry-run", "-i", PATCH],
                             cwd=work, capture_output=True, text=True)
        already = False
        if chk.returncode != 0:
            rev = subprocess.run(["patch", "-p1", "-R", "--dry-run", "-i", PATCH],
                                 cwd=work, capture_output=True, text=True)
            if rev.returncode == 0:
                # ★関所そのものは既に入っている。でも隠す表（kanseiHidden.generated.ts）は
                #   毎日作り直すので、中身が変わっていれば**そこだけ**押す。
                #   （1140番より前は、ここで「何もしません」と帰っていた＝表が更新されなかった）
                already = True
                log.append("関所の差分はもう入っています。隠す表の変化だけ見ます。")
            else:
                log.append("差分が当たりません（mainが動いた可能性）:\n" + chk.stdout[-1200:])
                return {"ok": False, "log": log, "totalYen": 0.0}
        else:
            subprocess.run(["patch", "-p1", "-i", PATCH], cwd=work,
                           capture_output=True, text=True, check=True)
            log.append("差分を当てました")

        # ③ 新しいファイル（関所そのもの）
        files = {}
        for p in paths:
            files[p] = io.open(os.path.join(work, p), encoding="utf-8").read()
        for p, body in _new_files().items():
            files[p] = body
        # mainと同じ中身のものは送らない（空コミットを作らない・押し戻さない）
        for p in list(files):
            if p in sha_of:
                try:
                    cur = base64.b64decode(_req("GET", "%s/repos/%s/git/blobs/%s"
                                                % (API, GH_REPO, sha_of[p]), token)["content"])
                    if cur.decode("utf-8", "ignore") == files[p]:
                        del files[p]
                except Exception:
                    pass
        if not files:
            log.append("★mainと同じでした。何もしません。")
            return {"ok": True, "log": log, "alreadyIn": True, "totalYen": 0.0}
        log.append("送るファイル: %d本（%s）" % (len(files), ", ".join(sorted(files))))

        if dry:
            log.append("--dry-run なのでGitHubには書きません")
            return {"ok": True, "log": log, "dryRun": True, "totalYen": 0.0}

        # ④ blob → tree → commit → ref（1コミットで原子的に入る）
        tree = []
        for p, body in sorted(files.items()):
            blob = _req("POST", "%s/repos/%s/git/blobs" % (API, GH_REPO), token,
                        {"content": body, "encoding": "utf-8"})
            tree.append({"path": p, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        base_commit = _req("GET", "%s/repos/%s/git/commits/%s" % (API, GH_REPO, base_sha), token)
        new_tree = _req("POST", "%s/repos/%s/git/trees" % (API, GH_REPO), token,
                        {"base_tree": base_commit["tree"]["sha"], "tree": tree})
        msg = MESSAGE
        if payload.get("kensa"):
            msg = ("1140番【全曲検査】全曲を機械で1曲ずつ見て、"
                   "再生できる動画が1本も無いものを表から外す\n\n"
                   "検査 = tools/1140_kensa.py（全件・サンプリングなし）\n"
                   "実測 = tools/1140_jissoku.py（oEmbedで動画IDを1件ずつ）\n"
                   "データは1件も消していない（隠しているだけ）。"
                   "直れば次の生成で自動的に戻る。\n"
                   "戻し方: src/lib/kansei.ts の KANSEI_GATE = false。")
        commit = _req("POST", "%s/repos/%s/git/commits" % (API, GH_REPO), token,
                      {"message": msg, "tree": new_tree["sha"], "parents": [base_sha]})
        _req("PATCH", "%s/repos/%s/git/refs/heads/%s" % (API, GH_REPO, BRANCH), token,
             {"sha": commit["sha"], "force": False})
        log.append("★mainに入りました: %s" % commit["sha"][:8])
        return {"ok": True, "log": log, "commit": commit["sha"], "totalYen": 0.0}
    except urllib.error.HTTPError as e:
        log.append("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "ignore")[:600]))
        return {"ok": False, "log": log, "totalYen": 0.0}
    except Exception as e:  # noqa: BLE001
        log.append("落ちました: %r" % (e,))
        return {"ok": False, "log": log, "totalYen": 0.0}
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    out = run_job({"dryRun": "--dry-run" in sys.argv})
    print(json.dumps(out, ensure_ascii=False, indent=1))
