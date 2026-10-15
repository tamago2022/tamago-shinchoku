#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1026番：**もう書いてしまった候補**の出典を、機械で全部見直す。

なぜ要るか：関所を直しても、直す前に書いた候補（status/shiire_kouho/*.json）の
`src` は古い判定のまま。Wikipediaの誤爆記事を出典にしている行が残っていたら、
そこに書いた「事実」は嘘になる（skill sekisho-jijitsu-shutten）。
★1件ずつ目で見ない。全部機械で当たる。
"""
import io, json, os, re, sys, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import shiire_fetch as sf  # noqa: E402

KOUHO = os.path.join(REPO, "status", "shiire_kouho")


def wiki_title_of(url):
    m = re.match(r"https?://([a-z]+)\.wikipedia\.org/wiki/(.+)$", url or "")
    if not m:
        return None, None
    return m.group(1), urllib.parse.unquote(m.group(2)).replace("_", " ")


RAW = os.path.join(REPO, "status", "shiire_raw")


def _raw_text(artist, lang):
    """集めた素材の本文。無ければ None（★無いのに『確かめた』と言わない）。"""
    p = os.path.join(RAW, sf.slug(artist) + ".json")
    if not os.path.exists(p):
        return None
    d = json.loads(io.open(p, encoding="utf-8").read())
    w = d.get("wikipedia_%s" % (lang or "en")) or {}
    return w.get("text") or ""


def main():
    bad, unknown, seen, files = [], [], 0, 0
    for fn in sorted(os.listdir(KOUHO)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        d = json.loads(io.open(os.path.join(KOUHO, fn), encoding="utf-8").read())
        artist = ((d.get("identified") or {}).get("name")
                  or (d.get("entry") or {}).get("artist") or fn[:-5])
        files += 1
        for c in (d.get("candidates") or []):
            for url in re.findall(r"https?://\S+", " ".join(
                    str(c.get(k) or "") for k in ("src", "fact", "why"))):
                u = url.rstrip("）、。,")
                if u.endswith(")") and u.count("(") < u.count(")"):
                    u = u[:-1]          # 文末の閉じ括弧だけ落とす（'Kneecap_(band)' を壊さない）
                lang, title = wiki_title_of(u)
                if not title:
                    continue
                seen += 1
                # 本文は手元に無いので、題だけで当たれるところまで当たる
                ok_name, why = sf.name_matches(artist, title, "")
                kind, why_k = sf.article_kind(title, "")
                if kind == "work":
                    bad.append((fn, artist, c.get("name", "")[:40], title, why_k))
                elif not ok_name:
                    # 題が別の文字体系のときは、題だけでは判らない（例：平沢進→Susumu Hirasawa）。
                    # ★ここで「別物」と断じない。素材の本文で当たり直す。
                    core = sf.title_core(title)
                    if sf._is_latin(artist) != sf._is_latin(core):
                        txt = _raw_text(artist, lang)
                        if txt is None:
                            unknown.append((artist, title, "素材が無いので確かめられない"))
                            continue
                        ok2, why2 = sf.name_matches(artist, title, txt)
                        if ok2:
                            continue
                        bad.append((fn, artist, c.get("name", "")[:40], title, why2))
                    else:
                        bad.append((fn, artist, c.get("name", "")[:40], title, why))
    print("■ 候補ファイル %d枚／Wikipediaを出典にした行 %d件" % (files, seen))
    print("■ 出典が本人の記事でない疑い：%d件" % len(bad))
    for b in bad:
        print("  %-22s %-34s → %-32s %s" % (b[1][:22], b[2], b[3][:32], b[4][:50]))
    if unknown:
        print("■ 確かめられなかった（素材が手元に無い）：%d件" % len(unknown))
        for u in unknown:
            print("  %-22s → %-32s %s" % (u[0][:22], u[1][:32], u[2]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
