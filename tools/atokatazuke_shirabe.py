#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""後片付けの棲卸し（98404号・2026-10-19・たまごさん「使ったらしまう・使ったら閉じる」）。

1日に1回（tools/shimau.py の日次測定に相乗り。shimau.py から呼ばれる）、
「誰が作って、何が残っているか」を一覧にする：
  ① /private/tmp（worktree・claude-* を除く。拡張子・名前のパターンで種類分け）
  ② 作業場 .worktrees（~/Documents/AI作業/.worktrees。status/queue.json の n/title と
     対応づける＝名前が q<n>-日付 の形なので、どの依頼が残したかが分かる）
  ③ status/ の中間ファイル（auto-launch-*.log・_tmp_*・スクリーンショット等）
  ④ Chromiumの一時プロフィール（~/.tamago/chrome-*。自動操作専用のログイン済みプロフィール）

既存の tools/worktree_taihi.py・tools/youryou_tantei.py は「消す・容量の推移」担当。
ここは「今どれだけ残っていて、前回から増えたか」の一覧だけに専念する（消さない・読むだけ）。

結果：status/public/atokatazuke.json（前回との増減つき。履歴は status/atokatazuke_hist.json）
逆テスト：python3 tools/atokatazuke_shirabe.py --self-test
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
WTB = os.path.join(HOME, "Documents", "AI作業", ".worktrees")
TMP = "/private/tmp"
OUT = os.path.join(REPO, "status", "public", "atokatazuke.json")
HIST = os.path.join(REPO, "status", "atokatazuke_hist.json")
QUEUE = os.path.join(REPO, "status", "queue.json")

