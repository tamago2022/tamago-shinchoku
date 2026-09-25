#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1142番：門の生死を実測する係（＋弾いた数の台帳）。

たまごさん（2026-09-25）：
  「ミスがなくなる＝門。出す前に機械が弾く。
   ★弾いた数を必ず数える。弾き0が続いたら門が死んでいる＝赤。」

------------------------------------------------------------------
なぜこれが要るのか
------------------------------------------------------------------
門はもう十分ある。2026-09-25 実測：

  tools/sekisho/gate_artist_song.py     本人か（名前一致は証拠にしない）
  tools/sekisho/gate_fact_source.py     断定に出典URLがあるか
  tools/sekisho/jev_honnin.py           機械に本人か聞く
  tools/oni_gate.py                     鬼監督
  .githooks/pre-push                    上を push の直前で必ず通す

**足りないのは門ではない。「その門が今も生きているか」を確かめる係。**

火災報知器は、鳴らない日が続いても「平和だ」とは言えない。
**押しボタンで鳴らしてみないと、電池切れと平和は見分けがつかない。**
これは世界中どこでも同じで、SRE では synthetic check／canary、
工場の受入検査では「わざと不良品を1個流す」と呼ばれている。

------------------------------------------------------------------
やること（2つだけ）
------------------------------------------------------------------
  ① わざと通ってはいけない1件を、各門に流す。
     → 弾けば **門は生きている**。通ったら **門は死んでいる＝赤**。
     ★本物のデータには一切触らない。その場で作る偽物だけを流す。
  ② 弾いた数を status/1142_kanmon.jsonl に1行ずつ足す。
     → 1142_loop.py の「門が弾いた数」がこれを読む。

------------------------------------------------------------------
戻し方（1行）
------------------------------------------------------------------
  python3 ~/Desktop/tamago-shinchoku/tools/1142_loop.py --modosu
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import datetime

JST = datetime.timezone(datetime.timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LEDGER = os.path.join(STATUS, "1142_kanmon.jsonl")
OUT = os.path.join(STATUS, "public", "1142_kanmon.json")


def now():
    return datetime.datetime.now(JST)


def nokosu(gate, tsuuka, riyuu, what):
    """★通したものも弾いたものも、同じ1行で残す。弾きだけ残すと母数が消える。"""
    row = dict(at=now().isoformat(), gate=gate, tsuuka=bool(tsuuka),
               riyuu=riyuu, what=what)
    try:
        with io.open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


# ════════════════════════════════════════════════════════════════
# わざと通ってはいけない1件（＝押しボタン）
#   ★どれも「たまごさんが実際にやられた事故」をそのまま小さくしたもの
# ════════════════════════════════════════════════════════════════
NISEMONO = [
    dict(
        gate="出典の門",
        tool="sekisho/gate_fact_source.py",
        naze="出典URLの無い断定（akiko『Do You Know?』2026-09-19の事故）",
        ts=('export const artists = [\n'
            '  { id: "x-1142-test", name: "テスト太郎", aliases: [], eras: [], '
            'about: "門の押しボタン用。本物ではない。", songs: [\n'
            '    { id: "x-1142-song", title: "テスト曲", '
            'note: "2002年に発表されたオリジナル・バラード。代表曲のひとつ。", '
            'youtubeId: "PENDING" }\n'
            '  ]}\n'
            '];\n'),
    ),
    dict(
        gate="本人の門",
        tool="sekisho/gate_artist_song.py",
        naze="名前の字面が一致しただけの別人（akiko × AKIKO の事故）",
        ts=('export const artists = [\n'
            '  { id: "akiko", name: "akiko", aliases: ["AKIKO"], eras: ["00s"], '
            'about: "ジャズシンガー。", songs: [\n'
            '    { id: "coffee-or-tea-prod-silverstrike", '
            'title: "Coffee or tea (Prod. SILVERSTRIKE)", '
            'note: "チャンネル名が一致しているだけの別人。", youtubeId: "FKIVSFDmmAs" }\n'
            '  ]},\n'
            '  { id: "akiko-yano", name: "矢野顕子", aliases: ["Akiko Yano"], '
            'eras: ["70s"], about: "シンガーソングライター。", songs: [\n'
            '    { id: "gohan-ga-dekita-yo", title: "ごはんができたよ", '
            'note: "1980年発表。", year: 1980, youtubeId: "PENDING" }\n'
            '  ]}\n'
            '];\n'),
    ),
]


def _run(cmd, cwd=REPO, sec=90):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=sec)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "時間切れ"
    except FileNotFoundError:
        return 127, "その門のファイルが無い"
    except Exception as e:
        return 1, str(e)[:200]


