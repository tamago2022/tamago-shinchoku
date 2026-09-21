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
ASIA_ANCHORS = ("Hanggai", "The HU", "LEENALCHI", "Minyo Crusaders")

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
    asia = [c for c in result["candidates"] if c["axis"].endswith("アジア")]
    if include_asia and not asia:
        result["notYetChecked"].append(
            "アジアの候補が0件で終わった。英語圏に偏った回として記録する。")
    return result


# ---------------------------------------------------------------------------
# 入荷を検知して勝手に走る
# ---------------------------------------------------------------------------

def _load(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


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
        _save(os.path.join(OUT_DIR, "%s.json" % slug), res)
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
        _save(os.path.join(OUT_DIR, "%s.json" % slug), res)
        print("%s：候補 %d件／同定できず %d件"
              % (artist, len(res["candidates"]), len(res["notYetChecked"])))
        return 0
    if "--watch" in args:
        added, dug = watch()
        if not ("--quiet" in args):
            print("掘った入口 %d本／候補 %d件" % (dug, added))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
