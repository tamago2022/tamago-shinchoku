# -*- coding: utf-8 -*-
"""1051番【保留を機械で三つに割る】関所の保留2230件を、動画を上げたチャンネル名で判定する。

判定（人の目を使わない。全部この規則だけ）:
  白  … 動画を上げたチャンネルが**棚の本人**だった。＝関所の誤検知。棚に残す。
  黒  … チャンネルが**別人**（関所が名指しした相手、または別の棚の持ち主）で、
        かつ棚の本人の名前がチャンネルに一切入っていない。＝別人混入の疑いが濃い。
  保留… それ以外（レーベル・コンピ・個人のアップ・動画が消えている）。
        ★判定できないものは触らない。一覧に残すだけ。

★ここでは1件もファイルを書き換えない。消さない。並べるだけ。
"""
import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from parse_coverguide import parse  # noqa: E402

MIN = 4
# ★飾りは「末尾についた本人印」だけ落とす。
#   実測 2026-09-24：records / channel / music まで落とすと
#   「Sony Music (Japan)」→sony、「Rainbow Channel」→rainbow、「Stax Records」→stax
#   になり、松田聖子のソニー公式MVや資生堂の社歌が「別人」に化けた。★落としすぎが事故を生む。
HONNIN_JIRUSHI = re.compile(
    r"(\s*[-–—]\s*topic|vevo|\s*official(\s*channel)?|\s*公式(チャンネル)?)\s*$", re.I)
PAREN = re.compile(r"[（(\[].*?[)）\]]")
# 共演の印。これが曲名にあるなら「客演かもしれない」＝黒にしない。
KYAKUEN = re.compile(r"feat\.?|ft\.?|\bwith\b|&|＆|×|\bx\b|duet|vs\.?", re.I)
# ★「本人の名前が曲名から抜かれた跡」。
#   実測 2026-09-24：棚に入っている曲名は、棚の本人の名前だけ消してある。
#   だから「, Lady Gaga - It's De-Lovely」（トニー・ベネットの棚）は、
#   元が「Tony Bennett, Lady Gaga - ...」＝**本人が連名で演っている**。
#   この跡を読まずに黒にすると、本物の共演盤を別人扱いして外してしまう。
NUKETA_ATO = re.compile(
    r"^\s*[,、，/／・&＆-]|[,、，/／]\s*[-–—]|[,、，/／&＆]\s*$|[-–—]\s*$|"
    r"[（(\[]\s*(feat\.?|ft\.?|with|&)?\s*[)）\]]|(feat\.?|ft\.?|with)\s*[)）\]]", re.I)


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if not unicodedata.combining(c))
    return re.sub(r"[\s'\"’“”・.,\-_/()\[\]!&+]+", "", s)


def ch_core(s):
    """チャンネル名の芯。『○○ - Topic』『○○VEVO』『○○ Official』だけ同じにする。"""
    s = s or ""
    for _ in range(3):
        s2 = HONNIN_JIRUSHI.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    return norm(PAREN.sub("", s))


