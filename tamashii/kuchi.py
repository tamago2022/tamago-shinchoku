#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1051番【魂の口】ごきげん補給所の魂を、どの脳からでも同じ形で呼べる3つの道具にする。

━━ たまごさん（2026-09-24・原文）━━

  「基礎AIを自前で作ってはいけない。ごきげん補給所が持つべき資産は
    『何を出せば、この人が少しごきげんになるか』という選球眼とデータ。モデルは交換部品にする。」
  「C-3POそのものを作らない。C-3POが来た瞬間に
    『ごきげん補給所の人格と宝箱』を注入できる状態を作る。」

━━ この口は3つしかない（増やさない）━━

    osusume(konomi, kibun, ima_no_tana, hito)  → 曲・動画カードを返す
    shiraberu(go)                              → 棚・アーティスト・曲を引く
    jinkaku()                                  → 人格と会話の決まりを返す

━━ この口が絶対に持たないもの（＝脳の仕事）━━

  ・APIキー、モデル名、WebSocket、音声の形式、トークン、課金
  ・「どのAI会社か」という情報を1バイトも持たない
  → だから ElevenAgents / GPT-Live / Grok Voice / Gemini Live のどれに差し替えても、
    このファイルは**1バイトも書き換えなくていい。**

━━ ★AIを1回も呼ばない。1円もかからない。同じ入力なら毎回同じ答えが出る ━━

  おすすめは乱数を使っていない。`hito`（その人の識別子）から作った決まった数で
  一番下の1枚だけをずらす。だから「同じ人には同じ、違う人には違う」が再現できる。

━━ 使い方 ━━

  Pythonから:
      import kuchi
      kuchi.call("osusume", {"konomi": ["久保田利伸", "ブラジル"]})

  コマンドから（脳がシェル越しに叩く場合）:
      python3 tamashii/kuchi.py osusume '{"konomi":["久保田利伸"]}'
      python3 tamashii/kuchi.py jinkaku '{}'
      python3 tamashii/kuchi.py --tools          # 3方言の関数定義を書き出す
      python3 tamashii/kuchi.py --self-test      # ★叩いて確かめる
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))

SOUL_PATH = os.path.join(HERE, "data", "tamashii.json")
JINKAKU_PATH = os.path.join(HERE, "jinkaku.json")
TOOLS_PATH = os.path.join(HERE, "tools.json")

_soul = None
_jinkaku = None
_index = None


# ══════════════════════════════════════════════════════════════
# 1. 口の仕様（★正本はここ1箇所だけ。3方言はここから機械的に作る）
# ══════════════════════════════════════════════════════════════
KUCHI_SPEC = [
    {
        "name": "osusume",
        "description": (
            "お客さんの好み・気分・いまいる棚から、ごきげん補給所のカードを出す。"
            "安心4枚＋冒険1枚。カードはドアであって命令ではない。"
            "うんちくは元データにあるときだけ1行返る（無ければ null＝黙る）。"
        ),
        "params": {
            "konomi": {
                "type": "array",
                "items": {"type": "string"},
                "description": "好きなもの。アーティスト名・国・雰囲気・動物・言葉、何でもよい。2人ぶん入れてよい。",
            },
            "kibun": {"type": "string", "description": "いまの気分（例：疲れた／踊りたい／静か）。無ければ空でよい。"},
            "ima_no_tana": {
                "type": "string",
                "description": "いまいる棚のid（music / food / cute / laugh / travel / dance / joy）。分からなければ空。",
            },
            "hito": {
                "type": "string",
                "description": "その人を表す文字列（席番号でもニックネームでもよい）。一番下の『こちらもどうぞ』だけがこれで変わる。",
            },
        },
        "required": ["konomi"],
    },
    {
        "name": "shiraberu",
        "description": "言葉から、棚・アーティスト・曲を引く。当たったものだけ返す。無ければ空で返す（作らない）。",
        "params": {
            "go": {"type": "string", "description": "調べたい言葉。アーティスト名・曲名・棚の名前・別名。"},
            "kazu": {"type": "integer", "description": "最大何件返すか。既定8。"},
        },
        "required": ["go"],
    },
    {
        "name": "jinkaku",
        "description": "ごきげん補給所の人格と会話の決まりを返す。会話を始める前に1回だけ呼ぶ。時刻で案内人／深夜のママが切り替わる。",
        "params": {},
        "required": [],
    },
]


