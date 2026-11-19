#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1028番【Julesの採点機】試験の答えを機械だけで判定する。★AIを1回も呼ばない。課金0。

なぜ要るか：
  「使えるなら採用、使えないならクビ」を**後から動かせない形**で決めるため、
  採点を人の目ではなく機械に固定する。基準は status/1028/jules_saiten_kijun.md。

使い方:
  # PRの中身をGitHubから取って採点する（Mac側）
  python3 tools/1028_jules_saiten.py --pr 461
  # 手元のファイルを採点する
  python3 tools/1028_jules_saiten.py --file yomi-answers/jules.json
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

TARGET_PATH = "yomi-answers/jules.json"
GATE_REPO = "tamago2022/joy-relief-station"
KATA = re.compile(r"^[゠-ヿー・]+$")   # 全角カタカナ＋長音＋中黒だけ
GOUKAKU = 82          # 149件中82件＝55.0%（人の54.5%を上回る最小の整数）
NINGEN = 0.545        # 人（Claude子セッション）の自己検品 169/310


def _targets():
    p = os.path.join(REPO, "status", "1028", "jules_shiken_149.json")
    return json.load(open(p, encoding="utf-8"))


def saiten(text, changed_files=None, target=None):
    """(印, 合格率, [理由...]) を返す。印は '◯採用' / '△条件付き' / '✕クビ'。

    ★2026-09-23（1030番）target を足した理由：
      同じ149件を Codex にも投げると、置き場は `yomi-answers/codex.json` になる。
      TARGET_PATH を決め打ちのままだと、**Codexの正しい答えが門1で全部✕になる。**
      規則（件数・キー一致・カタカナ・合格線82件）は1文字も変えていない。
      ★採点の規則はこのファイルにしか書かない。baton.py 側には1行も写さない。
    """
    target = target or TARGET_PATH
    names = _targets()
    riyu, kado = [], True

    # --- 門1：変更が1ファイルだけか
    if changed_files is not None:
        if list(changed_files) != [target]:
            kado = False
            riyu.append("門1 ✕ 変更が %s の1本だけではない：%s"
                        % (target, ", ".join(changed_files) or "（0本）"))
        else:
            riyu.append("門1 ◯ 変更は %s の1本だけ" % target)

    # --- 門2：JSONとして読めるか
    try:
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError("辞書ではない（%s）" % type(d).__name__)
        riyu.append("門2 ◯ JSONとして読めた（%d件）" % len(d))
    except Exception as e:
        riyu.append("門2 ✕ JSONとして読めない：%s" % e)
        return "✕クビ", 0.0, riyu

    # --- 門3：キー集合が完全一致か
    want, got = set(names), set(d.keys())
    if want != got:
        kado = False
        tarinai, yokei = sorted(want - got), sorted(got - want)
        riyu.append("門3 ✕ キーが一致しない（足りない%d件／余計%d件）" % (len(tarinai), len(yokei)))
        for n in tarinai[:5]:
            riyu.append("    足りない: %s" % n)
        for n in yokei[:5]:
            riyu.append("    余計: %s" % n)
    else:
        riyu.append("門3 ◯ キー149件が完全一致")

    # --- 合格率
    tootta = [n for n in names if (d.get(n) or "").strip() and KATA.match((d.get(n) or "").strip())]
    rate = len(tootta) / float(len(names))
    riyu.append("合格率 %d/%d＝%.1f%%（人は54.5%%）" % (len(tootta), len(names), rate * 100))

    # 通らなかった値のうち、空ではないのに形が違うもの＝指示を外している
    katachi = [(n, d.get(n)) for n in names
               if (d.get(n) or "").strip() and not KATA.match((d.get(n) or "").strip())]
    if katachi:
        riyu.append("カタカナ以外が混ざったもの %d件（例：%s）"
                    % (len(katachi), " / ".join("%s→%s" % (a, b) for a, b in katachi[:3])))

    if not kado:
        return "✕クビ", rate, riyu
    if len(tootta) >= GOUKAKU:
        return "◯採用", rate, riyu
    return "△条件付き", rate, riyu


def _from_pr(num):
    import _965_keijiban as K
    r = K.run_job({"repo": GATE_REPO, "action": "prfiles", "number": num})
    files = [f.get("name") for f in (r.get("files") or [])]
    head = K.run_job({"repo": GATE_REPO, "action": "prstate", "numbers": [num]})
    pr = (head.get("prs") or [{}])[0]
    c = K.run_job({"repo": GATE_REPO, "action": "content",
                   "path": TARGET_PATH, "ref": "refs/pull/%s/head" % num})
    return (c.get("text") or c.get("body") or ""), files, pr


if __name__ == "__main__":
    a = sys.argv
    if "--file" in a:
        p = a[a.index("--file") + 1]
        txt = open(p if os.path.isabs(p) else os.path.join(REPO, p), encoding="utf-8").read()
        mark, rate, riyu = saiten(txt)
        pr = {}
    else:
        num = a[a.index("--pr") + 1]
        txt, files, pr = _from_pr(num)
        mark, rate, riyu = saiten(txt, files)
    print("=" * 56)
    print("Julesの試験　判定：%s（合格率 %.1f%%）" % (mark, rate * 100))
    if pr:
        print("PR: %s  %s" % (pr.get("url"), pr.get("title")))
    print("=" * 56)
    for r in riyu:
        print(" ", r)
