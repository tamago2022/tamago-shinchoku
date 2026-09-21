#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周辺を掘る — 1本入れたら、その周りが勝手に集まる。

たまごさん（2026-09-22）:
  「今さ、外部から『オチケン・ジェネシス』（OTYKEN - GENESIS）っていうのを入れたのね。
   俺はここら辺のジャンルとか全然知らなくて、こういうサウンドも知らないだけで
   多分たくさんあるはずなんだよね。だから自分が音楽を入れたら、その周辺のヒット曲や、
   このアーティストだけじゃなくて似たような影響・同ポジションのグループやアーティストを
   探して、仕入れ候補にしておいてほしいんだよね。
   （まだ棚には入れないで、仕入れ候補として持っておいてほしい）」

■ この道具がやらないこと（ここが一番大事）
  ★**棚に入れない。**書き込むのは status/shiire_kouho/ だけ。
    coverGuide.ts にも status/nyuka/ にも触らない。採否は後で人が決める。
  ★**名前が似ているだけで繋がない。**同定はMusicBrainzのMBID（＋あればISNI）で取る。
    （akikoの棚に矢野顕子を入れた前科。skill sekisho-artist-song）
  ★**裏が取れないことを推測で埋めない。**理由には必ず出典URLを持たせ、
    取れなかったものは notYetChecked に「取れない」と書いて残す。
    （skill sekisho-jijitsu-shutten）

■ 掘る先（0円だけ。鍵の要るものは使わない）
  1. MusicBrainz ws/2 …… 同定（MBID/ISNI）・タグ・地域。鍵不要。
  2. Last.fm の +similar ページ …… 隣に誰がいるか。**APIキーは使わない**。
     公開HTMLを読むだけ。1件ごとに間を空ける。
  3. Wikipedia …… 同じアーティストの他の曲・影響・レーベル。

  ★Spotify の「関連アーティスト」は使わない。
    公式リファレンス get-an-artists-related-artists は **Deprecated** と表示されている
    （2026-09-22 実見）。「昔は使えた」は証拠にならないので、依存させない。
    https://developer.spotify.com/documentation/web-api/reference/get-an-artists-related-artists

■ 英語圏に偏らせない
  Last.fm の「似ている」は聴き手の多い国へ流れる（OTYKENの隣は北欧ばかりになる）。
  そこで **アジアのアンカー**（下の ASIA_ANCHORS）を必ず1本以上通し、
  アジア側の隣人も同じ回で取る。アジアの候補が0件で終わった回は「偏った」として記録する。

■ 数える
  走った回数と、候補が増えた件数の**両方**を status/shiire_kouho/_run.json に書く。
  ★「走った>0 なのに 候補0」は赤。--report がそれを赤で出す。