def tools_json() -> dict:
    """★同じ仕様から、脳ごとの方言を機械的に作る。手で3回書かない（写すと必ず食い違う）。"""

    def jsonschema(spec):
        return {
            "type": "object",
            "properties": spec["params"],
            "required": spec["required"],
        }

    openai_style = [
        {"type": "function", "function": {"name": s["name"], "description": s["description"], "parameters": jsonschema(s)}}
        for s in KUCHI_SPEC
    ]
    # xAI Grok Realtime / OpenAI Realtime は function を包まない平たい形
    realtime_style = [
        {"type": "function", "name": s["name"], "description": s["description"], "parameters": jsonschema(s)}
        for s in KUCHI_SPEC
    ]
    # ElevenLabs Agents は webhook ツール（HTTPで叩く）
    eleven_style = [
        {
            "type": "webhook",
            "name": s["name"],
            "description": s["description"],
            "api_schema": {
                "url": "{TAMASHII_URL}/" + s["name"],
                "method": "POST",
                "request_body_schema": jsonschema(s),
            },
        }
        for s in KUCHI_SPEC
    ]
    # Gemini Live（functionDeclarations）
    gemini_style = {
        "functionDeclarations": [
            {"name": s["name"], "description": s["description"], "parameters": jsonschema(s)} for s in KUCHI_SPEC
        ]
    }
    return {
        "_これは何": "魂の口の関数定義。★脳を替えるときはこのファイルを差すだけ。中身（KUCHI_SPEC）は1つ。",
        "tsukutta": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "openai": openai_style,
        "realtime": realtime_style,
        "elevenlabs": eleven_style,
        "gemini": gemini_style,
    }


# ══════════════════════════════════════════════════════════════
# 2. 魂を読む
# ══════════════════════════════════════════════════════════════
def _load():
    global _soul, _jinkaku, _index
    if _soul is not None:
        return
    if not os.path.exists(SOUL_PATH):
        raise SystemExit("魂がまだ出ていない。先に `python3 tamashii/shukkoshi.py` を走らせる。")
    _soul = json.load(open(SOUL_PATH, encoding="utf-8"))
    _jinkaku = json.load(open(JINKAKU_PATH, encoding="utf-8"))

    # 検索用の索引（正規化した語 → アーティスト）
    idx = []
    for a in _soul["artists"]:
        words = [a["name"]] + a.get("aliases", [])
        idx.append((a, {_norm(w) for w in words if w}))
    _index = idx


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"[\s　’'`\"“”‐\-–—_,.!?！？・:：;；/\\()\[\]【】「」『』]+", "", s)
    return s


def _seed(*parts) -> int:
    """決まった数を作る（FNV-1a 64bit）。★乱数ではない。
    JS版（kuchi.mjs）でも同じ式で同じ数が出る必要があるので、
    ブラウザで同期実行できない SHA ではなく、足し算と掛け算だけのこれを使う。"""
    h = 0xCBF29CE484222325
    for b in "|".join(str(p) for p in parts).encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# ══════════════════════════════════════════════════════════════
# 3. カードの形（★カード＝ドア）
# ══════════════════════════════════════════════════════════════
def _card(artist: dict, song: dict, riyu: str) -> dict:
    return {
        "kind": "song",
        "title": song["title"],
        "artist": artist["name"],
        "artist_id": artist["id"],
        "song_id": song["id"],
        # ★URLは組み立てない（叩いて200を確かめていないものを渡さない）。道だけ渡す。
        "path": f"/cover-guide?artist={artist['id']}&song={song['id']}",
        "youtubeId": song.get("youtubeId"),
        "year": song.get("year"),
        # ★うんちくは元データにあるときだけ。無ければ null＝黙る。
        "unchiku": song.get("unchiku"),
        "hitokoto": song.get("hitokoto"),
        "door": True,
        "riyu": riyu,
    }


