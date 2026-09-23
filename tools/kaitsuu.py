#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1029番：開通（かいつう）。全部の口を1発で叩いて、◯／✕と理由だけを出す係。

たまごさん（2026-09-23）：
  「1回開けたらもう全部通るようにしてよ」
  「ログインを求められ続けるのがすげえ苦痛なんだよ」

------------------------------------------------------------------
なぜ新しく作るのではなく、既にある台帳に乗せるのか
------------------------------------------------------------------
  叩く仕事は tools/kagi_daicho.py が既にやっている（5分便に相乗り・実測のみ）。
  ここで同じものを2本目として作ると、**数字が2つになって、どちらが本当か分からなくなる。**
  ＝ たまごさんが一番嫌がる「動いているのに取れていない」を、自分で作ることになる。
  だからこの係は叩き直さない。**台帳の結果を読んで、黙って飲み込まれている分だけを表に出す。**

------------------------------------------------------------------
この係がやること（台帳がやっていない3つだけ）
------------------------------------------------------------------
  1. no_credential / 401 / 403 / skip / blocked を **1件も省略せずに** 並べる。
     （台帳は件数を数えるが、朝の知らせには出していなかった）
  2. ★「走った回数 > 0 なのに 取れた回数 = 0」を最上段の赤にする。
     これが最悪の壊れ方。動いて見えるので、誰も気づかない。
  3. ★ 台帳に**載っていない口**を赤にする。載っていないものは、
     壊れていることにすら気づけない（Metaの鍵が3週間見つからなかった理由）。

------------------------------------------------------------------
使い方
------------------------------------------------------------------
    python3 tools/kaitsuu.py              … 人が読む形で全部出す
    python3 tools/kaitsuu.py --json       … 機械が読む形
    python3 tools/kaitsuu.py --asa        … 毎朝1回。★赤のときだけ知らせる。緑なら黙る
    python3 tools/kaitsuu.py --self-test  … 自己試験

