#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/url_hantei.py ── 34575号

【判定日で赤になった案件】「URLを入れる → 結果が出る → Obsidianに保存される」
という一番コアな1本の流れを、まず動くところまで作る（CLI手動実行で十分）。

★1184号関所（オリジナル禁止・票 hyo-1792528560・sonomama）：判定ロジックを
  新しく書かない。判定は既存の tools/hantei.py の kensa_html() をそのまま呼ぶ
  （hantei.py自身の大原則「判定は、ここにしか書かない」をそのまま守る）。
  このファイルがやるのは配線だけ：
    ① URLを取りに行く（urllib.request。Python公式の標準手段・追加インストール不要）
    ② 既存の kensa_html() に渡して合否をもらう（判定基準は1文字も書き換えない）
    ③ 結果をObsidian Vaultへ1本のmdとして書く（AI出力/URL判定/ 配下・新規フォルダ）
    ④ status/url_hantei_log.jsonl にも1行残す（Obsidianが開けない時の控え）

★Vaultの関所（tools/stop_kanmon/vault_kanmon.mjs）を踏まえ、1回の実行で
  Vaultに書くのは1ファイルだけ（1日20回の上限に対して無害な回数）。
  00_現在地.md・作業キュー.md等の既存ファイルには一切触れない。

使い方:
  python3 tools/url_hantei.py --url "https://example.com/"
  python3 tools/url_hantei.py --url "https://example.com/" --no-vault   # 確認のみ、Vaultに書かない
  python3 tools/url_hantei.py --self-test                               # 判定ロジックの逆テスト
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hantei  # noqa: E402  判定の正本はこの1ファイルにしかない（呼ぶだけ）

JST = datetime.timezone(datetime.timedelta(hours=9))
VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain")
OUT_DIR = os.path.join(VAULT, "AI出力", "URL判定")
LOG = os.path.join(REPO, "status", "url_hantei_log.jsonl")


def fetch(url, timeout=15):
    """標準ライブラリだけでURLを取りに行く。戻り値: dict(status, body, error, ms)。"""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (tamago-url-hantei/1.0)"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read()
            return {"status": status, "body": body, "error": "",
                     "ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": b"", "error": "HTTP %s" % e.code,
                 "ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"status": 0, "body": b"", "error": str(e),
                 "ms": int((time.time() - t0) * 1000)}


def judge_url(url):
    """URL1本を判定する。判定本体は hantei.kensa_html() を呼ぶだけ。"""
    r = fetch(url)
    if r["error"] or r["status"] >= 400 or r["status"] == 0:
        return {"url": url, "ok": False, "mark": "🔴",
                 "reasons": [r["error"] or ("HTTP %s" % r["status"])],
                 "status": r["status"], "bytes": len(r["body"]), "ms": r["ms"]}
    text = r["body"].decode("utf-8", errors="ignore")
    ok, ng = hantei.kensa_html(text, name=url)
    return {"url": url, "ok": ok, "mark": "✅" if ok else "🔴",
             "reasons": ng if ng else ["中身あり・既存の判定(hantei.kensa_html)を通過"],
             "status": r["status"], "bytes": len(r["body"]), "ms": r["ms"]}


def _slug(url):
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s)[:40].strip("-")
    return s or "url"


def save_obsidian(result):
    """結果をObsidian Vaultへ1本のmdとして書く。戻り値: 書いたファイルの絶対パス。"""
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.datetime.now(JST)
    fname = "%s_%s.md" % (now.strftime("%Y-%m-%d_%H%M%S"), _slug(result["url"]))
    path = os.path.join(OUT_DIR, fname)
    lines = [
        "# URL判定：%s" % result["url"],
        "",
        "- 判定日時：%s" % now.strftime("%Y-%m-%d %H:%M JST"),
        "- 結果：%s %s" % (result["mark"], "合格" if result["ok"] else "不合格"),
        "- HTTPステータス：%s" % result["status"],
        "- バイト数：%s" % result["bytes"],
        "- 取得時間：%sms" % result["ms"],
        "",
        "## 理由",
    ]
    for reason in result["reasons"]:
        lines.append("- %s" % reason)
    lines.append("")
    lines.append(
        "（34575号「URLを入れる→結果が出る→Obsidianに保存される」コアフローの最小実装。"
        "判定ロジックは tools/hantei.py の kensa_html() をそのまま使用・新規発明なし）")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def run(url, write_to_vault=True):
    result = judge_url(url)
    saved_path = save_obsidian(result) if write_to_vault else None
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    row = dict(result)
    row["at"] = datetime.datetime.now(JST).isoformat()
    row["savedTo"] = saved_path
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return result, saved_path


def self_test():
    """逆テスト：判定が本当に赤を検出できるかを確かめる（枷1の精神）。"""
    ng = []
    ok1, reasons1 = hantei.kensa_html(
        "<html><head><title>t</title>"
        "<meta name=\"viewport\" content=\"width=device-width\"></head>"
        "<body>" + ("x" * 300) + "</body></html>")
    if not ok1:
        ng.append("正常なHTMLなのに不合格にした：%s" % reasons1)
    ok2, reasons2 = hantei.kensa_html("<html><body>short</body></html>")
    if ok2:
        ng.append("短すぎるHTML・title無し・viewport無しを合格にした（逆テスト失敗）")
    # URLが取れないケース（存在しないポート）も赤になるか
    bad = judge_url("http://127.0.0.1:1/nonexistent-34575")
    if bad["ok"]:
        ng.append("繋がらないURLを合格にした（逆テスト失敗）")
    print("自己試験：%s" % ("OK" if not ng else "NG"))
    for n in ng:
        print("  ★NG %s" % n)
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--no-vault", action="store_true",
                     help="Obsidianへ保存しない（確認のみ・ログだけ残す）")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.url:
        ap.error("--url か --self-test のどちらかが必要です")
    result, saved_path = run(a.url, write_to_vault=not a.no_vault)
    print(json.dumps({
        "url": result["url"], "mark": result["mark"], "ok": result["ok"],
        "status": result["status"], "bytes": result["bytes"], "ms": result["ms"],
        "reasons": result["reasons"], "savedTo": saved_path,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