"""

import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "status", "shiire_kouho")
RUN_JSON = os.path.join(OUT_DIR, "_run.json")
SEEN_JSON = os.path.join(OUT_DIR, "_seen.json")

UA = "tamago-shotengai/1.0 (https://github.com/tamago2022; shuhen_horu.py)"
MB = "https://musicbrainz.org/ws/2"

# アジアに必ず寄り道するための入口。ここを通ることで、
# 英語圏の「似ている」だけで終わらないようにする。
# 2026-09-22 追加：ABAO（阿爆／阿仍仍）。台湾・パイワン族。
#   前回（初回）の実測で**台湾の同ポジションが1件も出てこなかった**ため、入口を1本足した。
#   裏：第31回金曲奨でアルバム『kinakaian 母親的舌頭』が年度アルバム賞・原住民語アルバム賞、
#       収録曲「Thank You 感謝」が年度楽曲賞で最多3冠（フォーカス台湾 2020-10-13）。
#       https://japan.cna.com.tw/topic/column/202010130001.aspx
#   ★ここに名前を置くのは「Last.fm の隣を取りに行く入口」としてだけ。棚には出さない。
ASIA_ANCHORS = ("Hanggai", "The HU", "LEENALCHI", "Minyo Crusaders", "ABAO")

# ---- 2026-09-22 追加：掘り方をもう1本（隣に頼らない道）----
# なぜ足したか（実測）：初回の28件に**台湾が0件**だった。
#   原因は道が1本しか無かったこと。Last.fm の「似ている」は聴き手の数で決まるので、
#   聴き手の少ない言語圏は、いくらアンカーを足しても隣に並ばない。
#   ＝アンカーを増やすだけでは構造的に届かない。**別の原理の道**が要る。
# 足した道：MusicBrainz の「土地 × タグ」検索。
#   誰かに似ているかどうかを一切見ない。「その土地で、その手触りに札が付いている人」を直接引く。
#   鍵不要・0円。Spotifyの関連アーティスト(Deprecated)には触らない。
# たまごさんの指示：中国・韓国・台湾は必ず含める。だから MUST に置いて毎回通す。
AREA_MUST = ("Taiwan", "China", "South Korea")
# 土地側で引くときの札。OTYKENの位置＝「その土地の言葉・伝統の歌い方 × いまの音」。
# ★2回に分けて引く。理由は実測（2026-09-22 07:50・台湾で初回を走らせた結果）：
#   広い札を一度に投げたら、返ってきたのは 鄧麗君・蔡琴・羅大佑 だった。
#   全員たしかに台湾で、たしかに "folk" の札が付いている。**でも位置が違う。**
#   向こうの "folk" は「campus folk（校園民歌）」＝1970年代の学生フォークにも付く札で、
#   OTYKEN の位置（その土地の言葉・伝統の歌い方 × いまの音）とは別物だった。
#   ＝広い札で引くと、土地は合っているのに**位置がずれたものが上位を埋める。**
#   だから「その土地の言葉・先住の歌」を名指しする狭い札を**先に**通し、
#   0件のときだけ広い札へ落ちる。どちらで取れたかは候補に必ず書き残す。
AREA_TAGS_NARROW = ("indigenous", "aboriginal", "throat singing",
                    "ethnic", "world music")
AREA_TAGS_WIDE = ("indigenous", "aboriginal", "folk", "world music",
                  "traditional", "ethnic", "throat singing")
AREA_TAGS = AREA_TAGS_NARROW

# ---- 3本目：民族・言語の名前で引く（2026-09-22）----
# なぜ要るか（実測 2026-09-22 07:53）：
#   狭い札（indigenous / aboriginal）で台湾を引いたら**0件**だった。
#   中国は同じ札で 杭盖乐队（Hanggai・内モンゴル）が一発で出た。
#   ＝向こうの札付けの厚さが土地によって違う。**台湾には「先住」の札がほとんど無い。**
#   札が無いものは、札で引くかぎり永久に出てこない。だから札を使わない道をもう1本足す。
# 足した道：**その土地の民族・言語の名前そのもので引く。**
#   MusicBrainz の検索は名前・別名・注記（disambiguation）にも当たるので、
#   「Paiwan の歌い手」と注記されている人は、札が1つも無くてもここで引っかかる。
# 台湾の16族は原住民族委員会（政府機関）が公認しているもの。
#   https://www.cip.gov.tw/zh-tw/tribe/grid-list/index.html?cumid=8F19BF08AE220D65
#   https://www.tacp.gov.tw/about/sixteen-tribes
# ★ここに並べるのは「検索語」であって、棚に入れる根拠ではない。
#   引っかかった人を本人と確定するのは、今までどおり MBID／ISNI の同定だけ。
AREA_PEOPLES = {
    "Taiwan": ("Paiwan", "Amis", "Bunun", "Atayal", "Puyuma", "Rukai",
               "Tsou", "Saisiyat", "Tao", "Thao", "Kavalan", "Truku",
               "Sakizaya", "Seediq", "aboriginal", "indigenous"),
    "China": ("Mongolian", "Uyghur", "Tibetan", "Yi", "Miao", "Zhuang",
              "throat singing", "indigenous"),
    "South Korea": ("pansori", "minyo", "gugak", "samulnori",
                    "traditional korean", "folk"),
}

# 候補から外す語。**素人カバー・静止画だけの動画・切り抜き**を入口で落とす。
NG_WORDS = (
    "歌ってみた", "弾いてみた", "cover by", "カラオケ", "karaoke",
    "耳コピ", "cover contest", "fan made", "fanmade", "ai cover",
    "切り抜き", "作業用", "1時間耐久", "睡眠用",
)
# Last.fm のバイオにこれが出たら「カバー中心のネット発」とみなして落とす。
NG_BIO = ("make instrumental and vocal covers", "covers on music from",
          "cover of video game")


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json, text/html;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _get_json(url, timeout=25):
    return json.loads(_get(url, timeout))


# ---------------------------------------------------------------------------
# 同定（名前一致で繋がないための唯一の入口）
# ---------------------------------------------------------------------------

def identify(name):
    """MusicBrainz で1組に絞れたときだけ同定済みとして返す。
    絞れなければ None を返す。**推測で1件目を採らない。**"""
    q = urllib.parse.quote(name)
    try:
        j = _get_json("%s/artist?query=%s&fmt=json&limit=5" % (MB, q))
    except Exception as e:
        return None, "MusicBrainzに届きませんでした（%s）" % e
    arts = j.get("artists") or []
    if not arts:
        return None, "MusicBrainzに見つかりません"
    top = arts[0]
    # 2位と点差が無い＝同名が並んでいる。ここで止める（別人事故の入口）。
    if len(arts) > 1 and (top.get("score", 0) - arts[1].get("score", 0)) < 5:
        return None, "同名が並んでいて1組に絞れません（%s ほか）" % arts[1].get("name")
    return {
        "name": top.get("name"),
        "mbid": top.get("id"),
        "isni": (top.get("isnis") or [None])[0],
        "area": ((top.get("area") or {}).get("name")
                 or (top.get("begin-area") or {}).get("name")),
        "type": top.get("type"),
        "began": (top.get("life-span") or {}).get("begin"),
        "disambiguation": top.get("disambiguation"),
        "tags": [t.get("name") for t in (top.get("tags") or [])],
        "src": "%s/artist?query=%s&fmt=json" % (MB, q),
    }, ""


# ---------------------------------------------------------------------------
# 隣を取る（Last.fm の公開ページ。鍵を使わない）
# ---------------------------------------------------------------------------

SIM_BLOCK = re.compile(
    r'<h3[^>]*class="[^"]*artist-similar-artists-sidebar-item-name'
    r'|<h3[^>]*class="[^"]*big-artist-list-title', re.I)
NAME_RE = re.compile(r'/music/([^"/?]+)"', re.I)


def neighbors(name, limit=12):
    """Last.fm の +similar ページから隣のアーティスト名を拾う。
    ★HTMLの形は向こうの都合で変わる。変わったら0件で返し、
      呼び出し側が「取れなかった」として記録する。推測で埋めない。"""
    url = "https://www.last.fm/music/%s/+similar" % urllib.parse.quote(name)
    try:
        html = _get(url)
    except Exception:
        return [], url
    out, seen = [], set()
    for m in re.finditer(r'href="/music/([^"/?]+)"[^>]*>', html):
        raw = urllib.parse.unquote(m.group(1)).replace("+", " ")
        if raw.lower() == name.lower() or raw in seen:
            continue
        if len(raw) < 2 or raw.startswith("_"):
            continue
        seen.add(raw)
        out.append(raw)
        if len(out) >= limit:
            break
    return out, url


def looks_amateur(text):
    low = (text or "").lower()
    return any(w in low for w in NG_WORDS) or any(w in low for w in NG_BIO)


# ---------------------------------------------------------------------------
# 土地から引く（隣に頼らない2本目の道・2026-09-22）
# ---------------------------------------------------------------------------

def area_dig(area, tags=AREA_TAGS, limit=12):
    """MusicBrainz を「土地 × 札」で引く。誰かに似ているかは見ない。

    返すのは (候補のリスト, 使ったURL, 取れなかった理由)。
    ★0件なら0件と返す。**推測で埋めない。**向こうの札付けが薄い土地では
      本当に0件になるので、それは「札が薄い」という事実として上へ返す。
    """
    q = 'area:"%s" AND (%s)' % (
        area, " OR ".join('tag:"%s"' % t for t in tags))
    url = "%s/artist?query=%s&fmt=json&limit=%d" % (
        MB, urllib.parse.quote(q), limit)
    try:
        j = _get_json(url)
    except Exception as e:
        return [], url, "MusicBrainzに届きませんでした（%s）" % e
    out = []
    for a in (j.get("artists") or []):
        # 同定は済んでいる（MBIDで引いた本人そのもの）＝名前一致ではない。
        name = a.get("name") or ""
        if not name or looks_amateur(name):
            continue
        got_area = ((a.get("area") or {}).get("name")
                    or (a.get("begin-area") or {}).get("name") or "")
        # ★土地で引いたのに土地が違うものが混じることがある（検索の点数の都合）。
        #   名前や札で「それっぽいから」と拾わない。土地が一致したものだけ通す。
        if got_area and area.lower() not in got_area.lower():
            continue
        out.append({
            "name": name, "mbid": a.get("id"),
            "isni": (a.get("isnis") or [None])[0],
            "area": got_area or area,
            "type": a.get("type"),
            "began": (a.get("life-span") or {}).get("begin"),
            "disambiguation": a.get("disambiguation"),
            "tags": [t.get("name") for t in (a.get("tags") or [])],
            "src": url,
        })
    return out, url, ""


def people_dig(area, limit=12):
    """民族・言語の名前で引く（札に頼らない3本目）。
    札が1つも付いていなくても、注記に「Paiwan の歌い手」とあれば引っかかる。"""
    words = AREA_PEOPLES.get(area)
    if not words:
        return [], "", "この土地の民族・言語の名前を持っていません"
    q = 'area:"%s" AND (%s)' % (area, " OR ".join('"%s"' % w for w in words))
    url = "%s/artist?query=%s&fmt=json&limit=%d" % (
        MB, urllib.parse.quote(q), limit)
    try:
        j = _get_json(url)
    except Exception as e:
        return [], url, "MusicBrainzに届きませんでした（%s）" % e
    out = []
    for a in (j.get("artists") or []):
        name = a.get("name") or ""
        if not name or looks_amateur(name):
            continue
        got_area = ((a.get("area") or {}).get("name")
                    or (a.get("begin-area") or {}).get("name") or "")
        if got_area and area.lower() not in got_area.lower():
            continue
        blob = "%s %s %s" % (name, a.get("disambiguation") or "",
                             " ".join(t.get("name") or ""
                                      for t in (a.get("tags") or [])))
        # ★ここが肝。土地が合っているだけでは通さない。
        #   **民族・言語の名前が本当に本文に出ているものだけ**通す。
        #   これを外すと、前回の 鄧麗君・蔡琴 と同じ「土地は合うが位置が違う」に戻る。
        hit = [w for w in words if w.lower() in blob.lower()]
        if not hit:
            continue
        # ★MusicBrainz の「まとめ枠」を落とす（実測 2026-09-22 07:56）。
        #   民族名で引いたら Atayal Tribe / Paiwan Tribe / Kavalan People が並んだ。
        #   これは**その民族の録音をまとめて置くための枠**で（注記に catch-all とある）、
        #   実在の歌い手でも団体でもない。ここを通すと「曲を入れられない名前」が候補に混ざる。
        dis = (a.get("disambiguation") or "").lower()
        if "catch-all" in dis or "catchall" in dis:
            continue
        if re.search(r"\b(Tribe|People|Peoples)$", name):
            continue
        out.append({
            "name": name, "mbid": a.get("id"),
            "isni": (a.get("isnis") or [None])[0],
            "area": got_area or area, "type": a.get("type"),
            "began": (a.get("life-span") or {}).get("begin"),
            "disambiguation": a.get("disambiguation"),
            "tags": [t.get("name") for t in (a.get("tags") or [])],
            "hit": hit, "src": url,
        })
    return out, url, ""


def area_dig2(area, limit=12):
    """3段で引く。狭い札 → 民族・言語の名前 → 広い札。
    返り：(候補, 使ったURL, 取れなかった理由, どれで取れたか)
    ★「広いほうで取れた」ことを隠さない。位置がずれている可能性の印として残す。"""
    rows, url, why = area_dig(area, AREA_TAGS_NARROW, limit)
    if rows:
        return rows, url, "", "狭い札（先住・その土地の歌）"
    time.sleep(1.1)
    rows2, url2, why2 = people_dig(area, limit)
    if rows2:
        return rows2, url2, "", "民族・言語の名前（札に頼らない道）"
    time.sleep(1.1)
    rows3, url3, why3 = area_dig(area, AREA_TAGS_WIDE, limit)
    if rows3:
        return rows3, url3, "", "広い札（★位置がずれている可能性あり。人が見る）"
    return [], url3, (why or why2 or why3 or "3つとも0件"), "取れず"


# ---------------------------------------------------------------------------
# 1本掘る
# ---------------------------------------------------------------------------

def dig(entry_artist, entry_song="", include_asia=True, per=10, sleep=1.1):
    me, why = identify(entry_artist)
    result = {
        "entry": {"artist": entry_artist, "song": entry_song},
        "identified": me, "identifyProblem": why,
        "candidates": [], "rejected": [], "notYetChecked": [],
    }
    if not me:
        result["notYetChecked"].append(
            "入口の同定が取れなかった：%s ／ %s" % (entry_artist, why))

    axes = [(entry_artist, "同ポジション")]
    if include_asia:
        axes += [(a, "同ポジション・アジア") for a in ASIA_ANCHORS]

    got = set()
    for src_name, axis in axes:
        names, page = neighbors(src_name, per)
        time.sleep(sleep)
        if not names:
            result["notYetChecked"].append(
                "隣が取れなかった（ページの形が変わった可能性）：%s" % page)
            continue
        for n in names:
            if n in got:
                continue
            got.add(n)
            if looks_amateur(n):
                result["rejected"].append(
                    {"name": n, "why": "素人カバー・切り抜きの語がある", "src": page})
                continue
            ident, iwhy = identify(n)
            time.sleep(sleep)
            if not ident:
                result["notYetChecked"].append(
                    "同定が取れない候補：%s（%s）" % (n, iwhy))
                continue
            result["candidates"].append({
                "name": ident["name"], "mbid": ident["mbid"],
                "isni": ident.get("isni"), "area": ident.get("area"),
                "axis": axis,
                "why": "%s の隣に並んでいる（Last.fm の聴かれ方による）" % src_name,
                "from": {"artist": entry_artist, "song": entry_song},
                "tags": ident.get("tags"),
                "src": page, "identitySrc": ident["src"],
                "video": "未確認",
            })
    # ---- 2本目の道：土地から引く（2026-09-22）----
    # 隣（Last.fm）を1件も見ない。たまごさんの指示で 中国・韓国・台湾 は毎回必ず通す。
    if include_asia:
        for area in AREA_MUST:
            rows, url, why, how = area_dig2(area)
            time.sleep(sleep)
            if why:
                result["notYetChecked"].append("土地から引けなかった：%s（%s）" % (area, why))
                continue
            if not rows:
                result["notYetChecked"].append(
                    "土地から引いたが0件：%s（向こうの札付けが薄い。"
                    "別の札か別の道が要る）／ %s" % (area, url))
                continue
            for r in rows:
                key = (r.get("mbid") or r["name"])
                if key in got:
                    continue
                got.add(key)
                result["candidates"].append({
                    "name": r["name"], "mbid": r.get("mbid"),
                    "isni": r.get("isni"), "area": r.get("area"),
                    "axis": "同ポジション・アジア（土地から）",
                    "why": "%s の土地から直接引いた（%s）。誰かに似ているかは"
                           "一切見ていない。札：%s"
                           % (area, how, "・".join(r.get("tags") or []) or "無し"),
                    "from": {"artist": entry_artist, "song": entry_song},
                    "tags": r.get("tags"), "src": url, "identitySrc": url,
                    "video": "未確認",
                })

    asia = [c for c in result["candidates"] if "アジア" in c["axis"]]
    if include_asia and not asia:
        result["notYetChecked"].append(
            "アジアの候補が0件で終わった。英語圏に偏った回として記録する。")
    # ★たまごさんの指示（中国・韓国・台湾は必ず含める）が実際に果たせたかを、毎回数える。
    for area in (AREA_MUST if include_asia else ()):
        n = sum(1 for c in result["candidates"]
                if area.lower() in (c.get("area") or "").lower())
        if n == 0:
            result["notYetChecked"].append(
                "★%s が0件のまま終わった回。指示は「必ず含める」なので、"
                "これは満たせていない。" % area)
    return result


# ---------------------------------------------------------------------------
# 入荷を検知して勝手に走る
# ---------------------------------------------------------------------------

def _load(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _merge_save(path, res):
    """★上書きしない。前に居た候補を必ず残してから書く。

    なぜ要るか（2026-09-22 08:00 実害）：
      この道具を掘り直したとき、前の回に**人が出典付きで書いた28件**が
      まるごと消えた。status/ はgitが見ていないので、履歴からも戻せなかった
      （公開済みのHTMLから拾い直して復旧した）。
      「掘るたびに前の仕事が消える」道具は、走れば走るほど損をする。
    合わせ方：MBIDがあればMBID、無ければ名前で1件と見る。
      **先に居たほうを残す。**手書きの note/fact を機械の一行で上書きしない。
    """
    old = _load(path, {})
    def key(c):
        return (c.get("mbid") or re.sub(r"[^0-9a-z぀-鿿]", "",
                                        (c.get("name") or "").lower())[:20])
    seen, merged = {}, []
    for c in (old.get("candidates") or []) + (res.get("candidates") or []):
        k = key(c)
        if k in seen:
            if c.get("mbid") and not seen[k].get("mbid"):
                seen[k]["mbid"] = c["mbid"]
            continue
        seen[k] = dict(c)
        merged.append(seen[k])
    for i, c in enumerate(merged):
        c["n"] = i + 1
    out = dict(old)
    out.update({k: v for k, v in res.items() if k != "candidates"})
    out["candidates"] = merged
    if old.get("entry") and not res.get("entry"):
        out["entry"] = old["entry"]      # 入口の手書きを消さない
    out["kept"] = len(old.get("candidates") or [])
    out["addedThisRun"] = len(merged) - len(old.get("candidates") or [])
    _save(path, out)
    return out["addedThisRun"]


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(obj, ensure_ascii=False, indent=1))


def watch(max_new=2):
    """status/nyuka/ に積まれた入荷票のうち、まだ掘っていないものを掘る。
    ★言われてから動くのではなく、入荷が置かれた側から気づいて動く。"""
    seen = set(_load(SEEN_JSON, {"artists": []})["artists"])
    todo = []
    for sub in ("pending", "done"):
        d = os.path.join(REPO, "status", "nyuka", sub)
        for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not fn.endswith(".json"):
                continue
            it = _load(os.path.join(d, fn), {})
            a = (it.get("artist") or "").strip()
            if a and a not in seen and a not in [t[0] for t in todo]:
                todo.append((a, it.get("title") or ""))
    run = _load(RUN_JSON, {"runs": 0, "candidates": 0, "history": []})
    added = 0
    for artist, song in todo[:max_new]:
        res = dig(artist, song)
        slug = re.sub(r"[^a-z0-9]+", "-", artist.lower()).strip("-") or "unknown"
        _merge_save(os.path.join(OUT_DIR, "%s.json" % slug), res)
        added += len(res["candidates"])
        seen.add(artist)
    run["runs"] += 1
    run["candidates"] += added
    run["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "dug": len(todo[:max_new]), "added": added})
    run["history"] = run["history"][-50:]
    _save(RUN_JSON, run)
    _save(SEEN_JSON, {"artists": sorted(seen)})
    return added, len(todo[:max_new])


def report():
    run = _load(RUN_JSON, {"runs": 0, "candidates": 0, "history": []})
    files = [f for f in (os.listdir(OUT_DIR) if os.path.isdir(OUT_DIR) else [])
             if f.endswith(".json") and not f.startswith("_")]
    total = 0
    for f in files:
        total += len(_load(os.path.join(OUT_DIR, f), {}).get("candidates") or [])
    print("走った回数: %d ／ 溜まっている候補: %d件（%d本の入口）"
          % (run["runs"], total, len(files)))
    if run["runs"] > 0 and total == 0:
        print("★赤：走っているのに候補が0件。掘る先の形が変わった可能性がある。")
        return 1
    return 0


# ---------------------------------------------------------------------------
# 工場側の代行係から呼ばれる口（2026-09-22）
# ---------------------------------------------------------------------------

def run_job(payload):
    """tools/gaibu_runner.py が kind="horu" のときに呼ぶ。

    なぜ要るか（実測 2026-09-22 07:41）：
      Cowork/Dispatch のサンドボックスからは musicbrainz.org にも last.fm にも
      **回線が出ない**（プロキシが CONNECT に 403 を返す）。このMacからは出る。
      ＝向こうは「どこを掘るか」の票を置くだけ、掘るのはこちら、という形にする。

    payload:
      mode    … "artist"（入口から掘る）／"area"（土地から引くだけ）／"watch"
      artist  … mode=artist のときの入口
      song    … 任意
      areas   … mode=area のときの土地。省略なら AREA_MUST（中国・韓国・台湾）

    ★金は一切かからない（鍵の要る先を1つも叩かない）。
    ★棚には書かない。書き先は status/shiire_kouho/ だけ。
    """
    mode = (payload or {}).get("mode") or "artist"
    if mode == "area":
        areas = (payload or {}).get("areas") or list(AREA_MUST)
        found, miss, hows = {}, [], {}
        for a in areas:
            rows, url, why, how = area_dig2(a)
            hows[a] = how
            if why:
                miss.append("%s：%s" % (a, why))
            elif not rows:
                miss.append("%s：0件（札が薄い）／%s" % (a, url))
            found[a] = rows
            time.sleep(1.1)
        return {"ok": any(found.values()), "mode": "area", "found": found,
                "howTaken": hows, "notYetChecked": miss, "totalYen": 0.0}
    if mode == "watch":
        added, dug = watch()
        return {"ok": True, "mode": "watch", "dug": dug, "added": added,
                "totalYen": 0.0}
    artist = (payload or {}).get("artist") or ""
    if not artist:
        return {"ok": False, "error": "入口のアーティスト名が空です", "totalYen": 0.0}
    res = dig(artist, (payload or {}).get("song") or "")
    slug = re.sub(r"[^a-z0-9]+", "-", artist.lower()).strip("-") or "unknown"
    _merge_save(os.path.join(OUT_DIR, "%s.json" % slug), res)
    run = _load(RUN_JSON, {"runs": 0, "candidates": 0, "history": []})
    run["runs"] += 1
    run["candidates"] += len(res["candidates"])
    run["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "dug": 1, "added": len(res["candidates"]),
                           "via": "工場の代行係"})
    run["history"] = run["history"][-50:]
    _save(RUN_JSON, run)
    return {"ok": True, "mode": "artist", "artist": artist,
            "added": len(res["candidates"]),
            "asia": sum(1 for c in res["candidates"] if "アジア" in c["axis"]),
            "savedTo": "status/shiire_kouho/%s.json" % slug,
            "notYetChecked": res["notYetChecked"], "totalYen": 0.0}


def main():
    args = sys.argv[1:]
    if "--report" in args:
        return report()
    if "--artist" in args:
        i = args.index("--artist")
        artist = args[i + 1]
        song = args[args.index("--song") + 1] if "--song" in args else ""
        res = dig(artist, song)
        slug = re.sub(r"[^a-z0-9]+", "-", artist.lower()).strip("-")
        _merge_save(os.path.join(OUT_DIR, "%s.json" % slug), res)
        print("%s：候補 %d件／同定できず %d件"
              % (artist, len(res["candidates"]), len(res["notYetChecked"])))
        return 0
    if "--area" in args:
        # 2本目の道だけを単体で試す（台湾が本当に出るのかを、その場で見るため）
        i = args.index("--area")
        areas = [args[i + 1]] if len(args) > i + 1 and not args[i + 1].startswith("--") \
            else list(AREA_MUST)
        rc = 0
        for a in areas:
            rows, url, why, how = area_dig2(a)
            print("── %s ──（%s） %s" % (a, how, why or "%d件" % len(rows)))
            print("   %s" % url)
            for r in rows:
                print("   ・%s ／ %s ／ 札:%s ／ %s"
                      % (r["name"], r.get("area"),
                         "・".join(r.get("tags") or []) or "無し", r.get("mbid")))
            if not rows:
                rc = 1
            time.sleep(1.1)
        return rc
    if "--watch" in args:
        added, dug = watch()
        if not ("--quiet" in args):
            print("掘った入口 %d本／候補 %d件" % (dug, added))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