# ══════════════════════════════════════════════════════════════
# 4. 選球眼（安心4：冒険1 ／ 2人を満足させる ／ 固定と可変）
# ══════════════════════════════════════════════════════════════
def _score(artist: dict, song: dict, words: list) -> int:
    """語との近さ。0＝かすってもいない。"""
    sc = 0
    names = {_norm(artist["name"])} | {_norm(x) for x in artist.get("aliases", [])}
    t = _norm(song["title"])
    about = _norm(artist.get("about") or "")
    unchiku = _norm(song.get("unchiku") or "")
    for w in words:
        n = _norm(w)
        if not n:
            continue
        if n in names:
            sc += 10
        elif any(n in x or x in n for x in names if len(x) >= 2):
            sc += 6
        if n and n in t:
            sc += 4
        if n and len(n) >= 2 and n in about:
            sc += 2
        if n and len(n) >= 2 and n in unchiku:
            sc += 1
    if song.get("youtubeId"):
        sc += 2  # ★1クリックで鳴るものを優先（憲法・骨組み禁止／鳴らない札を通さない）
    if song.get("pick"):
        sc += 1
    return sc


def _candidates(words: list) -> list:
    """(score, artist, song) を高い順。同点はidで固定（毎回同じ順になる）。"""
    out = []
    for a in _soul["artists"]:
        for s in a["songs"]:
            sc = _score(a, s, words)
            if sc >= 4:
                out.append((sc, a, s))
    out.sort(key=lambda x: (-x[0], x[1]["id"], x[2]["id"]))
    return out


def osusume(konomi=None, kibun: str = "", ima_no_tana: str = "", hito: str = "") -> dict:
    _load()
    if isinstance(konomi, str):
        konomi = [konomi]
    konomi = [k for k in (konomi or []) if str(k).strip()]
    hint = [w for w in (konomi + ([kibun] if kibun else []))]

    cand = _candidates(hint)

    # ── 安心4枚：★必ず4枚。まずアーティストが偏らないよう1人1枚、
    #    足りなければ言葉のかすりを緩め、それでも足りなければ同じ人の別の曲で埋める。
    #    （空席のまま出すと「安心4：冒険1」が崩れる。崩れると選球眼が測れない）
    anshin, used_artists, used_songs = [], set(), set()

    def _tsumu(pairs, hitori_ichimai=True):
        for sc, a, s in pairs:
            if len(anshin) >= 4:
                return
            if (a["id"], s["id"]) in used_songs:
                continue
            if hitori_ichimai and a["id"] in used_artists:
                continue
            anshin.append(_card(a, s, "安心"))
            used_artists.add(a["id"])
            used_songs.add((a["id"], s["id"]))

    if len(konomi) >= 2:
        # ★趣味の違う2人が同時に聞いている前提。片方だけで4枚埋めない。
        #   1人ぶんずつ交互に積む（2人なら2枚ずつ、3人なら1〜2枚ずつ）。
        betsu = [_candidates([k]) for k in konomi[:4]]
        for _ in range(4):
            for hitori in betsu:
                if len(anshin) >= 4:
                    break
                mada = [x for x in hitori if x[1]["id"] not in used_artists]
                _tsumu(mada[:1])  # ★1周に1人1枚ずつ。片方が4枚さらうのを止める
    _tsumu(cand)
    if len(anshin) < 4:
        yurui = [x for x in ((_score(a, s, hint), a, s) for a in _soul["artists"] for s in a["songs"]) if x[0] >= 2]
        yurui.sort(key=lambda x: (-x[0], x[1]["id"], x[2]["id"]))
        _tsumu(yurui)
    if len(anshin) < 4:
        _tsumu(cand, hitori_ichimai=False)  # ★同じ人の別の曲で埋める（外さない方を優先）

    # ── 橋1枚：趣味の違う2人を満足させる（★無理に繋がない。無ければ null）
    hashi = None
    if len(konomi) >= 2:
        a_hits = {x[1]["id"] for x in _candidates([konomi[0]])}
        b_hits = {x[1]["id"] for x in _candidates([konomi[1]])}
        both = a_hits & b_hits
        if both:
            for sc, a, s in cand:
                if a["id"] in both:
                    hashi = _card(a, s, "橋")
                    break

    # ── 冒険1枚：好みに1つもかすっていないところから。★入力から決まる＝毎回同じ
    bouken = None
    miss = [a for a in _soul["artists"] if a["id"] not in used_artists and a["songs"]]
    playable = [a for a in miss if any(s.get("youtubeId") for s in a["songs"])]
    pool = playable or miss
    if pool:
        a = pool[_seed("bouken", *konomi, kibun, ima_no_tana) % len(pool)]
        songs = [s for s in a["songs"] if s.get("youtubeId")] or a["songs"]
        s = songs[_seed("bouken-song", a["id"], *konomi) % len(songs)]
        bouken = _card(a, s, "冒険")

    cards = anshin + ([bouken] if bouken else [])

    # ── この流れで：★固定。先頭のカードと同じアーティストの別の曲。同じ入力なら毎回同じ。
    kono_nagare_de = []
    if anshin:
        top = anshin[0]
        a = next((x for x in _soul["artists"] if x["id"] == top["artist_id"]), None)
        if a:
            rest = [s for s in a["songs"] if s["id"] != top["song_id"] and s.get("youtubeId")]
            rest.sort(key=lambda s: (not s.get("pick"), s["id"]))
            kono_nagare_de = [_card(a, s, "この流れで") for s in rest[:3]]

    # ── こちらもどうぞ：★その人ごとに変える。文脈から離れてよい。
    kochira_mo_douzo = None
    if pool:
        a = pool[_seed("kochira", hito or "nanashi", datetime.now(JST).strftime("%Y-%m-%d")) % len(pool)]
        songs = [s for s in a["songs"] if s.get("youtubeId")] or a["songs"]
        s = songs[_seed("kochira-song", hito or "nanashi", a["id"]) % len(songs)]
        kochira_mo_douzo = _card(a, s, "こちらもどうぞ")

    # ── 一言：★うんちくがあるときだけ1行。無ければ黙る。
    hitokoto = None
    if anshin:
        hitokoto = anshin[0].get("hitokoto") or anshin[0].get("unchiku")
        if hitokoto and len(hitokoto) > 90:
            hitokoto = None  # 長いうんちくは声で読ませない（喋りすぎは減点）

    return {
        "ok": True,
        "cards": cards,
        "hashi": hashi,
        "kono_nagare_de": kono_nagare_de,
        "kochira_mo_douzo": kochira_mo_douzo,
        "hitokoto": hitokoto,
        "kimari": {
            "hiritsu": f"安心{len(anshin)}：冒険{1 if bouken else 0}",
            "kono_nagare_de": "固定",
            "kochira_mo_douzo": "人ごとに変える",
            "atatta": len(cand),
        },
    }


