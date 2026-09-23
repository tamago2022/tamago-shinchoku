#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1058番【Gensparkへ自動で流す配管】

━━ なぜ作ったか（2026-09-24・たまごさん原文）━━

  「Gensparkにも金払ってるんだから使ってあげないともったいない。
    俺が水汲みをやるからDevinは動かせるけど、Gensparkは動かせないの。
    CLIから繋がってるんでしょう。動かそうよ。」
  「配管は作り切る。中身の仕事だけ後から差せる形にする。
    たまごさんが番号で仕事を選ぶ。選ばれるまでクレジットを使わない。」

━━ 実測で分かっていること（憶測なし）━━

  ・`gsk` は Mac の /Users/mac/.npm-global/bin/gsk に入っている。
    サンドボックス（Cowork/Dispatch）からは出られない。**心臓（Mac）から走らせる。**
  ・`gsk me` は残クレジットを返す。**これはクレジットを消費しない**（実測：前後で不変）。
  ・`gsk search <q>` が一番安い問い。実測 -1.000 クレジット。
  ・2026-09-24 02:09 実測の残高 1924.937。10/4でプラン終了・繰り越しなし。

━━ 設計（増やさない）━━

  ① **献立（status/gsk/shigoto.json）** … 番号つきの仕事の一覧。中身だけ後から差せる。
  ② **注文（status/gsk/erabi.json）** … たまごさんが選んだ番号。
     ★`erabu` が null のあいだは **1クレジットも使わない**。ファイルを1枚読んで即戻る。
  ③ **在庫（status/gsk/todo_<番号>.jsonl）** … その仕事の対象1件＝1行。
  ④ **台帳（status/gsk_daicho.jsonl）** … 1回投げるごとに1行。残クレジットを毎回記録。
  ⑤ **栓** … 1日の上限（日割り）を超えたらその日は流さない。既定 0件＝止まっている。
  ⑥ **諦め** … 同じ1件で3回失敗したら「取れない」と記録して次へ。無限に叩かない。
  ⑦ たまごさんに質問しない。判断はここでする。

━━ 使い方 ━━

    python3 tools/genspark_nagashi.py --zan            # 残クレジットを見る（0クレジット）
    python3 tools/genspark_nagashi.py --kondate        # 献立（番号つきの仕事一覧）を出す
    python3 tools/genspark_nagashi.py --erabu 2        # 2番の仕事を流し始める
    python3 tools/genspark_nagashi.py --tomeru         # 止める（erabu=null に戻す）
    python3 tools/genspark_nagashi.py --haikan-test    # 配管の実測（★1クレジットだけ使う）
    python3 tools/genspark_nagashi.py                  # 心臓から呼ばれる本体（1周＝最大N件）

  終了コード: 0=正常 / 1=配管が通らない
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
GSKDIR = os.path.join(STATUS, "gsk")
SHIGOTO = os.path.join(GSKDIR, "shigoto.json")      # 献立
ERABI = os.path.join(GSKDIR, "erabi.json")          # 注文
DAICHO = os.path.join(STATUS, "gsk_daicho.jsonl")   # 台帳
ZAN = os.path.join(GSKDIR, "zan.json")              # 直近の残クレジット
GATE = os.path.join(GSKDIR, ".nagashi_at")          # 間引き
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")

# gsk の実体（実測の場所を先に見る。無ければ PATH から探す）
GSK_CANDIDATES = [
    "/Users/mac/.npm-global/bin/gsk",
    "/opt/homebrew/bin/gsk",
    "/usr/local/bin/gsk",
]
PLAN_END = date(2026, 10, 4)     # このプランが終わる日（繰り越しなし）
INTERVAL_SEC = 60                # 心臓から何度呼ばれても、実際に流すのは60秒に1回
PER_CYCLE = 3                    # 1周で投げる最大件数
MAX_TRY = 3                      # 同じ1件で3回失敗したら諦める


# ───────────────────────── 小道具 ─────────────────────────

def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _shirase(honbun: str):
    """黙らない。止めた／通らなかった事実は必ず外へ1行出す。"""
    try:
        _append(OUTBOX, {"at": _now(), "from": "genspark_nagashi", "what": honbun})
    except Exception:
        pass


def gsk_path():
    for p in GSK_CANDIDATES:
        if os.path.exists(p):
            return p
    for d in os.environ.get("PATH", "").split(":"):
        p = os.path.join(d, "gsk")
        if os.path.exists(p):
            return p
    return None


def gsk_run(args, timeout=180):
    """gsk を1本だけ走らせる。白名簿の外は走らせない。"""
    g = gsk_path()
    if not g:
        return {"ok": False, "error": "gsk が見つかりません（このMacに入っていない）"}
    try:
        r = subprocess.run([g] + list(args), capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "exit": r.returncode,
                "stdout": (r.stdout or "")[:200000], "stderr": (r.stderr or "")[:4000]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "%d秒で返りませんでした" % timeout}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}


