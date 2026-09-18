#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配達係 — 作ったものを「スマホでもパソコンでも開けるURL」にして渡す道具。

たまごさんの一言（2026-09-19）：
  「確認できないものをよこすな。押せないものをよこすな。
    これを押して本当に見れるのか、誰が確認してんだ。俺じゃん、結局テスターは。
    だからそれをやめてくれって。ゼロにしてよ。」

だからこの道具は、URLを組み立てて終わりにしない。
**実際に外から叩いて 200 が返り、中身が入っていることを確かめるまで、URLを出さない。**
確かめられなければ「渡せません」と言って終わる。それが正しい負け方。

なぜ回りくどいのか：
  Cowork/Dispatch のサンドボックスは社外向けプロキシの許可リストで
  tamago2022.github.io への接続が塞がれている（実測 HTTP 403 blocked-by-allowlist）。
  つまりセッション側からは、公開URLを永遠に自分で確かめられない。
  そこで「外から叩く」仕事だけを GitHub の runner に出し（.github/workflows/deliver-verify.yml）、
  その結果を status/public/deliver_verified.json として持ち帰らせ、こちらは github.com 経由で
  それを読む。github.com は許可リストに入っている（実測 200）。

使い方：
    python3 tools/deliver.py share/badge-size-sheet.html
    python3 tools/deliver.py share/a.html share/b.html --wait
    python3 tools/deliver.py --status          # 今の確認結果だけ見る

--wait を付けると、確認が取れるまで（最大25分）待ってからURLを出す。
"""
import argparse
import html
import json
import pathlib
import re
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "share" / "_deliver" / "manifest.json"
RESULT_REL = "status/public/deliver_verified.json"
BASE_URL = "https://tamago2022.github.io/tamago-shinchoku/"
RUNS_HTML = ("https://github.com/tamago2022/tamago-shinchoku/"
             "actions/workflows/deliver-verify.yml")

# share/ は全世界に公開される。重いものを置くと、たまごさんのスマホの通信量を食う。
MAX_BYTES = 1024 * 1024


def sh(*args, **kw):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, **kw)


def marker_of(path: pathlib.Path) -> str:
    """そのページにしか無い短い文字列。404ページや空HTMLを掴んでいないかの踏み絵。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<title>(.*?)</title>", text, re.S)
    if m:
        t = html.unescape(m.group(1)).strip()
        if len(t) >= 4:
            return t[:60]
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
    if m:
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if len(t) >= 4:
            return t[:60]
    return ""


def register(paths):
    """配達台帳に載せて、commitまでやる。pushはMac常駐（5分おき）が運ぶ。"""
    entries, problems = [], []
    for raw in paths:
        p = (REPO / raw).resolve()
        rel = p.relative_to(REPO).as_posix()
        if not p.is_file():
            problems.append(f"{rel}：ファイルが無い")
            continue
        if not rel.startswith("share/"):
            problems.append(f"{rel}：share/ の外にある（公開されないので渡せない）")
            continue
        size = p.stat().st_size
        if size > MAX_BYTES:
            problems.append(f"{rel}：{size/1024/1024:.1f}MB。"
                            f"1MBを超えるものは公開側に置かない約束")
            continue
        entries.append({"path": rel, "url": BASE_URL + rel,
                        "marker": marker_of(p), "bytes": size})

    if MANIFEST.exists():
        old = json.loads(MANIFEST.read_text(encoding="utf-8")).get("entries", [])
    else:
        old = []
    merged = {e["path"]: e for e in old}
    for e in entries:
        merged[e["path"]] = e
    # 台帳が太り続けないよう、直近30件だけ見張る
    keep = list(merged.values())[-30:]

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps({"entries": keep,
                    "登録日時": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sh("git", "add", MANIFEST.as_posix(), *[e["path"] for e in entries])
    c = sh("git", "commit", "-m",
           "配達: " + ", ".join(e["path"] for e in entries) if entries
           else "配達: 台帳の更新")
    if c.returncode == 0:
        print("commitした。Mac常駐（5分おき）がpushで運ぶ")
    else:
        print("commitする変更は無し（すでに載っている）")
    return entries, problems


def read_result():
    """runnerが持ち帰った確認結果を origin/main から読む。"""
    sh("git", "fetch", "-q", "origin", "main")
    r = sh("git", "show", f"origin/main:{RESULT_REL}")
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def run_conclusion():
    """書き戻しが権限で弾かれた場合の予備。github.comのHTMLから赤/青だけ読む。"""
    r = subprocess.run(["curl", "-sS", "--max-time", "30", RUNS_HTML],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "不明"
    head = r.stdout[:200000]
    if "completed successfully" in head:
        return "成功あり"
    if "completed with errors" in head or "Failure" in head:
        return "失敗あり"
    return "不明"


def show(entries, wait, limit_sec=1500):
    started = time.time()
    want = {e["url"] for e in entries} if entries else None
    while True:
        data = read_result()
        if data:
            got = {r["url"]: r for r in data.get("結果", []) if r.get("ok")}
            if want is None or want <= set(got):
                print(f"\n確認できたURL（確認日時 {data.get('確認日時_UTC')} / "
                      f"{data.get('確認のしかた')}）:")
                for url in (want or got.keys()):
                    r = got[url]
                    print(f"  {url}\n    HTTP {r['http']} / {r['bytes']}バイト / "
                          f"目印「{r['marker']}」を確認")
                return 0
        if not wait or (time.time() - started) > limit_sec:
            break
        print(f"…確認待ち {int(time.time()-started)}秒（Mac常駐のpush→Pages反映→"
              f"runnerの実地確認、の順に進む）", flush=True)
        time.sleep(30)

    print("\n渡せません。まだ 200 を実地で確認できていない。")
    print(f"  GitHub側の実行の様子: {run_conclusion()}")
    print(f"  詳しくは {RUNS_HTML}")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="share/ の下の配達物")
    ap.add_argument("--wait", action="store_true", help="確認が取れるまで待つ")
    ap.add_argument("--status", action="store_true", help="今の確認結果だけ見る")
    a = ap.parse_args()

    if a.status or not a.paths:
        data = read_result()
        if not data:
            print("まだ確認結果が無い")
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data.get("全部通ったか") else 1

    entries, problems = register(a.paths)
    for p in problems:
        print(f"✕ 渡せない — {p}")
    if not entries:
        return 1
    return show(entries, a.wait)


if __name__ == "__main__":
    sys.exit(main())
