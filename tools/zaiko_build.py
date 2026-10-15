#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在庫一覧（zaiko）：ごきげん補給所（joy-relief-station）に「今ある曲」を、誰でも読める1か所に出す。

たまごさん（2026-10-15）：
  「Genspark がマガジン原稿を書くとき、今ある曲を自分で確かめられるようにする。
    俺が口頭で曲を指定しても、在庫にあるか分からない問題をなくす。」

■ 出すもの（status/public/ → tools/pages_publish.sh が5分便で GitHub Pages へ）
  status/public/zaiko.json        … 入口。件数・使い方・アーティスト名簿（どの棚ファイルに居るか）・特集一覧
  status/public/zaiko/<key>.json  … 曲の本体。アーティストごとに 曲名／曲ページURL／YouTube ID／棚／特集
  status/public/zaiko.html        … 人間用の見やすいページ（検索窓。開いた時点では名簿しか読まない）
  ★どのファイルも 1MB 未満（pages_publish.sh の関所が 1MB 超を弾くため）。

■ 出どころ（正規表現でTSを読まない）
  /Users/mac/Desktop/joy-relief-station の origin/main を一時フォルダへ git archive で展開し、
  tools/zaiko/entry.ts を esbuild で束ねて node で1回走らせる。
  ＝倉庫下ろし・再生できない曲の隠し・アーティスト統合が「本番と同じように」済んだ姿を読む。
  作業ツリー（いま誰かが触っている枝）には一切触らない。git worktree も使わない。
  在庫に数えないもの：1140番の関所（kanseiHidden）で隠されている曲＝サイトに出ていない曲。
  棚は worlds.ts に書かれた棚だけ（管理画面からDBに足した棚は含まない）。

■ いつ作り直すか
  tools/machine_status_push.sh（5分便）から毎回呼ばれる。中で10分に1回だけ git fetch し、
  origin/main の版が前回と同じなら何もしない（数ミリ秒で戻る）。版が変わった時だけ作り直す。
  手で回す：python3 tools/zaiko_build.py --force

■ 使ったらしまう：一時フォルダは必ず消す（trap 相当を finally で）。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JRS = os.environ.get("ZAIKO_JRS", "/Users/mac/Desktop/joy-relief-station")
PUB = os.path.join(REPO, "status", "public")
SHARD_DIR = os.path.join(PUB, "zaiko")
STATE = os.path.join(REPO, "status", "zaiko_state.json")
LOCK = os.path.join(REPO, "status", ".zaiko_build.lock")
LOG = os.path.join(REPO, "status", "zaiko_build.log")
ENTRY = os.path.join(REPO, "tools", "zaiko", "entry.ts")
SITE = "https://joy-relief-station.lovable.app"
PAGES = "https://tamago2022.github.io/tamago-shinchoku/status/public"
FETCH_EVERY = 600
MAX_SHARD = 700 * 1024
ENV = dict(os.environ, PATH="/Users/mac/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", ""))


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def sh(args, timeout=120, **kw):
    return subprocess.run(args, capture_output=True, timeout=timeout, env=ENV, **kw)


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def entry_hash():
    with open(ENTRY, "rb") as f:
        a = f.read()
    with open(os.path.abspath(__file__), "rb") as f:
        b = f.read()
    return hashlib.sha1(a + b).hexdigest()[:12]