値（鍵・トークン・パスワードの中身）は一切読まない・書かない。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
DAICHO = os.path.join(PUBLIC, "kagi_daicho.json")
OUT = os.path.join(PUBLIC, "kaitsuu.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
ASA_STATE = os.path.join(STATUS, ".kaitsuu_asa.json")
JST = timezone(timedelta(hours=9))

# ★黙って飲み込まれがちな印。0件にせず、必ず表に出す（たまごさん指定）。
NOMIKOMI = ("no_credential", "401", "403", "skip", "skipped", "blocked",
            "unauthorized", "forbidden", "expired", "insufficient_quota")

# 開通ページ（share/check/1029-kaitsuu.html）が並べている口。
# ★ここに在るのに台帳に無いものは、「誰も見ていない口」として赤で出す。
PAGE_IDS = ("claude", "gmail", "github", "gemini", "lovable",
            "openai", "xai", "copilot", "meta")


def _load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _age_min(ep):
    if not ep:
        return None
    return (time.time() - float(ep)) / 60.0


PAGES_LOG = os.path.join(STATUS, "pages_publish.log")


def happyou_okure(limit_min=35):
    """★出したものが本当に出たか。「出した」と「出ている」は別物。

    2026-09-23 の実害：`tools/pages_publish.sh` の錠が300秒で切れる作りだったため、
    遅い回が次の回に追い越されて **2本が同時に gh-pages を押し**、
    `cannot lock ref … is at X but expected Y` で弾かれ続けていた。
    10:35 以降 本番が1度も更新されず、**mainに入れたのに画面は古いまま**。
    ★この壊れ方は「成功も失敗も画面に出ない」ので、たまごさんが自分で見つけるまで誰も気づけない。
    だからここで必ず表に出す。
    """
    try:
        last_ok, last_ng = None, None
        with io.open(PAGES_LOG, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "公開しました" in line:
                    last_ok = line[:19]
                elif "push に3回とも失敗" in line or "push が落ちました" in line:
                    last_ng = line[:19]
        if not last_ok:
            return "一度も『公開しました』が記録されていません"
        t = datetime.strptime(last_ok, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        mins = (datetime.now(JST) - t).total_seconds() / 60.0
        if mins > limit_min:
            w = "最後に本番へ出たのが %d分前（%s）" % (mins, last_ok)
            if last_ng and last_ng > last_ok:
                w += "／そのあと push が落ちています（%s）" % last_ng
            return w + "＝mainに入れても画面は変わっていません"
    except Exception:
        return None
    return None


def collect():
    """台帳を読んで、赤だけを形にして返す。★叩き直さない（数字を2つにしない）。"""
    d = _load(DAICHO)
    if not d:
        return dict(ok=False,
                    why="台帳(status/public/kagi_daicho.json)がありません。"
                        "5分便が動いていないか、まだ1回も走っていません。",
                    generatedAt=None, keys=[], karamawari=[], nomikomi=[],
                    missing=list(PAGE_IDS), redCount=None)

    rows = d.get("rows") or []
    byid = {r.get("id"): r for r in rows}

    # ---- 1. 鍵・つながり。✕と△は理由ごと全部出す ----
    keys = []
    for r in rows:
        keys.append(dict(
            id=r.get("id"), what=r.get("what"), status=r.get("status"),
            detail=r.get("detail"), fix=r.get("fix"),
            stops=r.get("stops"),
            measuredMinAgo=(round(_age_min(r.get("measuredAt")), 1)
                            if r.get("measuredAt") else None),
        ))

    # ---- 2. ★走った>0 なのに 取れた=0（最悪の壊れ方） ----
    karamawari = []
    for w in (d.get("watchers") or []):
        runs = int(w.get("runs") or 0)
        catches = int(w.get("catches") or 0)
        if runs > 0 and catches == 0:
            karamawari.append(dict(
                id=w.get("id"), label=w.get("label"),
                runs=runs, catches=catches,
                blocked=w.get("blocked") or "",
                need=w.get("need") or "",
                why=(byid.get(w.get("need"), {}) or {}).get("detail") or "",
            ))

    # ---- 3. 飲み込まれている印を、1件も省略せずに ----
    nomikomi = []
    for w in (d.get("watchers") or []):
        b = str(w.get("blocked") or "").lower()
        if not b:
            continue
        hit = [n for n in NOMIKOMI if n in b]
        if hit:
            nomikomi.append(dict(who=w.get("label"), mark=w.get("blocked"),
                                 words=hit, runs=w.get("runs"),
                                 catches=w.get("catches")))
    for r in rows:
        det = str(r.get("detail") or "").lower()
        hit = [n for n in NOMIKOMI if n in det]
        if hit and r.get("status") != "ok":
            nomikomi.append(dict(who=r.get("what"), mark=r.get("detail"),
                                 words=hit, runs=None, catches=None))

    # ---- 4. ★台帳に載っていない口＝誰も見ていない ----
    missing = [i for i in PAGE_IDS if i not in byid]

    # ---- 5. ★出したものが本当に出たか（2026-09-23 実害） ----
    kouhai = happyou_okure()
    if kouhai:
        karamawari.append(dict(id="pages", label="本番への公開(GitHub Pages)",
                               runs=1, catches=0, blocked=kouhai, need="", why=kouhai))

    red = ([k for k in keys if k["status"] == "ng"]
           and True or bool(karamawari) or bool(missing))
    return dict(
        ok=True, generatedAt=d.get("generatedAt"),
        keys=keys, karamawari=karamawari, nomikomi=nomikomi, missing=missing,
        redKeys=[k for k in keys if k["status"] == "ng"],
        unknownKeys=[k for k in keys if k["status"] == "unknown"],
        redCount=len([k for k in keys if k["status"] == "ng"])
                 + len(karamawari) + len(missing),
        red=red,
    )


MARK = {"ok": "○", "ng": "✕", "unknown": "△"}


def show(res):
    if not res.get("ok"):
        print("✕ " + res["why"])
        return 1
    print("＝＝ 開通のようす（機械が叩いた結果・%s）＝＝" % (res.get("generatedAt") or "?"))
    print("")
    for k in res["keys"]:
        old = ""
        if k["measuredMinAgo"] is not None and k["measuredMinAgo"] > 60:
            old = "  ※%d分前の古い測定" % k["measuredMinAgo"]
        print("%s %-30s %s%s" % (MARK.get(k["status"], "?"),
                                 (k["what"] or "")[:30], k["detail"], old))
    print("")
    if res["karamawari"]:
        print("★走ったのに1つも取れていないもの（一番まずい壊れ方）")
        for w in res["karamawari"]:
            print("  ✕ %s：走った%d回 → 取れた0回　%s" %
                  (w["label"], w["runs"], w["blocked"] or w["why"]))
        print("")
    if res["missing"]:
        print("★台帳に載っていない口（＝壊れていても誰も気づけない）")
        for m in res["missing"]:
            print("  ✕ %s" % m)
        print("")
    if res["nomikomi"]:
        print("★黙って飲み込まれていた印（%d件・1件も省略していません）" % len(res["nomikomi"]))
        for n in res["nomikomi"]:
            print("  ・%s … %s" % (n["who"], n["mark"]))
        print("")
    print("赤 合計 %s件" % res["redCount"])
    return 0


def asa():
    """毎朝1回。★赤のときだけ知らせる。緑なら1文字も書かない。"""
    res = collect()
    _save(OUT, dict(at=datetime.now(JST).isoformat(), **res))

    now = datetime.now(JST)
    # 朝に1回だけ。夜中に鳴らさない（--now を付ければ今すぐ試せる）
    if now.hour < 7 and "--now" not in sys.argv:
        return 0
    today = now.strftime("%F")
    st = _load(ASA_STATE, {}) or {}
    if st.get("lastDay") == today:
        return 0                      # 1日1回だけ
    st["lastDay"] = today
    _save(ASA_STATE, st)

    if not res.get("ok"):
        text = "【開通】" + res["why"]
    elif not res.get("redCount"):
        return 0                      # ★緑なら黙る
    else:
        parts = []
        for k in res.get("redKeys", []):
            parts.append("・%s … %s" % (k["what"], k["detail"]))
        for w in res.get("karamawari", []):
            parts.append("・%s … 走った%d回で取れた0回（%s）"
                         % (w["label"], w["runs"], w["blocked"] or w["why"]))
        for m in res.get("missing", []):
            parts.append("・%s … 台帳に載っていません（誰も見ていない口）" % m)
        text = ("【開通】いま閉じている口が %d件あります。\n%s\n"
                "押すだけの一覧 → share/check/1029-kaitsuu.html"
                % (res["redCount"], "\n".join(parts[:12])))
    try:
        os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now(JST).isoformat(),
                                "from": "kaitsuu", "text": text},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass
    print(text)
    return 0


def self_test():
    ng = 0
    res = collect()
    if not isinstance(res, dict):
        print("✕ collect() が辞書を返さない"); ng += 1
    for key in ("ok", "keys", "karamawari", "nomikomi", "missing"):
        if key not in res:
            print("✕ %s が無い" % key); ng += 1
    # ★飲み込みの印を取りこぼしていないか（形で確かめる）
    for w in ("no_credential", "401", "403", "skip"):
        if w not in NOMIKOMI:
            print("✕ 印 %s を見ていない" % w); ng += 1
    print("自己試験 %s" % ("合格" if ng == 0 else "不合格 %d件" % ng))
    return 1 if ng else 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if "--asa" in sys.argv:
        return asa()
    res = collect()
    _save(OUT, dict(at=datetime.now(JST).isoformat(), **res))
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    return show(res)


if __name__ == "__main__":
    sys.exit(main())
