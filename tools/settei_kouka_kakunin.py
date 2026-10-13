#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/settei_kouka_kakunin.py ── 「設定が効いていない気がする」を機械で測る係。

34683号（判定日赤）:
  言われた日時 2026-08-07(金)02:06「設定が効いていない気がする：CLAUDE.mdを読み直して」
  一言で終わっていて具体的にどの設定かが書かれていないまま1ヶ月以上未着手→判定日赤。

━━ この係が確定させたこと ━━
  AGENTS.md/CLAUDE.mdの過去の実例（34483号「認証情報代理入力禁止」等）を見ると、
  この工場では「文章の注意書きだけでは効かない」が繰り返し起きていた。
  共通パターン：①憲法に文章だけ書く → ②1ヶ月気づかれず判定日赤 → ③機械の関所に変える。
  34683号への対応は、個別の1ルールを直すことではなく、
  **「憲法に書いた約束に、機械の裏付け（tools/配下のファイル）が本当にあるか」を
  定期的に自動で点検する**仕組みを作ることだと判断した（CLAUDE.md/AGENTS.md追記と対）。

━━ やること ━━
  CLAUDE.md / AGENTS.md（本リポジトリ、および joy-relief-station があれば両方）を読み、
  本文中に出てくる `tools/xxx.py` `tools/xxx.mjs` `tools/xxx.sh` 形式のパスを全部抽出し、
  実際にファイルが存在するかどうかを突き合わせる。
  「憲法に書いてあるのに実体のファイルが無い」＝まさに「設定が効いていない」の実物。

使い方
    python3 tools/settei_kouka_kakunin.py            # 点検して結果を表示＋JSON保存
    python3 tools/settei_kouka_kakunin.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT_JSON = os.path.join(ST, "public", "settei_kouka.json")

JST = datetime.timezone(datetime.timedelta(hours=9))

# 点検対象：(リポジトリルート, [相対ファイルパス...])
TARGETS = [
    (REPO, ["CLAUDE.md", "AGENTS.md"]),
    ("/Users/mac/Desktop/joy-relief-station", ["CLAUDE.md", "AGENTS.md"]),
]

PATTERN = re.compile(r"[\w./_-]+\.(?:py|mjs|sh)(?=[^\w.]|$)")

# 他リポジトリへの相対パスに使われる接頭辞 → そのリポジトリのルート実パス。
# 「tamago-shinchoku/tools/xxx.py」のような「他方から見た相対パス」表記を
# 自分のリポジトリ基準でそのまま結合すると二重パスになり誤検知するため、
# 接頭辞を剥がしてから正しいルートで存在確認する。
CROSS_REPO_PREFIX = {
    "tamago-shinchoku": "/Users/mac/tamago/tamago-shinchoku",
    "joy-relief-station": "/Users/mac/Desktop/joy-relief-station",
}


def now():
    return datetime.datetime.now(JST)


PLACEHOLDER_NAMES = {"xxx", "foo", "bar", "example", "sample"}


def is_placeholder(path: str) -> bool:
    base = os.path.basename(path)
    stem = base.rsplit(".", 1)[0]
    return stem.lower() in PLACEHOLDER_NAMES


def resolve(repo_root: str, path: str, nearby_text: str = "") -> str:
    """表記ゆれ（他リポジトリ名を先頭に持つ相対パス）を解決して絶対パスを返す。
    ★近傍の文章だけでクロスリポジトリ判定すると「他リポジトリの名前が
      文中に出てくるだけ」で誤検知する（34683号点検スクリプト自身の実測で発覚）。
      だからパス自体に接頭辞が付いている場合だけクロスリポジトリとして解決する。
    """
    first = path.split("/", 1)[0]
    if first in CROSS_REPO_PREFIX:
        rest = path.split("/", 1)[1] if "/" in path else ""
        return os.path.join(CROSS_REPO_PREFIX[first], rest)
    return os.path.join(repo_root, path)


def scan_file(repo_root: str, rel_path: str):
    """1ファイルからツール言及パスを抽出し、存在確認した結果のリストを返す。"""
    full = os.path.join(repo_root, rel_path)
    results = []
    if not os.path.exists(full):
        return results
    with io.open(full, encoding="utf-8") as f:
        text = f.read()
    seen = set()
    for m in PATTERN.finditer(text):
        path = m.group(0)
        if "/" not in path or path in seen or is_placeholder(path):
            continue
        seen.add(path)
        target_full = resolve(repo_root, path)
        exists = os.path.exists(target_full)
        results.append({"path": path, "exists": exists})
    return results


def main():
    if "--self-test" in sys.argv:
        return self_test()

    all_results = []
    missing_total = 0
    for repo_root, files in TARGETS:
        for rel in files:
            for r in scan_file(repo_root, rel):
                r["repo"] = os.path.basename(repo_root.rstrip("/"))
                r["source"] = rel
                all_results.append(r)
                if not r["exists"]:
                    missing_total += 1

    missing = [r for r in all_results if not r["exists"]]
    present = [r for r in all_results if r["exists"]]

    print("点検対象（憲法ファイル中のtools言及）: %d件" % len(all_results))
    print("実在する: %d件" % len(present))
    print("実在しない（憲法に書いてあるのに無い＝効いていない疑い）: %d件" % len(missing))
    for m in missing:
        print("  - [%s] %s（%s内で言及）" % (m["repo"], m["path"], m["source"]))

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    payload = {
        "checkedAt": now().strftime("%Y-%m-%d %H:%M:%S"),
        "n34683": True,
        "total": len(all_results),
        "present": len(present),
        "missing": len(missing),
        "missingList": missing,
    }
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("JSON保存: %s" % OUT_JSON)

    return 1 if missing_total > 0 else 0


def self_test():
    """自分自身（このファイル）が実在パスとして正しく判定できるかの最小テスト。"""
    tmp_dir = "/tmp/settei_kouka_selftest"
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(os.path.join(tmp_dir, "tools"), exist_ok=True)
    with io.open(os.path.join(tmp_dir, "tools", "real.py"), "w", encoding="utf-8") as f:
        f.write("# dummy\n")
    claude_md = os.path.join(tmp_dir, "CLAUDE.md")
    with io.open(claude_md, "w", encoding="utf-8") as f:
        f.write("ここは tools/real.py で機械化した。だが tools/nai.py はまだ無い。\n")

    results = scan_file(tmp_dir, "CLAUDE.md")
    ok_real = any(r["path"] == "tools/real.py" and r["exists"] for r in results)
    ok_fake = any(r["path"] == "tools/nai.py" and not r["exists"] for r in results)
    if ok_real and ok_fake:
        print("SELF_TEST: PASS（実在/不在を両方正しく見分けた）")
        return 0
    print("SELF_TEST: FAIL results=%r" % results)
    return 2


if __name__ == "__main__":
    sys.exit(main())