def chikai(a, b):
    """綴り違いの同じ人か（1文字ちがいまで）。Mark Martel と Marc Martel を別人にしない。"""
    if not a or not b or abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 5:
        return False
    if a == b:
        return True
    # 1文字の入替・追加・削除だけ許す
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    lo, hi = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(hi)):
        if hi[:i] + hi[i + 1:] == lo:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", default="status/_1039/src_lib_coverGuide.ts")
    ap.add_argument("--hold", default="status/_1051/hold_map.json")
    ap.add_argument("--ch", default="status/_1051/yt_channels.json")
    ap.add_argument("--out", default="status/_1051/hantei.json")
    a = ap.parse_args()
    p = lambda x: x if os.path.isabs(x) else os.path.join(REPO, x)

    artists = parse(p(a.ts))
    # 名前（芯）→ 棚id。別の棚の持ち主を当てるのに使う。
    owner = {}
    for ar in artists:
        for nm in [ar["name"]] + ar.get("aliases", []):
            n = norm(PAREN.sub("", nm))
            if len(n) >= MIN:
                owner.setdefault(n, set()).add(ar["id"])
    self_names = {}
    for ar in artists:
        self_names[ar["id"]] = {norm(PAREN.sub("", x))
                                for x in [ar["name"]] + ar.get("aliases", [])
                                if len(norm(PAREN.sub("", x))) >= MIN}

    hold = json.load(open(p(a.hold), encoding="utf-8"))
    chmap = json.load(open(p(a.ch), encoding="utf-8")) if os.path.exists(p(a.ch)) else {}

    shiro, kuro, nokori = [], [], []
    for h in hold:
        vid = h.get("youtubeId") or ""
        info = chmap.get(vid) or {}
        ct = info.get("channelTitle") or ""
        rec = dict(h, channelTitle=ct, channelId=info.get("channelId") or "")
        if not vid:
            rec["riyu"] = "動画idが取れない"
            nokori.append(rec)
            continue
        if not ct:
            rec["riyu"] = "動画が消えている／非公開（チャンネルが取れない）"
            nokori.append(rec)
            continue

        core = ch_core(ct)
        mine = self_names.get(h["artist_id"], set())
        # 白：チャンネルの芯に棚の本人の名前が入っている（逆も見る／綴り1文字違いも同じ人）
        if any(m and (m in core or core in m or chikai(m, core)) for m in mine):
            rec["riyu"] = "上げたチャンネルが棚の本人（%s）＝関所の誤検知" % ct
            shiro.append(rec)
            continue
        # 黒：チャンネルの芯が別の棚の持ち主そのもの
        hit = set()
        for n, ids in owner.items():
            if n == core:
                hit |= {i for i in ids if i != h["artist_id"]}
        # 関所が名指しした相手なら、なお濃い
        yubisashi = set(h.get("other_ids") or [])
        if hit:
            # ★曲名に共演の印／名前が抜かれた跡があるなら、本人が連名で演っているかもしれない。黒にしない。
            ttl = h.get("title") or ""
            # ★曲名の「演者の位置」（最初の - より左）に本人の名前が残っているなら連名。
            #   「Eric Clapton / Jeff Beck - Moon River」はジェフ・ベックの棚でよい。
            #   逆に「Anthony Hamilton - Pillows」は、pillows が題名の側なので連名ではない。
            enja = re.split(r"\s[-–—]\s", ttl, 1)[0] if re.search(r"\s[-–—]\s", ttl) else ""
            renmei = any(m and m in norm(enja) for m in mine) if enja else False
            if renmei or KYAKUEN.search(ttl) or NUKETA_ATO.search(ttl):
                rec["riyu"] = ("上げたのは別人（%s）だが、曲名に共演の印／本人の名前が抜かれた跡がある＝"
                               "本人が連名で演っている可能性。人が見るまで動かさない" % ct)
                rec["chigau_ids"] = sorted(hit)
                nokori.append(rec)
                continue
            rec["riyu"] = ("上げたチャンネルが別人（%s）。棚の本人の名前はチャンネルに無い%s"
                           % (ct, "／関所が名指しした相手と一致" if (hit & yubisashi) else ""))
            rec["chigau_ids"] = sorted(hit)
            kuro.append(rec)
            continue
        rec["riyu"] = "チャンネル『%s』は本人でも棚の持ち主でもない（レーベル／コンピ／個人）" % ct
        nokori.append(rec)

    out = {"shiro": shiro, "kuro": kuro, "hoshu": nokori,
           "kazu": {"shiro": len(shiro), "kuro": len(kuro), "hoshu": len(nokori),
                    "zenbu": len(hold)}}
    json.dump(out, open(p(a.out), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("白（誤検知・棚に残す）%d ／ 黒（別人の疑いが濃い）%d ／ 保留 %d ／ 合計 %d"
          % (len(shiro), len(kuro), len(nokori), len(hold)))
    print("書いた: %s" % p(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
