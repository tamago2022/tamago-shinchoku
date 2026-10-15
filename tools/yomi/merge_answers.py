# -*- coding: utf-8 -*-
"""外部AI（ChatGPT/Codex と Gemini/Jules）の答えを突き合わせる。
   ・2社が一致したもの → manual.json に採用（次回のビルドから自動で効く）
   ・割れたもの／片方しか答えていないもの → out/yomi-final-check.json（ここだけ人が見る）
   使い方: python3 merge_answers.py --answers out/answers --out out
"""
import json, os, sys, re, glob

KATA = re.compile(r'^[゠-ヿーー・]+$')
HERE = os.path.dirname(os.path.abspath(__file__))

def key(v):
    return re.sub(r'[・ー\s]', '', v or '')

def main():
    a = sys.argv
    adir = a[a.index("--answers") + 1] if "--answers" in a else "out/answers"
    out = a[a.index("--out") + 1] if "--out" in a else "out"

    answers = {}
    for p in sorted(glob.glob(os.path.join(adir, "*.json"))):
        who = os.path.splitext(os.path.basename(p))[0]
        try:
            answers[who] = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print("読めなかった:", p, e)

    if len(answers) < 2:
        print("答えが %d 社ぶんしかありません。2社そろうまで採用しません。" % len(answers))

    manual_path = os.path.join(HERE, "manual.json")
    manual = json.load(open(manual_path, encoding="utf-8")) if os.path.exists(manual_path) else {}

    names = set()
    for d in answers.values():
        names |= set(d.keys())

    adopted, split = {}, []
    for n in sorted(names):
        vals = {w: (d.get(n) or "").strip() for w, d in answers.items()}
        filled = {w: v for w, v in vals.items() if v and KATA.match(v)}
        if len(filled) >= 2 and len({key(v) for v in filled.values()}) == 1:
            adopted[n] = sorted(filled.values(), key=len)[-1]   # 中黒つきの長い方を採る
        elif filled:
            split.append({"name": n, "answers": vals,
                          "why": "2社の答えが割れている" if len(filled) >= 2 else "1社しか答えていない"})

    manual.update(adopted)
    json.dump(manual, open(manual_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    json.dump(split, open(os.path.join(out, "yomi-final-check.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({"答えた社数": len(answers), "一致して採用": len(adopted),
                      "人が最後に見る": len(split)}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