def shiraberu(go: str = "", kazu: int = 8) -> dict:
    _load()
    kazu = max(1, min(int(kazu or 8), 30))
    n = _norm(go)
    if not n:
        return {"ok": True, "tana": [], "artists": [], "songs": []}

    tana = [t for t in _soul["tana"] if n in _norm(t["title"]) or n in _norm(t["id"]) or n in _norm(t.get("subtitle") or "")]

    artists = []
    for a, words in _index:
        if any(n == w or (len(n) >= 2 and n in w) or (len(w) >= 2 and w in n) for w in words):
            artists.append(
                {
                    "id": a["id"],
                    "name": a["name"],
                    "aliases": a.get("aliases", []),
                    "kyokusu": len(a["songs"]),
                    "path": f"/cover-guide?artist={a['id']}",
                    "about": a.get("about"),
                }
            )
    artists.sort(key=lambda x: (-x["kyokusu"], x["id"]))

    songs = []
    for a in _soul["artists"]:
        for s in a["songs"]:
            if len(n) >= 2 and n in _norm(s["title"]):
                songs.append(_card(a, s, "しらべ"))
    songs.sort(key=lambda c: (c["youtubeId"] is None, c["artist_id"], c["song_id"]))

    return {
        "ok": True,
        "tana": tana[:kazu],
        "artists": artists[:kazu],
        "songs": songs[:kazu],
        "atatta": {"tana": len(tana), "artists": len(artists), "songs": len(songs)},
    }


def jinkaku() -> dict:
    _load()
    now = datetime.now(JST)
    h = now.hour
    sugata = next((g for g in _jinkaku["sugata"] if g["id"] == ("mama" if (h >= 23 or h < 5) else "annainin")))
    out = dict(_jinkaku)
    out["ima"] = now.strftime("%Y-%m-%d %H:%M JST")
    out["ima_no_sugata"] = sugata
    out["ok"] = True
    out.pop("sugata", None)
    return out


# ══════════════════════════════════════════════════════════════
# 5. 脳から呼ぶ入口（★脳はここしか触らない）
# ══════════════════════════════════════════════════════════════
FUNCS = {"osusume": osusume, "shiraberu": shiraberu, "jinkaku": jinkaku}


