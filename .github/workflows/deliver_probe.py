#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub の runner の上で走り、公開URLを「外から」叩いて確かめる係。

たまごさんのスマホと同じ条件（ログイン無し・素のインターネット）で叩く。
GitHub Pages は push から反映まで数十秒〜数分かかるので、200 になるまで待つ。
"""
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "share" / "_deliver" / "manifest.json"
RESULT = ROOT / "status" / "public" / "deliver_verified.json"

MAX_WAIT_SEC = 420      # Pages の反映待ち上限（7分）
INTERVAL_SEC = 20
MIN_BYTES = 400         # これ未満は「空HTML／404ページを掴んだ」とみなす


def curl(url):
    """(http_code, body_bytes, body_text) を返す。落ちても例外にしない。"""
    try:
        p = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", "30",
             "-w", "\n__HTTPCODE__%{http_code}", url],
            capture_output=True, timeout=45,
        )
        out = p.stdout.decode("utf-8", "replace")
        code = "000"
        if "__HTTPCODE__" in out:
            out, _, tail = out.rpartition("\n__HTTPCODE__")
            code = tail.strip() or "000"
        return code, len(p.stdout), out
    except Exception as e:  # noqa: BLE001
        return "000", 0, f"(curl自体が失敗: {e})"


def main():
    if not MANIFEST.exists():
        print("配達台帳が無い。確かめるものが無いので素通り")
        pathlib.Path("/tmp/deliver_ok").write_text("empty")
        return 0

    entries = json.loads(MANIFEST.read_text(encoding="utf-8")).get("entries", [])
    if not entries:
        print("配達台帳が空。素通り")
        pathlib.Path("/tmp/deliver_ok").write_text("empty")
        return 0

    pending = {e["url"]: e for e in entries}
    results = {}
    started = time.time()

    while pending and (time.time() - started) < MAX_WAIT_SEC:
        for url in list(pending):
            entry = pending[url]
            code, nbytes, body = curl(url)
            marker = entry.get("marker") or ""
            has_marker = (marker in body) if marker else True
            ok = (code == "200") and (nbytes >= MIN_BYTES) and has_marker
            results[url] = {
                "url": url,
                "path": entry.get("path"),
                "http": code,
                "bytes": nbytes,
                "marker": marker,
                "marker_found": has_marker,
                "ok": ok,
            }
            state = "○" if ok else "×"
            print(f"{state} {code} {nbytes}バイト 目印={'有' if has_marker else '無'} {url}",
                  flush=True)
            if ok:
                del pending[url]
        if pending:
            waited = int(time.time() - started)
            print(f"…まだ {len(pending)} 本。Pages反映待ち {waited}秒経過。"
                  f"{INTERVAL_SEC}秒待ってもう一度", flush=True)
            time.sleep(INTERVAL_SEC)

    all_ok = not pending
    payload = {
        "確認日時_UTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "確認したコミット": os.environ.get("COMMIT_SHA", "")[:12],
        "確認のしかた": "GitHubのrunnerから公開URLをcurlし、HTTP200・中身のバイト数・目印の文字列の3つを見た",
        "全部通ったか": all_ok,
        "結果": [results[e["url"]] for e in entries if e["url"] in results],
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## 配達物の実地確認\n\n")
            fh.write("| 判定 | HTTP | バイト数 | 目印 | URL |\n|---|---|---|---|---|\n")
            for r in payload["結果"]:
                fh.write(f"| {'○' if r['ok'] else '×'} | {r['http']} | {r['bytes']} | "
                         f"{'有' if r['marker_found'] else '無'} | {r['url']} |\n")

    if all_ok:
        pathlib.Path("/tmp/deliver_ok").write_text("ok")
        print("\n全部 200・中身あり。渡してよい")
        return 0
    print("\n通らなかったものがある。渡してはいけない")
    return 1


if __name__ == "__main__":
    sys.exit(main())
