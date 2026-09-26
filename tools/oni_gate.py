#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鬼監督の判定は、ここにしか書かない。

━━ なぜこれを作ったか（2026-09-22・たまごさん）━━

  「人がいなくても回る仕組みがいいな。俺の分身が欲しいんだよね。
   鬼監督が結構それに近い存在ではあるんだけど、俺のデータを本当に覚えて、
   『俺だったらこれは絶対許さない』を、俺の代わりにやってくれる人が必要なんだよ。」

実測して分かったこと（2026-09-22 07:30・この工場の中で確かめた）：

  $ grep -c "kenpin_gate|鬼監督" .githooks/pre-push .git/hooks/pre-commit
    .githooks/pre-push:0
    .git/hooks/pre-commit:0

  ＝ 鬼監督は**どの機械にも呼ばれていなかった。**
  `tools/kenpin_gate.py --can-deliver` という門は既にあったが、それを呼べと
  書いてあるのは tools/prompt_rules/always-18-kenpin-gate.md だけ。
  つまり「思い出したセッションだけが通る門」＝**呼ばなければ素通り。**

  これは 1018番（進捗表が26時間ウソの緑を出していた件）と同じ形の事故である。
  あのときの原因は「判定が2か所に別々に書いてあって片方だけ直っていた」。
  今回の原因は「判定が0か所にしか強制されていない」。
  → 1018番と同じ直し方をする。**判定を1ファイルに置き、機械の一本道に埋める。**

━━ 置いた場所（ここが肝）━━

  .githooks/pre-push → push のたびに必ず走る。
  push はセッションの種類・道具・人の記憶に関係なく、
  **origin/main へ出るときに必ず1回だけ通る唯一の点。**
  だから「通らないと出られない」。呼び忘れという概念が存在しなくなる。

━━ なぜAIに採点させないのか ━━

  調べた失敗例：AIに自分の出力を自己レビューさせると自分に10点を付ける
  （self-preference bias・Panickssery et al. 2024 で因果関係まで実証されている）。
  → **ここではAIを1回も呼ばない。**全部ただの文字列判定。
    クレジットを1円も使わない。毎回同じ答えが出る。甘くならない。

━━ 借金のあつかい ━━

  既にあるページを全部赤にすると、やり直しの山ができてかえって止まる
  （鬼監督「厳しさの調整」）。だから gate_fact_source.py と同じ型を丸ごと移植する：
  いまある違反は status/oni_baseline.json に「借金」として記録し、push は止めない。
  **これから新しく増えた分だけを止める。**

━━ 規則（たまごさんが実際に言ったことだけ。思いつきを足さない）━━

  各規則に「いつ言われたか」を必ず持たせる。出どころの無い規則はここに書かない。

使い方:
  python3 tools/oni_gate.py <file.html|file.md> [--strict] [--json out.json]
  python3 tools/oni_gate.py --write-baseline        # いまの違反を借金として記録（初回だけ）
  python3 tools/oni_gate.py --self-test             # 規則が本当に効くか見本で試す