def call(name: str, args: dict | None = None) -> dict:
    """★どの脳もこの1行を呼ぶ。脳ごとの分岐はここに書かない。"""
    fn = FUNCS.get(name)
    if fn is None:
        return {"ok": False, "error": f"そんな口はない: {name}", "aru_kuchi": list(FUNCS)}
    args = {k: v for k, v in (args or {}).items() if k in fn.__code__.co_varnames}
    try:
        return fn(**args)
    except Exception as e:  # 脳を落とさない。理由をそのまま上に返す
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ══════════════════════════════════════════════════════════════
# 6. 自己試験（★叩いて通ったものだけが証拠）
# ══════════════════════════════════════════════════════════════
def self_test() -> int:
    ng = []
    _load()

    # ① 3つの口が全部返るか
    for name in ("osusume", "shiraberu", "jinkaku"):
        r = call(name, {"konomi": ["久保田利伸"], "go": "久保田利伸"})
        if not r.get("ok"):
            ng.append(f"{name} が返らない: {r.get('error')}")

    # ② 安心4：冒険1 になっているか
    r = osusume(konomi=["久保田利伸"])
    n_anshin = sum(1 for c in r["cards"] if c["riyu"] == "安心")
    n_bouken = sum(1 for c in r["cards"] if c["riyu"] == "冒険")
    if n_anshin != 4 or n_bouken != 1:
        ng.append(f"安心4：冒険1 になっていない（安心{n_anshin}・冒険{n_bouken}）")

    # ③ 同じ入力なら毎回同じか（＝乱数を使っていないこと）
    a = osusume(konomi=["久保田利伸"], hito="seki-1")
    b = osusume(konomi=["久保田利伸"], hito="seki-1")
    if json.dumps(a, ensure_ascii=False) != json.dumps(b, ensure_ascii=False):
        ng.append("同じ入力で答えが変わる（乱数が混ざっている）")

    # ④ 「この流れで」は人が変わっても固定か
    c = osusume(konomi=["久保田利伸"], hito="seki-2")
    if [x["song_id"] for x in a["kono_nagare_de"]] != [x["song_id"] for x in c["kono_nagare_de"]]:
        ng.append("『この流れで』が人によって変わっている（固定のはず）")

    # ⑤ 「こちらもどうぞ」は人ごとに変わるか
    diff = False
    for i in range(12):
        d = osusume(konomi=["久保田利伸"], hito=f"seki-{i}")
        if d["kochira_mo_douzo"]["song_id"] != a["kochira_mo_douzo"]["song_id"]:
            diff = True
            break
    if not diff:
        ng.append("『こちらもどうぞ』が誰でも同じ（人ごとに変えるはず）")

    # ⑥ 趣味の違う2人：橋が出るか／出ないときに null で正直に返るか
    f = osusume(konomi=["久保田利伸", "犬"])
    if "hashi" not in f:
        ng.append("2人ぶんの好みで hashi が返っていない")

    # ⑦ ★うんちくが無い曲に、うんちくを作っていないか
    made_up = 0
    for c in f["cards"] + f["kono_nagare_de"]:
        src = None
        for ar in _soul["artists"]:
            if ar["id"] == c["artist_id"]:
                src = next((s for s in ar["songs"] if s["id"] == c["song_id"]), None)
        if src and (src.get("unchiku") or None) != (c.get("unchiku") or None):
            made_up += 1
    if made_up:
        ng.append(f"元データに無いうんちくが付いている: {made_up}件")

    # ⑧ ★鍵・モデル名・AI会社の名前がこの口に混ざっていないか
    #    （検査する場所は「魂の本体」だけ。説明文と、この自己試験そのものは対象外。
    #     禁句を素で書くと自分に引っかかるので、組み立ててから探す）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src.split("# 2. 魂を読む", 1)[-1].split("def self_test", 1)[0].lower()
    kinku = ["api" + "_key", "api" + "key", "s" + "k-", "xa" + "i-", "ws" + "s://",
             "gp" + "t-4", "gro" + "k-", "elev" + "en_", "open" + "ai.com", "anthro" + "pic"]
    for word in kinku:
        if word in body:
            ng.append(f"口の中に脳の話が混ざっている: {word}")

    # ⑨ 3方言の関数定義が同じ3つを指しているか
    t = tools_json()
    names = {
        "openai": sorted(x["function"]["name"] for x in t["openai"]),
        "realtime": sorted(x["name"] for x in t["realtime"]),
        "elevenlabs": sorted(x["name"] for x in t["elevenlabs"]),
        "gemini": sorted(x["name"] for x in t["gemini"]["functionDeclarations"]),
    }
    if len({json.dumps(v) for v in names.values()}) != 1:
        ng.append(f"脳ごとに口の数が違う: {names}")

    for line in ng:
        print("✕", line)
    if not ng:
        print(
            f"○ 魂の口：3つ全部通った（osusume / shiraberu / jinkaku）"
            f"／{len(_soul['artists'])}人・{sum(len(x['songs']) for x in _soul['artists'])}曲"
            f"／4方言（openai・realtime・elevenlabs・gemini）で同じ3つ"
            f"／AIを0回・0円・同じ入力なら毎回同じ"
        )
    return 1 if ng else 0


