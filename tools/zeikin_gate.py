#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1036番【税金ライン・3区＝検品】告発にしない門。★AIを1回も呼ばない。

━━ なぜ要るか（たまごさん・2026-09-23 原文）━━

  「誰かを悪者にしようっていうんじゃなくて、そういうズルができないような社会にしたい」

  税金の話は、放っておくと必ず「あいつが悪い」になる。なった瞬間に、
  ①間違えたときに謝るのがたまごさんになり（4分類判定の2番）
  ②読んだ人が怒りで回り始める（憲法第21条「怒りで回さない、笑いで回す」に真っ向から反する）。

  だから**文章の側で機械的に止める。**思い出した人だけが通る門にはしない。

━━ 落とす条件は3つだけ（増やさない）━━

  ZG1  個人を名指しして責めている（「◯◯議員は〜だ」＋非難語が同じ文の中）
       → 落とす。制度・金額・仕組みの話に書き換えれば通る。
  ZG2  断定語（陰謀・犯罪・隠蔽・不正・詐欺・私物化・着服・ぼったくり …）を使っている
       → 落とす。事実として立証していない限り、これは意見であって事実ではない。
  ZG3  「確認できたこと」と「確認できていないこと」が分かれていない
       → 落とす。★これが無いと、読んだ人は全部を事実だと思って人に転送する。

  ★数字の出典・前に出した数字との食い違いは **tools/kazu_gate.py** が見る。
    ここに2つ目の判定を書かない（1018番：判定が2か所にあると片方だけ直る）。
    このファイルは kazu_gate.py を**必ず**呼ぶ。片方だけ通った状態を作らせない。

━━ 使い方 ━━

    python3 tools/zeikin_gate.py --file status/uratori/xxx.md
    echo "…" | python3 tools/zeikin_gate.py
    python3 tools/zeikin_gate.py --self-test     # わざと悪い文で落ちるか試す

終了コード: 0=通過 / 1=落とした（★出してはいけない）
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
KAZU = os.path.join(HERE, "kazu_gate.py")

# ZG1 個人を指す形（肩書・敬称）。組織名・政党名は入れない（個人ではないので）
HITO = re.compile(
    r"[一-鿿゠-ヿA-Za-z]{2,8}"
    r"(議員|大臣|首相|総理|知事|市長|町長|村長|長官|次官|局長|理事長|会長|社長|氏|さん|君)"
)
# 非難語（「その人が悪い」と読める語）
HINAN = re.compile(
    r"(悪い|ずるい|卑怯|恥知らず|許せない|responsible|クズ|腐って|嘘つき|"
    r"私腹|懐に入れ|着服|懐へ|でたらめ|무責任|無責任|税金泥棒|寄生)"
)
# ZG2 立証していないのに使うと断定になる語
DANTEI = re.compile(
    r"(陰謀|犯罪|隠蔽|いんぺい|不正|詐欺|横領|着服|私物化|ぼったくり|"
    r"税金泥棒|癒着|裏金|出来レース|グル|仕組まれ)"
)
# ZG3 この2つが両方そろっていること
KAKUNIN_OK = re.compile(r"(確認できたこと|裏が取れたこと|ここまでは確かめた)")
KAKUNIN_NG = re.compile(r"(確認できていないこと|まだ確かめられていない|裏が取れていないこと|取れなかったこと)")

# ZG4 難しい言葉（たまごさん 2026-09-23：「難しい言葉を1つも使わない。
#     使うならその場で1行で説明」）。★説明が無ければ落とす。
#     説明とみなす形： 「◯◯＝」「◯◯とは」「◯◯（…）」のどれか。
MUZUKASHII = [
    "特例", "経過措置", "持分", "控除", "課税標準", "累進課税", "逓減", "按分",
    "賦課", "徴収", "減免", "繰越", "損益通算", "非課税枠", "納付", "譲渡所得",
    "受贈", "生前贈与", "相続時精算課税", "路線価", "評価額", "申告",
    "財政投融資", "特別会計", "一般会計", "歳出", "歳入", "補正予算", "予備費",
    "標準報酬月額", "賦課方式", "マクロ経済スライド", "所得代替率",
]


def _sentences(text: str):
    for s in re.split(r"[。\n！？!?]", text):
        s = s.strip()
        if s:
            yield s


def check(text: str):
    """落とした理由の一覧を返す。空なら通過。"""
    bad = []

    # ZG1
    for s in _sentences(text):
        m = HITO.search(s)
        if m and HINAN.search(s):
            bad.append("ZG1 個人を名指しして責めています → 「%s」…（%s）"
                       % (s[:40], m.group(0)))
    # ZG2
    for m in DANTEI.finditer(text):
        i = max(0, m.start() - 20)
        bad.append("ZG2 立証していない断定語『%s』 → 「…%s…」"
                   % (m.group(0), text[i:m.end() + 15].replace("\n", " ")))
    # ZG3
    if not (KAKUNIN_OK.search(text) and KAKUNIN_NG.search(text)):
        bad.append("ZG3 「確認できたこと」と「確認できていないこと」が分かれていません")

    # ZG4
    for w in MUZUKASHII:
        if w not in text:
            continue
        if re.search(re.escape(w) + r"\s*(＝|=|とは|（|\()", text):
            continue
        bad.append("ZG4 難しい言葉『%s』に説明がありません → その場で1行（%s＝…）を足すか、言い換える" % (w, w))

    return bad


def run_kazu(text: str):
    """★数字の門を必ず通す。片方だけ通った状態を作らせない。"""
    if not os.path.exists(KAZU):
        return 1, "tools/kazu_gate.py が見つかりません（★この門は単独では使えません）"
    p = subprocess.run([sys.executable, KAZU, "--text", text],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


SELFTEST_NG = """佐藤議員は税金泥棒で、裏金を私腹に入れている。
年間3800億円が無駄になっている。
"""
SELFTEST_OK = """## 確認できたこと
この制度は法律に書かれている（https://laws.e-gov.go.jp/api/2/keyword?keyword=相続税 200 12:40）。

## 確認できていないこと
いくら使われたかは、まだ1つの資料でしか見ていない。

## 3つの質問
いくら／だれに／なぜ。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--text")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-kazu", action="store_true", help="★普段は使わない")
    a = ap.parse_args()

    if a.self_test:
        ng = check(SELFTEST_NG)
        ok = check(SELFTEST_OK)
        print("わざと悪い文 → 落とした理由 %d件（1件以上なら合格）" % len(ng))
        for b in ng:
            print("   " + b)
        print("良い文 → 落とした理由 %d件（0件なら合格）" % len(ok))
        for b in ok:
            print("   " + b)
        return 0 if (ng and not ok) else 1

    if a.file:
        text = io.open(a.file, encoding="utf-8").read()
    elif a.text:
        text = a.text
    else:
        text = sys.stdin.read()

    bad = check(text)
    rc = 0
    if bad:
        print("✕ 3区で落としました（出してはいけない）")
        for b in bad:
            print("   " + b)
        rc = 1
    else:
        print("◯ 3区（告発にしない門）通過")

    if not a.no_kazu:
        krc, kout = run_kazu(text)
        print("--- 数字の門（tools/kazu_gate.py） ---")
        print(kout.strip()[:3000])
        if krc != 0:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
