# -*- coding: utf-8 -*-
"""関所：曲ページに「裏の取れていない断定」を書かせない。

たまごさんの型：
  - 完全に裏取って。取れないなら書かない。
  - 事実には出典リンク。リンクを飛ばすのが「盗んでいない証明」。
  - 「オリジナル」と書くには作詞作曲クレジットの出典が要る。
  - 判定できないものは「書かない」側に倒す。無いほうがマシ、間違ってるより。

きっかけ（2026-09-19）:
  akiko「Do You Know?」のページに「2002年に発表されたオリジナル・バラード」とあった。
  2002年は裏が取れた（公式サイト／CDJournal／ユニバーサル）。
  だが「オリジナル」＝本人の書き下ろし、は作詞作曲クレジットが要る。
  公式サイト・CDJournal・ユニバーサルのどこにもクレジットは載っていなかった。
  → 裏が取れないので「オリジナル」は外した。これがこの関所の原型。

判定：
  note / about に「断定の事実」があるのに、その項目に出典URLが無ければ NG。
  出典URLとして認めるのは、その項目内の src / source / srcs フィールド、
  または note 本文中の http(s) リンク。

使い方:
  python3 tools/sekisho/gate_fact_source.py <coverGuide.ts>
      点検して一覧を出す（exit 0）
  python3 tools/sekisho/gate_fact_source.py <coverGuide.ts> --strict
      既存分(baseline)以外に1件でも出たら exit 1（push・仕入れの入口用）
  python3 tools/sekisho/gate_fact_source.py <coverGuide.ts> --json out.json
  python3 tools/sekisho/gate_fact_source.py <coverGuide.ts> --write-baseline
      いまの未出典分を「既知の借金」として記録する（初回だけ）

終了コード: 0=通過 / 1=新しい未出典の断定あり（--strict時）
"""
import json
import os
import re
import sys

BASELINE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "status", "fact_source_baseline.json",
)

# 断定の事実。危険度が高い順。
PATTERNS = [
    ("A", "オリジナル", r"オリジナル(?!ビデオ|・ビデオ)"),
    ("A", "原曲",       r"原曲"),
    ("A", "年号",       r"(?:19|20)\d{2}\s*年"),
    ("A", "代表曲",     r"代表曲|出世作|デビュー作|デビュー曲"),
    ("B", "カバー",     r"カバー|カヴァー|自作曲|書き下ろし"),
    ("B", "受賞",       r"受賞|グラミー|レコード大賞|1位|首位|No\.1"),
    ("B", "数字",       r"万枚|億回|万回|ミリオン|週連続"),
]

URL_RE = re.compile(r"https?://")
# { id: "...", title: "...", note: "..." } 形式の1項目
ENTRY_RE = re.compile(
    r'\{\s*id:\s*"((?:[^"\\]|\\.)*)"\s*,\s*title:\s*"((?:[^"\\]|\\.)*)"'
    r'(?P<rest>(?:[^{}]|\{[^{}]*\})*)\}'
)
NOTE_RE = re.compile(r'note:\s*"((?:[^"\\]|\\.)*)"')
SRC_RE = re.compile(r'(?:src|source|srcs|sourceUrl)\s*:\s*[\["]')


def scan(path):
    text = open(path, encoding="utf-8").read()
    bad = []
    for m in ENTRY_RE.finditer(text):
        sid, title, rest = m.group(1), m.group(2), m.group("rest")
        nm = NOTE_RE.search(rest)
        note = nm.group(1) if nm else ""
        if not note:
            continue
        has_src = bool(URL_RE.search(rest)) or bool(SRC_RE.search(rest))
        if has_src:
            continue
        hit = []
        for level, label, pat in PATTERNS:
            if re.search(pat, note):
                hit.append((level, label))
        if hit:
            line = text.count("\n", 0, m.start()) + 1
            bad.append({
                "id": sid,
                "title": title,
                "note": note,
                "line": line,
                "level": min(h[0] for h in hit),
                "why": "/".join(h[1] for h in hit),
            })
    return bad


def load_baseline():
    try:
        with open(BASELINE, encoding="utf-8") as f:
            return set(json.load(f).get("known", []))
    except Exception:
        return set()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    strict = "--strict" in args
    bad = scan(path)

    if "--write-baseline" in args:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({
                "note": "この関所ができた時点で既に出典の無かった断定。ここにある分は"
                        "pushを止めないが、直すべき借金。新しく増えた分だけを止める。",
                "known": sorted(b["id"] + "|" + b["note"] for b in bad),
            }, f, ensure_ascii=False, indent=1)
        print(f"baseline: {len(bad)} 件を記録しました -> {BASELINE}")
        return 0

    if "--json" in args:
        out = args[args.index("--json") + 1]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False, indent=1)

    known = load_baseline()
    new = [b for b in bad if (b["id"] + "|" + b["note"]) not in known]

    lv = {}
    for b in bad:
        lv[b["level"]] = lv.get(b["level"], 0) + 1
    print(f"SEKISHO_FACT_RESULT total={len(bad)} A={lv.get('A',0)} B={lv.get('B',0)} new={len(new)}")

    for b in sorted(new, key=lambda x: x["level"])[:50]:
        print(f'  [{b["level"]}] {b["id"]} (L{b["line"]}) {b["why"]}: {b["note"][:70]}')

    if strict and new:
        print("")
        print("🚧 出典の無い断定が新しく入りました。pushを止めます。")
        print("   ・断定の事実（年号／オリジナル／原曲／代表曲／受賞／枚数）には出典URLが必須。")
        print("   ・「オリジナル」と書くには作詞作曲クレジットの出典が必須。")
        print("   ・裏が取れないなら、その語を落とす。判定できないものは「書かない」側に倒す。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