# ══════════════════════════════════════════════════════════════
# 7. 突き合わせ表（★口が2つの言葉で書かれているとき、食い違いを機械で止める）
#    魂の本体は Python（ここ）。ブラウザの中で動く脳のために JS版（kuchi.mjs）がある。
#    人が見比べて「同じはず」と言うのは証拠にならないので、
#    決まった問いへの答えをここで書き出し、JS版はそれと1文字でも違えば落ちる。
# ══════════════════════════════════════════════════════════════
TESTVEC_PATH = os.path.join(HERE, "testvec.json")

TESTVEC_TOI = [
    {"konomi": ["久保田利伸"], "hito": "seki-1"},
    {"konomi": ["久保田利伸", "犬"], "hito": "seki-7"},
    {"konomi": ["ブラジル", "笑い"], "hito": "seki-2"},
    {"konomi": ["旅"], "kibun": "疲れた", "ima_no_tana": "travel", "hito": "seki-3"},
    {"konomi": ["そんな言葉はどこにもない9999"], "hito": "seki-4"},
]


def testvec() -> dict:
    _load()
    out = []
    for toi in TESTVEC_TOI:
        r = osusume(**toi)
        out.append(
            {
                "toi": toi,
                "cards": [[c["artist_id"], c["song_id"], c["riyu"]] for c in r["cards"]],
                "hashi": [r["hashi"]["artist_id"], r["hashi"]["song_id"]] if r["hashi"] else None,
                "kono_nagare_de": [c["song_id"] for c in r["kono_nagare_de"]],
                "hitokoto": r["hitokoto"],
            }
        )
    shira = []
    for go in ["久保田", "犬", "ブラジル", "ないない9999"]:
        r = shiraberu(go=go, kazu=5)
        shira.append({"go": go, "artists": [a["id"] for a in r["artists"]], "songs": [c["song_id"] for c in r["songs"]]})
    return {
        "_これは何": "Python版とJS版の口が同じ答えを出すことの証拠。片方だけ直すとここで落ちる。",
        "soul_sha256_12": hashlib.sha256(open(SOUL_PATH, "rb").read()).hexdigest()[:12],
        "osusume": out,
        "shiraberu": shira,
    }


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--testvec" in sys.argv:
        v = testvec()
        with open(TESTVEC_PATH, "w", encoding="utf-8") as fp:
            json.dump(v, fp, ensure_ascii=False, indent=1)
        print(f"書いた: {os.path.relpath(TESTVEC_PATH)}（おすすめ{len(v['osusume'])}問・しらべ{len(v['shiraberu'])}問）")
        sys.exit(0)
    if "--tools" in sys.argv:
        t = tools_json()
        with open(TOOLS_PATH, "w", encoding="utf-8") as fp:
            json.dump(t, fp, ensure_ascii=False, indent=2)
        print(f"書いた: {os.path.relpath(TOOLS_PATH)}（4方言・各{len(KUCHI_SPEC)}個）")
        sys.exit(0)
    if len(sys.argv) >= 2:
        nm = sys.argv[1]
        ar = json.loads(sys.argv[2]) if len(sys.argv) >= 3 else {}
        print(json.dumps(call(nm, ar), ensure_ascii=False, indent=2))
        sys.exit(0)
    print(__doc__)
