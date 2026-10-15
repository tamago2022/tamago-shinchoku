# -*- coding: utf-8 -*-
"""危ないものだけを外部AIへ投げる「問い」を組み立てる。0円（GitHubのIssueに貼るだけ）。
   出力: out/kaigi-question.md ／ out/kaigi-targets.json
   使い方: python3 make_kaigi.py --out out [--limit 200]
"""
import json, os, sys

def main():
    a = sys.argv
    out = a[a.index("--out") + 1] if "--out" in a else "out"
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 200
    rev = json.load(open(os.path.join(out, "yomi-review.json"), encoding="utf-8"))

    arts = [r for r in rev if r["type"] == "artist"]
    red = [r for r in arts if r["band"] == "red"]
    conflict = [r for r in arts if r["band"] == "yellow"
                and any("割れ" in s for s in r["reasons"])]
    target = (red + conflict)[:limit]

    lines = []
    lines.append("# 名前の読み（カタカナ）を教えてください")
    lines.append("")
    lines.append("「ごきげん補給所」の案内人が声で名前を読み上げます。"
                 "**King Gnu を「キング・ヌー」と英語読みしてしまった**ので、読みを固めています。")
    lines.append("機械（辞書・ローマ字・形態素解析）で "
                 "**大半は自動で埋まりました。ここに出すのは機械が外すものだけ**です。")
    lines.append("")
    lines.append("## お願い")
    lines.append("")
    lines.append("下の表の `yomi` を **全角カタカナだけ**で埋めて、"
                 "**JSONのコードブロックひとつ**で返してください。")
    lines.append("")
    lines.append("- 形式: `{\"名前\": \"カタカナ\", ...}`")
    lines.append("- 区切りは中黒「・」。長音は「ー」。")
    lines.append("- **分からないものは空文字 `\"\"` のままにしてください。"
                 "推測で埋めないでください。**間違いよりも空欄の方が助かります。")
    lines.append("- 日本のアーティストの英字表記（例 King Gnu → キングヌー）は"
                 "**本人・公式の読み**でお願いします。")
    lines.append("")
    lines.append("## 答える人")
    lines.append("")
    lines.append("- ChatGPT(Codex) と Gemini(Jules) の**両方**が、それぞれ別のコメントで答えてください。")
    lines.append("- **2人の答えが割れたものだけ**を人が最後に見ます。合っていればそのまま通します。")
    lines.append("")
    lines.append("## 表")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({r["name"]: "" for r in target},
                            ensure_ascii=False, indent=1))
    lines.append("```")
    lines.append("")
    lines.append("## 機械が今そう読んでいる案（参考。違っていたら直してください）")
    lines.append("")
    lines.append("| 名前 | 機械の案 | なぜ危ないと判断したか |")
    lines.append("|---|---|---|")
    for r in target:
        why = "／".join(r["reasons"])[:90].replace("|", "／")
        lines.append(f"| {r['name'].replace('|','／')} | {r['yomi'] or '（無し）'} | {why} |")
    lines.append("")

    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "kaigi-question.md"), "w", encoding="utf-8").write("\n".join(lines))
    json.dump([r["name"] for r in target],
              open(os.path.join(out, "kaigi-targets.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(json.dumps({"red": len(red), "conflict": len(conflict),
                      "issueに出す": len(target)}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
