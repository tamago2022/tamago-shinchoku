#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1055番：門0の証拠を数え、おかしいものを機械で落とす。

★数えるだけ。直さない。落ちたものは一覧に出す。
"""
import io, json, os, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHO = os.path.join(REPO, "status", "shiire_shoko")


def main():
    rows, warn = [], []
    for f in sorted(os.listdir(SHO)):
        if not f.endswith(".json") or f.startswith("_"):
            continue
        d = json.loads(io.open(os.path.join(SHO, f), encoding="utf-8").read())
        sho = d.get("shoko") or []
        urls = [s.get("url") for s in sho if s.get("url")]
        k = d.get("kokishiki") or {}
        rows.append({"slug": d["slug"], "name": d["name"], "hantei": d["hantei"],
                     "kuni": (d.get("honnin") or {}).get("kuni"),
                     "shokoKensu": len(urls),
                     "kokishikiYoutube": bool(k.get("youtube")),
                     "kokaiDouga": bool(k.get("kokaiDouga"))})
        if d["hantei"] not in ("本人確定", "保留"):
            warn.append("%s：判定が『本人確定／保留』以外（%s）" % (f, d["hantei"]))
        if not urls:
            warn.append("%s：証拠のURLが1つも無い（門0を通っていない）" % f)
        for u in urls:
            if not u.startswith("http"):
                warn.append("%s：URLになっていない（%s）" % (f, u))
    out = {
        "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kensu": len(rows),
        "honninKakutei": sum(1 for r in rows if r["hantei"] == "本人確定"),
        "horyuu": sum(1 for r in rows if r["hantei"] == "保留"),
        "kokishikiYoutubeAri": sum(1 for r in rows if r["kokishikiYoutube"]),
        "kokaiDougaAri": sum(1 for r in rows if r["kokaiDouga"]),
        "ochita": warn,
        "rows": rows,
    }
    io.open(os.path.join(SHO, "_index.json"), "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("件数 %d／本人確定 %d／保留 %d／公式YouTubeあり %d／公式動画あり %d"
          % (out["kensu"], out["honninKakutei"], out["horyuu"],
             out["kokishikiYoutubeAri"], out["kokaiDougaAri"]))
    if warn:
        print("★落ちたもの %d件:" % len(warn))
        for w in warn:
            print("  -", w)
        return 1
    print("★落ちたもの 0件")
    return 0


def selftest():
    """★見本で確かめる。落ちなくなったら関所が壊れている。"""
    f = os.path.join(SHO, "_zzz_mihon_warui.json")
    d = json.loads(io.open(f, encoding="utf-8").read())
    ok = (not (d.get("shoko") or [])) and d.get("hantei") == "本人確定"
    print("見本（証拠なし・本人確定）を落とせるか：%s" % ("はい" if ok else "★いいえ＝関所が壊れている"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