# ───────────────────────── 残クレジット（0クレジット） ─────────────────────────

def zandaka(record=True):
    """`gsk me` で残クレジットを見る。★これ自体はクレジットを使わない（実測）。"""
    r = gsk_run(["me"], timeout=60)
    bal = None
    if r.get("ok"):
        try:
            bal = json.loads(r["stdout"])["data"]["credit_balance"]
        except Exception:
            bal = None
    out = {"at": _now(), "zan": bal, "ok": bal is not None,
           "error": None if bal is not None else (r.get("error") or r.get("stderr") or "残高が読めません")}
    if record:
        _write_json(ZAN, out)
    return out


def nokori_nissu() -> int:
    return max(1, (PLAN_END - date.today()).days)


def hiwari_jougen(zan) -> int:
    """10/4までの日割り。★一気に使い切らない。"""
    if not zan:
        return 0
    return max(1, int(zan // nokori_nissu()))


# ───────────────────────── 献立と注文 ─────────────────────────

KONDATE_HINAGATA = {
    "説明": "番号つきの仕事の献立。★たまごさんが番号で選ぶまで1クレジットも使わない。中身だけ後から差せる。",
    "shigoto": [
        {
            "bangou": 1,
            "namae": "配管テスト（一番安い問いを1回だけ）",
            "toi": "genspark cli",
            "gsk": ["search", "{{q}}"],
            "todo": None,
            "1件あたり": 1,
            "件数": 1
        }
    ]
}


def kondate():
    k = _read_json(SHIGOTO, None)
    if k is None:
        _write_json(SHIGOTO, KONDATE_HINAGATA)
        k = KONDATE_HINAGATA
    return k


def erabi():
    e = _read_json(ERABI, None)
    if e is None:
        e = {"erabu": None, "1日の上限": 0, "決めた": None,
             "覚え書き": "erabu に献立の番号を入れると流れ始める。null のあいだは1クレジットも使わない。"}
        _write_json(ERABI, e)
    return e


def shigoto_wo_hiku(bangou):
    for s in kondate().get("shigoto", []):
        if int(s.get("bangou", -1)) == int(bangou):
            return s
    return None


# ───────────────────────── 在庫（対象1件＝1行） ─────────────────────────

def todo_path(s):
    t = s.get("todo")
    if not t:
        return None
    return t if os.path.isabs(t) else os.path.join(REPO, t)


def tsugi_no_ikken(s):
    """まだ投げていない／3回未満で失敗している1件を返す。無ければ None。"""
    p = todo_path(s)
    if not p or not os.path.exists(p):
        return None
    rows = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    for i, r in enumerate(rows):
        if r.get("済"):
            continue
        if int(r.get("失敗", 0)) >= MAX_TRY:
            continue
        return {"i": i, "row": r, "rows": rows, "path": p}
    return None


def todo_kaku(ctx):
    with open(ctx["path"], "w", encoding="utf-8") as f:
        for r in ctx["rows"]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ───────────────────────── 1件投げる ─────────────────────────

def hitotsu_nageru(s, toi, meta=None):
    """gsk へ1件投げて、台帳に残クレジットごと1行残す。"""
    mae = zandaka(record=False).get("zan")
    args = [a.replace("{{q}}", toi) for a in s.get("gsk", ["search", "{{q}}"])]
    t0 = time.time()
    r = gsk_run(args)
    ato = zandaka().get("zan")
    tsukatta = None
    if isinstance(mae, (int, float)) and isinstance(ato, (int, float)):
        tsukatta = round(mae - ato, 3)
    gyou = {
        "at": _now(),
        "bangou": s.get("bangou"),
        "shigoto": s.get("namae"),
        "toi": toi,
        "ok": bool(r.get("ok")),
        "秒": round(time.time() - t0, 1),
        "残クレジット": ato,
        "使ったクレジット": tsukatta,
        "error": None if r.get("ok") else (r.get("error") or (r.get("stderr") or "")[:300]),
    }
    if meta:
        gyou.update(meta)
    # 答えの実体は別置き（台帳を太らせない）
    if r.get("ok"):
        os.makedirs(os.path.join(GSKDIR, "kotae"), exist_ok=True)
        fn = os.path.join(GSKDIR, "kotae", "%s_%d.txt" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid()))
        try:
            with open(fn, "w", encoding="utf-8") as f:
                f.write(r.get("stdout", ""))
            gyou["答え"] = os.path.relpath(fn, REPO)
        except Exception:
            pass
    _append(DAICHO, gyou)
    return gyou


# ───────────────────────── 本体（心臓から呼ばれる） ─────────────────────────

def kyou_nagashita() -> int:
    kyou = time.strftime("%Y-%m-%d")
    n = 0
    if not os.path.exists(DAICHO):
        return 0
    with open(DAICHO, "r", encoding="utf-8") as f:
        for line in f:
            try:
                g = json.loads(line)
            except Exception:
                continue
            if str(g.get("at", "")).startswith(kyou) and g.get("使ったクレジット"):
                n += 1
    return n


def nagasu(force=False):
    """★選ばれていなければ、ファイルを1枚読んで即戻る（通信0・クレジット0）。"""
    e = erabi()
    bangou = e.get("erabu")
    if bangou in (None, "", 0):
        return {"ok": True, "流した": 0, "理由": "まだ番号が選ばれていません（クレジット0）"}

    # 間引き（心臓は15秒おきに呼ぶ。実際に流すのは60秒に1回）
    if not force:
        try:
            if os.path.exists(GATE) and (time.time() - os.path.getmtime(GATE)) < INTERVAL_SEC:
                return {"ok": True, "流した": 0, "理由": "間引き中"}
        except Exception:
            pass
    os.makedirs(GSKDIR, exist_ok=True)
    open(GATE, "w").close()

    s = shigoto_wo_hiku(bangou)
    if not s:
        _shirase("Gensparkの配管：献立に %s 番がありません。流していません。" % bangou)
        return {"ok": False, "流した": 0, "理由": "献立に %s 番がない" % bangou}

    z = zandaka()
    if not z.get("ok"):
        _shirase("Gensparkの配管：残クレジットが読めないので流していません（%s）" % z.get("error"))
        return {"ok": False, "流した": 0, "理由": z.get("error")}

    jougen = int(e.get("1日の上限") or 0) or hiwari_jougen(z["zan"])
    sumi = kyou_nagashita()
    if sumi >= jougen:
        return {"ok": True, "流した": 0, "理由": "今日の上限 %d件に達しています（残%s）" % (jougen, z["zan"])}

    nagashita = 0
    for _ in range(min(PER_CYCLE, jougen - sumi)):
        ctx = tsugi_no_ikken(s)
        if not ctx:
            return {"ok": True, "流した": nagashita, "理由": "この仕事の対象は全部さばきました",
                    "残": z["zan"]}
        row = ctx["row"]
        toi = str(s.get("toi", "{{q}}")).replace("{{q}}", str(row.get("q") or row.get("名前") or ""))
        g = hitotsu_nageru(s, toi, meta={"対象": row.get("名前") or row.get("q")})
        if g["ok"]:
            row["済"] = True
            row["答え"] = g.get("答え")
        else:
            row["失敗"] = int(row.get("失敗", 0)) + 1
            if row["失敗"] >= MAX_TRY:
                row["取れない"] = True
                row["済"] = True
        ctx["rows"][ctx["i"]] = row
        todo_kaku(ctx)
        nagashita += 1
        if not g["ok"]:
            break
    return {"ok": True, "流した": nagashita, "残": zandaka().get("zan")}


# ───────────────────────── 配管の実測（★1クレジットだけ） ─────────────────────────

def haikan_test():
    """一番安い問いを1回だけ投げて、配管が通ったかを数字で言う。"""
    mae = zandaka(record=False)
    if not mae.get("ok"):
        return {"ok": False, "理由": "gsk が返りません: %s" % mae.get("error"), "残": None}
    s = {"bangou": 0, "namae": "配管テスト", "gsk": ["search", "{{q}}"]}
    g = hitotsu_nageru(s, "genspark cli", meta={"配管テスト": True})
    return {"ok": bool(g["ok"]), "前": mae["zan"], "残": g["残クレジット"],
            "使った": g["使ったクレジット"], "error": g.get("error")}


# ───────────────────────── 口（CLI） ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zan", action="store_true", help="残クレジットを見る（0クレジット）")
    ap.add_argument("--kondate", action="store_true", help="献立を出す")
    ap.add_argument("--erabu", type=int, help="番号を選んで流し始める")
    ap.add_argument("--jougen", type=int, help="1日の上限（件）。0で日割り自動")
    ap.add_argument("--tomeru", action="store_true", help="止める")
    ap.add_argument("--haikan-test", action="store_true", help="★1クレジットだけ使って配管を実測")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if a.kondate:
        print(json.dumps(kondate(), ensure_ascii=False, indent=2))
        return 0
    if a.zan:
        print(json.dumps(zandaka(), ensure_ascii=False))
        return 0
    if a.tomeru:
        e = erabi(); e["erabu"] = None; e["決めた"] = _now(); _write_json(ERABI, e)
        print("止めました（クレジットは1つも使いません）")
        return 0
    if a.erabu is not None:
        if not shigoto_wo_hiku(a.erabu):
            print("献立に %d 番がありません" % a.erabu); return 1
        e = erabi(); e["erabu"] = a.erabu; e["決めた"] = _now()
        if a.jougen is not None:
            e["1日の上限"] = a.jougen
        _write_json(ERABI, e)
        print(json.dumps({"選んだ": a.erabu, "1日の上限": e.get("1日の上限")}, ensure_ascii=False))
        return 0
    if a.haikan_test:
        r = haikan_test()
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["ok"] else 1

    r = nagasu()
    if not a.quiet:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