終了コード: 0=通過 / 1=新しい違反あり（--strict時のみ止める）
"""
from __future__ import annotations

import argparse
import datetime
import glob
import html as _html
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "status", "oni_baseline.json")
LOG = os.path.join(REPO, "status", "oni_gate.log")
JST = datetime.timezone(datetime.timedelta(hours=9))


# ---------------------------------------------------------------------------
# 規則表：(記号, 名前, 正規表現, たまごさんの言葉＝出どころ)
#
# 入れてよいのは「間違えようがないもの」だけ。
# 迷うものを入れると誤爆の山になり、関所ごと信用されなくなって外される。
# ---------------------------------------------------------------------------
RULES = [
    ("R1", "実行ログを貼っている",
     r"Traceback \(most recent call last\)|npm ERR!|command not found|"
     r"fatal: |Exit code: |zsh: |bash: line ",
     "鬼監督§10『実行ログ・コマンド出力・エラーの抜粋を書いていないか』"
     "（たまごさん『まるで要らない』と名指し）"),

    ("R2", "diffやコミットを貼っている",
     r"diff --git|^@@ -|\+\+\+ b/|--- a/|commit [0-9a-f]{7,}|origin/main|"
     r"git (?:push|commit|add|merge)\b",
     "鬼監督§10『ファイル名・diff・コミット・ブランチを書いていないか』"),

    ("R3", "謝っている・言い訳している",
     r"申し訳|すみません|すいません|ご迷惑|お詫び|失礼しました|お待たせしました",
     "鬼監督§10『謝罪・言い訳・前置きを書いていないか』"),

    ("R4", "見ていない他人の反応を書いている",
     r"話題沸騰|話題を呼ん|続出|後を絶た|大反響|バズっ|ざわつ|絶賛の嵐",
     "鬼監督§5『観測していない他人の反応を書いていないか』"),

    ("R5", "欠乏感で脅している",
     r"見ないと損|知らないと損|見逃したら|今のうちに見ないと|見なきゃ損",
     "鬼監督§5『欠乏感で脅す言葉を使っていないか』"),

    ("R6", "水道水コピーになっている",
     r"代表曲のひとつ|代表曲の一つ|言わずと知れた|名曲中の名曲|説明不要の|"
     r"誰もが知る名曲",
     "鬼監督§5『水道水コピーになっていないか』"
     "（bonjovi-ojisan-kobun が禁じている型そのもの）"),
]

# 正規表現では書けない、形で見るしかない規則は下で個別に判定する。
SHAPE_RULES = {
    "R7": ("「完了」と言っているのに押せるURLが1つも無い",
           "鬼監督§9『本番のURLを実際に開いて、変わっていることを自分の目で見たか』"
           "／たまごさん『実装しただけで完了と言うな』（30回以上）"),
    "R8": ("同じ動画が同じページに2回以上出ている",
           "鬼監督§0『同じ動画が同じページに2回以上出ていないか。3枚並ぶのは論外』"),
    "R9": ("falを使ったと書いてあるのに、いくらかかったかが書いていない",
           "鬼監督§1『falを使った作業の報告に「使ったモデル」「回数」"
           "「1回いくら」「合計」が書いてあるか』（2026-09-06・案件#510で新設）"),
}

YT_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")
URL_RE = re.compile(r'href=["\']https?://')
DONE_RE = re.compile(r"完了|できました|できています|反映しました|直しました")
# 「falで12枚つくった」のように日本語がすぐ続く書き方が多い。
# \b は日本語文字との境目では効かないので、英字が続かないことで見る。
FAL_RE = re.compile(r"(?<![a-zA-Z])fal(?:\.ai|-ai)?(?![a-zA-Z])", re.I)
MONEY_RE = re.compile(r"[0-9][0-9,\.]*\s*円|\$[0-9]|ドル|USD")


# ★2026-09-26（1152番）台帳を出す紙のための、ただ1つの例外。
#
#   宿題台帳（share/check/1138-shukudai.html）は、たまごさんや引き継ぎ紙に
#   書いてあった文を**一字一句そのまま並べる**紙。だから題名の中に
#   「command not found」「git add -A」のような文字がそのまま入る。
#   これは**この紙がログを貼っている**のではなく、**台帳がそう記録している**。
#
#   実測（2026-09-26）：この区別が無かったため、鬼監督が1138をR1/R2で止め、
#   直しようがなかった（直す＝たまごさんの発言を書き換える、になってしまう）。
#
#   そこで「引用である」と明示した箱の中だけ、規則の照合から外す。
#     <code data-inyou="台帳">…</code>
#   ★外すのはR1/R2（ログ・diffを貼っていないか）だけ。
#     謝罪・水道水コピー・URLの有無（R3〜R9）は引用の中でも今までどおり見る。
#   ★この印を自分の文章に付けて逃げないこと。付けてよいのは
#     「別のファイルから一字一句写したもの」だけ。
INYOU_RE = re.compile(r'(?is)<code[^>]*data-inyou=[^>]*>.*?</code>')


def visible_text(raw: str, inyou_nuku: bool = False) -> str:
    """HTMLから、たまごさんの目に入る文字だけを取り出す。

    script/style の中はたまごさんには見えないので判定に使わない
    （見えないものを理由に落とすと、直しようがない指摘になる）。

    inyou_nuku=True のときは、引用と明示された箱の中身も外す（上の例外）。
    """
    if inyou_nuku:
        raw = INYOU_RE.sub(" ", raw)
    t = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"[ \t]+", " ", t)


def judge(raw: str, label: str = "") -> list:
    """鬼監督の判定。ここが唯一の判定。ほかのどの道具もこれを呼ぶこと。

    返すのは違反の一覧。空なら通過。
    """
    text = visible_text(raw)
    # R1（実行ログ）R2（diff・コミット）だけは、引用と明示された箱の中を見ない
    text_noinyou = visible_text(raw, inyou_nuku=True)
    hits = []

    for code, name, pat, why in RULES:
        haba = text_noinyou if code in ("R1", "R2") else text
        for m in re.finditer(pat, haba, re.M):
            snippet = haba[max(0, m.start() - 30):m.end() + 30].strip()
            hits.append({"code": code, "name": name, "why": why,
                         "hit": m.group(0)[:60], "around": snippet[:120]})
            break  # 同じ規則は1ページ1件だけ挙げる（同じ話を何度も読ませない）

    # R7 完了と言っているのに押せるURLが無い
    if DONE_RE.search(text) and not URL_RE.search(raw):
        name, why = SHAPE_RULES["R7"]
        hits.append({"code": "R7", "name": name, "why": why,
                     "hit": "完了の言葉あり／href=http が0件", "around": ""})

    # R8 同じ動画が2回以上
    ids = YT_RE.findall(raw)
    dup = sorted({i for i in ids if ids.count(i) >= 2})
    if dup:
        name, why = SHAPE_RULES["R8"]
        hits.append({"code": "R8", "name": name, "why": why,
                     "hit": "／".join(dup[:5]), "around": ""})

    # R9 falを使ったのに金額が無い
    if FAL_RE.search(text) and not MONEY_RE.search(text):
        name, why = SHAPE_RULES["R9"]
        hits.append({"code": "R9", "name": name, "why": why,
                     "hit": "falの記述あり／金額の記述が0件", "around": ""})

    for h in hits:
        h["label"] = label
    return hits


# ---------------------------------------------------------------------------
# 借金（baseline）：いまある違反は止めない。新しく増えた分だけ止める。
# gate_fact_source.py と同じ型を丸ごと移植している。
# ---------------------------------------------------------------------------
def _key(label: str, h: dict) -> str:
    return "%s::%s::%s" % (os.path.basename(label), h["code"], h["hit"][:40])


def load_baseline() -> set:
    try:
        with open(BASELINE, encoding="utf-8") as f:
            return set(json.load(f).get("known", []))
    except Exception:
        return set()


def write_baseline(targets) -> int:
    known = []
    for p in targets:
        try:
            raw = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for h in judge(raw, p):
            known.append(_key(p, h))
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump({
            "書いた日": datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
            "これは何": "いまページに残っている鬼監督違反＝借金。"
                        "これは止めない。新しく増えた分だけを止めるための控え。",
            "件数": len(known),
            "known": sorted(set(known)),
        }, f, ensure_ascii=False, indent=1)
    print("借金として記録しました：%d件 → %s" % (len(set(known)), BASELINE))
    return 0


def _log(line: str):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (
                datetime.datetime.now(JST).strftime("%F %T"), line))
    except Exception:
        pass


def _self_test() -> int:
    """規則が本当に効くかを見本で確かめる。
    関所が「実は何も見ていなかった」を防ぐのはこの試験だけ。"""
    cases = [
        ("R1", '<p>Traceback (most recent call last): エラーが出ました</p>', True),
        ("R2", '<p>git push して origin/main に入れました</p>', True),
        ("R3", '<p>申し訳ありません、直しました</p>', True),
        ("R4", '<p>ネットで話題沸騰の一曲</p>', True),
        ("R5", '<p>これ見ないと損します</p>', True),
        ("R6", '<p>彼女の代表曲のひとつ。</p>', True),
        ("R7", '<p>完了しました</p>', True),
        ("R8", '<a href="https://youtu.be/AAAAAAAAAAA">1</a>'
               '<a href="https://youtu.be/AAAAAAAAAAA">2</a>', True),
        ("R9", '<p>falで12枚つくりました</p><a href="http://x">見る</a>', True),
        ("--", '<p>できました</p><a href="https://example.com/x">見る</a>', False),
    ]
    bad = 0
    for code, sample, should_hit in cases:
        hits = judge(sample, "self-test")
        got = [h["code"] for h in hits]
        ok = (code in got) if should_hit else (not hits)
        print("%s %-4s %s" % ("✅" if ok else "❌", code,
                              "／".join(got) if got else "（違反なし）"))
        if not ok:
            bad += 1
    print("\n見本試験：%d件中 %d件 合格" % (len(cases), len(cases) - bad))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="鬼監督の関所 — たまごさんに見せる前に機械で落とす")
    ap.add_argument("files", nargs="*", help="見るファイル（htmlやmd）")
    ap.add_argument("--strict", action="store_true",
                    help="新しい違反が1件でもあれば exit 1（push の手前用）")
    ap.add_argument("--write-baseline", action="store_true",
                    help="いまの違反を借金として記録する（初回だけ）")
    ap.add_argument("--self-test", action="store_true",
                    help="規則が効くか見本で試す")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    if a.write_baseline:
        targets = a.files or sorted(
            glob.glob(os.path.join(REPO, "share", "check", "*.html")))
        return write_baseline(targets)

    if not a.files:
        ap.print_help()
        return 0

    known = load_baseline()
    new_hits, old_hits = [], []
    for p in a.files:
        try:
            raw = open(p, encoding="utf-8", errors="replace").read()
        except Exception as e:
            print("読めませんでした: %s (%s)" % (p, e))
            continue
        for h in judge(raw, p):
            (old_hits if _key(p, h) in known else new_hits).append(h)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"new": new_hits, "known": old_hits},
                      f, ensure_ascii=False, indent=1)

    if old_hits:
        print("（前からある分 %d件は借金として見逃します）" % len(old_hits))

    if not new_hits:
        print("ONI_GATE: OK — 新しい違反はありません（%d件みました）" % len(a.files))
        _log("OK files=%d known=%d" % (len(a.files), len(old_hits)))
        return 0

    print("\n🛑 鬼監督が止めました。たまごさんに見せる前に直してください。\n")
    for h in new_hits:
        print("  ● %s" % h["name"])
        print("    どこ : %s" % os.path.basename(h.get("label") or ""))
        print("    見つけた文字: %s" % h["hit"])
        if h["around"]:
            print("    まわり: …%s…" % h["around"])
        print("    なぜ : %s\n" % h["why"])
    _log("NG files=%d new=%d codes=%s" % (
        len(a.files), len(new_hits), ",".join(h["code"] for h in new_hits)))
    return 1 if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
