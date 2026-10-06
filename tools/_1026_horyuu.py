#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1026番：同定が通らず**わざと積まなかった組**を、理由つきで1枚にする。

★「積めなかった」を黙って消さない。消すと、同じ組を次のセッションがまた調べ直す。
★ここに載っている組は「調べれば積める」ではなく「**今ある出どころでは本人を決められない**」。
  決めるには、たまごさんが1つ選ぶか、フェス公式の出身地・SNSなど別の出どころが要る。
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import shiire_fetch as sf  # noqa: E402

RAW = os.path.join(REPO, "status", "shiire_raw")
KOUHO = os.path.join(REPO, "status", "shiire_kouho")
OUT = os.path.join(REPO, "status", "1026_shiire_horyuu.md")


def main():
    rows = []
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".json"):
            continue
        d = json.loads(io.open(os.path.join(RAW, fn), encoding="utf-8").read())
        if os.path.exists(os.path.join(KOUHO, fn)):
            continue
        cands = (d.get("musicbrainz") or {}).get("candidates") or []
        ok = d.get("identifyOk")
        if ok is None:
            ok, _ = sf.identify_ok(cands)
        w = d.get("works") or {}
        if ok and len(w.get("recordings") or []) >= 3:
            rows.append((d["name"], "積める（まだ積んでいないだけ）",
                         d.get("identifyWhy") or "", cands[:3]))
            continue
        why = d.get("identifyWhy") or d.get("worksWhyNot") or ""
        if ok and not (w.get("recordings") or []):
            why = "同定は通ったが、mbidから引ける録音が0件（MusicBrainzに曲が登録されていない）"
        rows.append((d["name"], "保留", why, cands[:3]))
    lines = ["# 仕入れ・保留の棚（1026番 2026-09-23）", "",
             "**ここに居る組は、まだ候補に積んでいない。**理由は下に1件ずつ書いてある。",
             "★「たぶんこの人」で埋めないために止めている。埋めれば率は下がるが、嘘が増える。", ""]
    hold = [r for r in rows if r[1] == "保留"]
    ready = [r for r in rows if r[1] != "保留"]
    lines += ["## 保留（%d組）" % len(hold), ""]
    for name, _, why, cands in hold:
        lines.append("### %s" % name)
        lines.append("- **止めた理由**：%s" % why)
        if cands:
            lines.append("- MusicBrainzに並んでいる同名：")
            for c in cands:
                lines.append("  - `%s` %s／%s／%s（score %s・mbid %s）"
                             % (c.get("name"), c.get("type") or "種別不明",
                                c.get("area") or "地域不明",
                                c.get("disambiguation") or "説明なし",
                                c.get("score"), (c.get("mbid") or "")[:8]))
            lines.append("- **決めるのに要るもの**：この組の出身地か公式の綴り。"
                         "フェスの名簿には名前しか無い（実測）。")
        lines.append("")
    if ready:
        lines += ["## 同定は通っている（積むのはこれから・%d組）" % len(ready), ""]
        for name, _, why, _c in ready:
            lines.append("- %s … %s" % (name, why))
    io.open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("保留 %d組／積める %d組 → status/1026_shiire_horyuu.md" % (len(hold), len(ready)))
    for name, st, why, _ in hold:
        print("  保留 %-24s %s" % (name[:24], why[:64]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