def dump(sha):
    """origin/main を一時フォルダへ出して、entry.ts を走らせた結果(dict)を返す。"""
    tmp = tempfile.mkdtemp(prefix="zaiko.")
    try:
        arc = sh(["git", "-C", JRS, "archive", sha, "src", "tsconfig.json", "package.json"], timeout=120)
        if arc.returncode != 0:
            raise RuntimeError("git archive 失敗: " + arc.stderr.decode("utf-8", "replace")[-300:])
        tar = subprocess.run(["tar", "-x", "-C", tmp], input=arc.stdout, capture_output=True, timeout=120)
        if tar.returncode != 0:
            raise RuntimeError("tar 失敗")
        os.symlink(os.path.join(JRS, "node_modules"), os.path.join(tmp, "node_modules"))
        shutil.copy(ENTRY, os.path.join(tmp, "entry.ts"))
        loaders = ["--loader:.%s=empty" % x for x in ("jpg", "jpeg", "png", "webp", "svg", "gif", "avif", "css")]
        b = sh([os.path.join(tmp, "node_modules", ".bin", "esbuild"), "entry.ts", "--bundle", "--platform=node",
                "--format=esm", "--packages=external", "--outfile=out.mjs", "--log-level=error"] + loaders,
               timeout=180, cwd=tmp)
        if b.returncode != 0:
            raise RuntimeError("esbuild 失敗: " + b.stderr.decode("utf-8", "replace")[-500:])
        r = sh(["node", "out.mjs"], timeout=180, cwd=tmp)
        if r.returncode != 0:
            raise RuntimeError("node 失敗: " + r.stderr.decode("utf-8", "replace")[-500:])
        return json.loads(r.stdout.decode("utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def song_url(aid, sid):
    from urllib.parse import quote
    return "%s/cover-guide?artist=%s&song=%s" % (SITE, quote(aid, safe="-_.~"), quote(sid, safe="-_.~"))


def first_key(aid):
    c = (aid or "_")[0].lower()
    if "a" <= c <= "z":
        return c
    if "0" <= c <= "9":
        return "0"
    return "etc"


def jdump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def write_if_changed(path, text):
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except Exception:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return True


def build(data, sha, sha_time):
    artists = []
    hidden = 0
    for a in data["artists"]:
        rows = []
        for s in a["songs"]:
            if s.get("hidden"):
                hidden += 1
                continue
            shelves = ["%s／%s（%s/shelf/%s/%s）" % (x["wl"], x["st"], SITE, x["w"], x["s"]) for x in s["shelves"]]
            feats = ["%s（%s%s）" % (f["title"], SITE, f["path"]) for f in s["features"]]
            row = [s["title"], song_url(a["id"], s["id"]), s.get("yt") or ""]
            if shelves or feats:
                row.append(shelves)
            if feats:
                row.append(feats)
            rows.append(row)
        if rows:
            artists.append({"id": a["id"], "name": a["name"], "aliases": a.get("aliases") or [], "songs": rows})

    # ---- 棚ファイルへ振り分け（1MB未満に収まるよう、大きい組は id の頭2文字・3文字で割る） ----
    def split(group, depth):
        size = len(jdump(group).encode("utf-8"))
        if size <= MAX_SHARD or depth >= 4:
            return [group]
        sub = {}
        for a in group:
            k = a["id"][:depth + 1].lower()
            sub.setdefault(k, []).append(a)
        if len(sub) == 1:
            return [group]
        out = []
        for k in sorted(sub):
            out.extend(split(sub[k], depth + 1))
        return out

    groups = {}
    for a in artists:
        groups.setdefault(first_key(a["id"]), []).append(a)
    shards = []
    for k in sorted(groups):
        parts = split(groups[k], 1) if k not in ("0", "etc") else [groups[k]]
        for i, p in enumerate(parts):
            name = k if len(parts) == 1 else "%s%d" % (k, i + 1)
            shards.append((name, p))

    os.makedirs(SHARD_DIR, exist_ok=True)
    cols = ["曲名", "曲ページURL", "YouTube ID", "所属する棚（部屋／棚名）", "出てくる特集"]
    directory = []
    shard_list = []
    keep = set()
    total = 0
    for name, group in shards:
        fn = "%s.json" % name
        keep.add(fn)
        n = sum(len(a["songs"]) for a in group)
        total += n
        body = {"_": "ごきげん補給所 在庫（曲）。各曲は [曲名, 曲ページURL, YouTube ID, 棚(あれば), 特集(あれば)]。",
                "cols": cols, "version": sha[:9], "artists": group}
        write_if_changed(os.path.join(SHARD_DIR, fn), jdump(body))
        shard_list.append({"file": "%s/zaiko/%s" % (PAGES, fn), "artists": len(group), "songs": n})
        for a in group:
            directory.append([a["name"], a["aliases"][:4], len(a["songs"]), name])
    for old in os.listdir(SHARD_DIR):
        if old.endswith(".json") and old not in keep:
            os.remove(os.path.join(SHARD_DIR, old))

    feats = {}
    for a in artists:
        for r in a["songs"]:
            if len(r) >= 5:
                for f in r[4]:
                    feats.setdefault(f, []).append("%s「%s」" % (a["name"], r[0]))
    shelf_count = {}
    for a in artists:
        for r in a["songs"]:
            if len(r) >= 4:
                for sname in r[3]:
                    shelf_count[sname] = shelf_count.get(sname, 0) + 1

    index = {
        "title": "ごきげん補給所（joy-relief-station）曲の在庫一覧",
        "how_to_use": [
            "原稿で使う曲は、まずこの一覧で在庫確認する。",
            "1) 下の artists（名簿）でアーティスト名を探す。各行は [名前, 別名, 曲数, 棚ファイル名]。",
            "2) 棚ファイル %s/zaiko/<棚ファイル名>.json を開き、そのアーティストの songs で曲名を探す。" % PAGES,
            "3) 載っていれば在庫あり：曲ページURL をそのまま原稿に使う。",
            "4) 載っていなければ在庫なし：原稿内に『新規入荷候補』と明記する（勝手に在庫扱いしない）。",
            "入荷は Claude 側で関所（sekisho-artist-song）を通してから。",
            "人間向けの検索ページ：%s/zaiko.html" % PAGES,
        ],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": {"repo": "tamago2022/joy-relief-station", "branch": "main", "commit": sha[:9], "commit_time": sha_time},
        "counts": {"songs": total, "artists": len(artists), "hidden_not_counted": hidden},
        "not_included": "サイトに出ていない曲（再生できる動画が無く隠されている曲）は数えていない。棚は worlds.ts に書かれた棚だけ（管理画面からDBで足した棚は含まない）。",
        "features": [{"title": m["title"], "url": SITE + m["path"], "kicker": m["kicker"],
                      "songs": feats.get("%s（%s%s）" % (m["title"], SITE, m["path"]), [])} for m in data.get("magazines", [])],
        "shelves": [{"name": k, "songs": v} for k, v in sorted(shelf_count.items(), key=lambda x: -x[1])],
        "shards": shard_list,
        "artists_cols": ["名前", "別名", "曲数", "棚ファイル名"],
        "artists": directory,
    }
    write_if_changed(os.path.join(PUB, "zaiko.json"), jdump(index))
    with open(os.path.join(REPO, "tools", "zaiko", "zaiko.html"), encoding="utf-8") as f:
        html = f.read()
    write_if_changed(os.path.join(PUB, "zaiko.html"), html)
    for p in [os.path.join(PUB, "zaiko.json"), os.path.join(PUB, "zaiko.html")] + \
             [os.path.join(SHARD_DIR, x) for x in keep]:
        if os.path.getsize(p) >= 1024 * 1024:
            raise RuntimeError("1MB超: %s" % p)
    return total, len(artists), hidden, len(shards)


def main():
    force = "--force" in sys.argv
    # 二重に走らせない（10分より古い錠は死んだものとして奪う）
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        if time.time() - os.path.getmtime(LOCK) < 600:
            return 0
        os.remove(LOCK)
        return main()
    try:
        if not os.path.isdir(os.path.join(JRS, ".git")):
            log("joy-relief-station が見つからない: %s" % JRS)
            return 1
        st = load_state()
        now = time.time()
        if force or now - st.get("fetched_at", 0) > FETCH_EVERY:
            sh(["git", "-C", JRS, "fetch", "-q", "origin", "main"], timeout=90)
            st["fetched_at"] = now
            save_state(st)
        r = sh(["git", "-C", JRS, "log", "-1", "--format=%H %cI", "origin/main"], timeout=30)
        if r.returncode != 0:
            log("origin/main が読めない")
            return 1
        sha, sha_time = r.stdout.decode().strip().split(" ", 1)
        eh = entry_hash()
        out_ok = os.path.exists(os.path.join(PUB, "zaiko.json"))
        if not force and out_ok and st.get("sha") == sha and st.get("entry") == eh:
            return 0
        t0 = time.time()
        data = dump(sha)
        total, na, hidden, nshard = build(data, sha, sha_time)
        st.update({"sha": sha, "entry": eh, "built_at": time.strftime("%F %T"), "songs": total,
                   "artists": na, "hidden": hidden, "shards": nshard})
        save_state(st)
        log("作り直した %s 曲=%d アーティスト=%d 隠れ=%d 棚ファイル=%d %.1f秒" % (sha[:9], total, na, hidden, nshard, time.time() - t0))
        print("zaiko: songs=%d artists=%d shards=%d commit=%s" % (total, na, nshard, sha[:9]))
        return 0
    except Exception as e:
        log("失敗: %s" % e)
        print("zaiko 失敗: %s" % e, file=sys.stderr)
        return 1
    finally:
        try:
            os.remove(LOCK)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