def oshibotan():
    """押しボタン：わざと不正な1件を流して、門が鳴るか実測する。"""
    kekka = []
    for n in NISEMONO:
        tool = os.path.join(REPO, "tools", n["tool"])
        if not os.path.exists(tool):
            kekka.append(dict(gate=n["gate"], ikiteru=None,
                              why="門のファイルが見つからない（%s）" % n["tool"]))
            nokosu(n["gate"], True, "門が見つからない＝素通り", n["naze"])
            continue
        fd, path = tempfile.mkstemp(suffix="_1142_nisemono.ts")
        try:
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(n["ts"])
            rc, out = _run([sys.executable, tool, path, "--strict"])
            if rc == 127:
                rc, out = _run([sys.executable, tool, path])
            # ★弾いた＝0以外で終わる／出力に止めた印がある
            hajiita = (rc not in (0,)) or any(
                w in out for w in ("NG", "止め", "弾", "未出典", "別人", "保留"))
            kekka.append(dict(gate=n["gate"], ikiteru=bool(hajiita),
                              why=(out or "").strip().splitlines()[-1][:120]
                              if out.strip() else "出力なし"))
            nokosu(n["gate"], not hajiita,
                   ("押しボタン：弾いた（門は生きている）" if hajiita
                    else "★押しボタン：通してしまった（門が死んでいる）"),
                   n["naze"])
        finally:
            try:
                os.close(fd)
                os.remove(path)
            except OSError:
                pass
    return kekka


def kazoeru(days=7):
    """台帳から、直近days日の 通した／弾いた を数える。"""
    since = (now() - datetime.timedelta(days=days)).isoformat()
    t = h = 0
    try:
        for line in io.open(LEDGER, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if str(r.get("at", "")) < since:
                continue
            if r.get("tsuuka"):
                t += 1
            else:
                h += 1
    except FileNotFoundError:
        pass
    return t, h


GATE_SEC = 6 * 3600          # 押しボタンは6時間に1回でいい（毎回叩くと無駄打ち）
GATE_AT = os.path.join(STATUS, ".1142_kanmon_at")


def mabiku():
    """6時間に1回だけ通す。★通さなかったことも黙らない（ログに1行残す）。"""
    if "--ima" in sys.argv:
        return True
    try:
        import time as _t
        if _t.time() - os.path.getmtime(GATE_AT) < GATE_SEC:
            return False
    except OSError:
        pass
    try:
        io.open(GATE_AT, "w").write("")
    except Exception:
        pass
    return True


def main():
    if not mabiku():
        print("押しボタンは6時間に1回。今回は見送り（--ima で今すぐ叩ける）")
        return
    k = oshibotan()
    t, h = kazoeru()
    shinda = [x["gate"] for x in k if x["ikiteru"] is not True]
    out = dict(at=now().strftime("%Y-%m-%d %H:%M:%S"),
               kekka=k, tooshita=t, hajiita=h,
               shindaKanmon=shinda,
               hitokoto=("★門が死んでいます：%s" % "／".join(shinda)) if shinda
                        else "門は全部生きています（押しボタンで実測）")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    json.dump(out, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print(out["hitokoto"])
    for x in k:
        print("  %s %s：%s" % ("✅" if x["ikiteru"] else "🔴", x["gate"], x["why"]))
    print("  直近7日：通した%d／弾いた%d" % (t, h))


if __name__ == "__main__":
    main()