WT_RE = re.compile(r"^q(\d+)-")
MEDIA_EXT = (".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".zip", ".tar", ".gz")


def du_bytes(p, limit=20000):
    try:
        if os.path.islink(p):
            return os.lstat(p).st_size
        if os.path.isfile(p):
            return os.path.getsize(p)
        total, n = 0, 0
        for dp, dns, fns in os.walk(p):
            for fn in fns:
                try:
                    total += os.lstat(os.path.join(dp, fn)).st_size
                except Exception:
                    pass
                n += 1
                if n > limit:
                    return total
        return total
    except Exception:
        return 0


def age_days(p):
    try:
        return round((time.time() - os.lstat(p).st_mtime) / 86400, 1)
    except Exception:
        return None


def queue_titles():
    """status/queue.json の n → 依頼タイトル。読めない・壊れていても空辞書で続ける。"""
    try:
        q = json.load(open(QUEUE, encoding="utf-8"))
        out = {}
        for it in q.get("items", []):
            n = it.get("n")
            if n is not None:
                out[str(n)] = it.get("hyoudai") or it.get("title")
        return out
    except Exception:
        return {}


def _cat(name, p):
    low = name.lower()
    if name.startswith("."):
        return "ドット隠しファイル"
    if re.match(r"^q\d+-", name) or os.path.isdir(os.path.join(p, ".git")):
        return "worktree/git作業場の複製"
    if low.endswith(".log"):
        return "ログ"
    if low.endswith(MEDIA_EXT):
        return "メディア・圧縮"
    if "playwright" in low or "chromium" in low or low.startswith("pw-"):
        return "自動操作ブラウザの使い捨てプロフィール"
    return "その他(スクリプト・テキスト等)"


def tally_tmp():
    rows = []
    if not os.path.isdir(TMP):
        return {"count": 0, "count_1day_over": 0, "total_gb": 0.0, "by_category_gb": {}, "top10_biggest": []}
    for name in sorted(os.listdir(TMP)):
        if name.startswith("claude-"):
            continue
        p = os.path.join(TMP, name)
        a = age_days(p)
        b = du_bytes(p) / 1e9
        rows.append({"name": name, "gb": round(b, 3), "age_days": a, "cat": _cat(name, p)})
    cat_gb = {}
    for r in rows:
        cat_gb[r["cat"]] = round(cat_gb.get(r["cat"], 0) + r["gb"], 3)
    n_old = sum(1 for r in rows if (r["age_days"] or 0) >= 1)
    rows.sort(key=lambda r: -(r["gb"] or 0))
    return {
        "count": len(rows),
        "count_1day_over": n_old,
        "total_gb": round(sum(r["gb"] for r in rows), 2),
        "by_category_gb": dict(sorted(cat_gb.items(), key=lambda x: -x[1])),
        "top10_biggest": rows[:10],
    }


def tally_worktrees():
    titles = queue_titles()
    rows = []
    if os.path.isdir(WTB):
        for name in sorted(os.listdir(WTB)):
            p = os.path.join(WTB, name)
            if not os.path.isdir(p):
                continue
            m = WT_RE.match(name)
            n = m.group(1) if m else None
            dirty = None
            try:
                r = subprocess.run(["git", "status", "--porcelain"], cwd=p,
                                    capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    dirty = bool(r.stdout.strip())
            except Exception:
                pass
            rows.append({
                "name": name, "n": n, "title": titles.get(n) if n else None,
                "gb": round(du_bytes(p) / 1e9, 3), "age_days": age_days(p), "dirty": dirty,
            })
    return {"count": len(rows), "total_gb": round(sum(r["gb"] for r in rows), 2), "items": rows}


def tally_status_mid():
    logs = glob.glob(os.path.join(REPO, "status", "auto-launch-*.log"))
    return {
        "auto_launch_log_count": len(logs),
        "auto_launch_log_gb": round(sum(os.path.getsize(p) for p in logs if os.path.exists(p)) / 1e9, 3),
        "_tmp_count": len(glob.glob(os.path.join(REPO, "status", "_tmp_*"))),
        "screenshot_png_count": len(glob.glob(os.path.join(REPO, "status", "*.png"))),
    }


def tally_chrome_profiles():
    rows = [{"name": os.path.basename(p), "gb": round(du_bytes(p) / 1e9, 2)}
            for p in sorted(glob.glob(os.path.join(HOME, ".tamago", "chrome-*")))]
    return {"items": rows, "total_gb": round(sum(r["gb"] for r in rows), 2)}


def run():
    res = {
        "at": time.strftime("%F %T"),
        "tmp": tally_tmp(),
        "worktrees": tally_worktrees(),
        "status_mid": tally_status_mid(),
        "chrome_profiles": tally_chrome_profiles(),
        "note": "「誰が作ったか」はworktree(n番)だけ名前から特定できる。/private/tmp の単発ファイルは"
                "命名規則がバラバラで個別の担当までは特定できないため種類分け(cat)だけを出す（正直に書く）。",
    }
    cur = {
        "tmp_gb": res["tmp"]["total_gb"], "tmp_count": res["tmp"]["count"],
        "worktrees_gb": res["worktrees"]["total_gb"], "worktrees_count": res["worktrees"]["count"],
        "chrome_profiles_gb": res["chrome_profiles"]["total_gb"],
    }
    try:
        prev = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        prev = {}
    res["since"] = prev.get("at")
    res["fueta"] = {k: round(cur[k] - prev.get(k, cur[k]), 2) for k in cur}
    cur["at"] = res["at"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False)
    return res


def self_test():
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="atokatazuke_selftest_")
    try:
        with open(os.path.join(d, "x.txt"), "w", encoding="utf-8") as f:
            f.write("a" * 1000)
        assert du_bytes(d) >= 1000, "du_bytes が測れていない"
        a = age_days(d)
        assert a is not None and a < 1, "age_days がおかしい"
        assert _cat("q123-foo", d) == "worktree/git作業場の複製"
        assert _cat("vite_dev_35090.log", d) == "ログ"
        assert _cat("output.mp4", d) == "メディア・圧縮"
        assert _cat("playwright_chromiumdev_profile-abc", d) == "自動操作ブラウザの使い捨てプロフィール"
        r = tally_tmp()
        assert "count" in r and "by_category_gb" in r
        rw = tally_worktrees()
        assert "items" in rw
        print("self-test OK")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
        sys.exit(0)
    out = run()
    print("書いた: status/public/atokatazuke.json（/private/tmp %d個 %.2fGB／作業場 %d個 %.2fGB）" % (
        out["tmp"]["count"], out["tmp"]["total_gb"], out["worktrees"]["count"], out["worktrees"]["total_gb"]))
