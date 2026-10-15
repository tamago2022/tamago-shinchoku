#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1038番（2026-09-23）「毎日やること」の専用の口。

■ なぜ作り替えたか（同じ形の壊れ方が今日3回目だったから）
  756番の仕組みは「毎朝の入荷見回り」を**発車待ちの列に1件ずつ積んで**いた。
  積む係は11日ぶん全部動いていた（788/818/844/877/903/938/948/977/1004/1016/1037）。
  なのに **1本も走っていない**。理由は簡単で、発車待ちが164件あって、
  毎日やることを優先度3で最後尾に積んでいたから。**永遠に順番が来ない。**

  ここを「優先度を上げる」で直すと、明日また同じことが起きる（今日3回目）。
  だから**パイプごと替える**：毎日やることは列に積まない。
  コピー直し（tools/gaibu_copy_naoshi.py）と同じく、**1日1回ゲートで自分で走る。**
  新しい常駐は増やさない（心臓 heartbeat.sh に相乗り）。

■ ★棚（Lovable / Supabase の admin_stock）の扱い
  たまごさんの実測で、棚の編集は28秒待っても開かない（share/check/1028-omosa.html）。
  だから **ここは棚に1文字も書かない。**
    ・拾う（GETだけ）・調べる・下書きを作る → ここまで自動
    ・棚に書き込む最後の1歩            → 「押すだけ」でたまごさんの前に出す
  出し先は status/public/mainichi_oshidake.json（この口が持ち主の1本）。
  ★status/public/uketori_machi.json には相乗りしない。あれは tools/baton.py が
    毎回まるごと書き直す持ち物なので、ここから足しても次の回に消える（実装を読んで確認）。

■ 判定の基準を新しく発明しない
  手つかず／水道水の判定は tools/gaibu_copy_nippou.py の judge() をそのまま呼ぶ。
  ★機械で言い切れないもの（絵と文字が合っているか等）は「未判定」と書く。想像で埋めない。

使い方:
  python3 tools/mainichi_kuchi.py            … 1日1回だけ本体が走る（何度呼んでもよい）
  python3 tools/mainichi_kuchi.py --force    … ゲートを無視して今すぐ走る
  python3 tools/mainichi_kuchi.py --show     … 前回の下書きを見る
"""
import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_copy_nippou as nippou  # noqa: E402  ★基準はあちらが正本。2か所に書かない。

JST = timezone(timedelta(hours=9))
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_JSON = os.path.join(PUBLIC, "mainichi_kuchi.json")
OSHIDAKE = os.path.join(PUBLIC, "mainichi_oshidake.json")
GATE = os.path.join(STATUS, ".mainichi_kuchi_last")
LOCK = os.path.join(STATUS, ".mainichi_kuchi.lock")

MORNING_HOUR = 6          # 朝6時以降の最初の便で走る（naoshi と同じ）
LOCK_STALE_SEC = 60 * 60  # 60分以上握ったままのロックは詰まりとみなす
DEADLINE_SEC = 5 * 60     # 1回の持ち時間。Macを占有し続けない
LOOKBACK_DAYS = 2         # 昨日ぶんを見る（取りこぼさないよう2日）


def now():
    return datetime.now(JST)


# ---------------------------------------------------------------- ロック
def lock_take():
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip() or 0)
        except Exception:
            pid = 0
        alive = False
        if pid:
            try:
                os.kill(pid, 0)
                alive = True
            except OSError:
                alive = False
        if alive and (time.time() - os.path.getmtime(LOCK)) < LOCK_STALE_SEC:
            return False
        try:
            os.remove(LOCK)
        except OSError:
            pass
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return False


def lock_free():
    try:
        os.remove(LOCK)
    except OSError:
        pass


# ---------------------------------------------------------------- 本体
def gather(deadline):
    """棚から GET だけで拾って、下書きを作る。★書き戻さない。"""
    out = {
        "ranAt": now().strftime("%Y-%m-%d %H:%M"),
        "source": None, "sourceNote": "", "diag": [], "red": [],
        "seen": 0, "drafts": [], "mihantei": [],
    }
    url, key, keyname, where = nippou.find_supabase(out["diag"])
    if not url:
        out["source"] = "取れていない"
        out["red"].append("正本（admin_stock）に手が届かない：" + where)
        return out
    out["source"] = "admin_stock"
    out["sourceNote"] = "admin_stock（鍵：%s・%s／★GETだけ）" % (keyname, where)

    since = (now() - timedelta(days=LOOKBACK_DAYS)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    try:
        rows = nippou.fetch_stock(url, key, since.isoformat())
    except Exception as e:  # noqa: BLE001
        out["red"].append("admin_stock から取れませんでした（%s）" % type(e).__name__)
        return out
    out["seen"] = len(rows)

    for row in rows:
        if time.time() > deadline:
            out["red"].append("持ち時間（%d秒）を使い切ったので途中で止めました" % DEADLINE_SEC)
            break
        title = nippou.pick(row, ("title", "song_title", "name"))
        copy = nippou.pick(row, ("whisper", "copy", "comment", "description"))
        why = nippou.judge(title, copy)
        if why:
            out["drafts"].append({
                "id": row.get("id"),
                "title": title,
                "now": copy,
                "why": why,
                "kind": nippou.pick(row, ("kind", "type", "source")) or "",
                "createdAt": nippou.pick(row, ("created_at",)) or "",
                # ★書き直し文はここでは作らない。文を作るのは naoshi の仕事（口を2つにしない）。
                "next": None,
            })
        # ★絵と文字が合っているかは、文字合わせでは言い切れない。
        #   「合っていない」と言うにはAIに絵を見せる必要があるので、ここでは未判定と書く。
        img = nippou.pick(row, ("image_url", "thumbnail_url", "thumb_url", "image"))
        if not img:
            out["mihantei"].append({"id": row.get("id"), "title": title,
                                    "why": "絵のURLが空（絵と文字が合っているかは未判定）"})
    return out


def to_oshidake(res):
    """棚に書く最後の1歩を「押すだけ」の形で並べる。★ここでも棚には書かない。"""
    items = []
    for d in res.get("drafts", []):
        items.append({
            "id": d["id"],
            "title": d["title"],
            "why": d["why"],
            "now": d["now"],
            "how": ("tools/gaibu_copy_naoshi.py が書き直し文を作って棚へ戻します。"
                    "今すぐやるなら status/.gaibu_copy_naoshi_force を置いてください"),
        })
    body = {
        "generatedAt": res.get("ranAt"),
        "rule": "★拾う・調べる・下書きまでが自動。棚へ書く1歩は自動にしない",
        "count": len(items),
        "items": items,
        "mihantei": res.get("mihantei", []),
    }
    os.makedirs(PUBLIC, exist_ok=True)
    with io.open(OSHIDAKE, "w", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False, indent=1))
    return len(items)


def run(force=False):
    today = now().strftime("%Y-%m-%d")
    if not force:
        if now().hour < MORNING_HOUR:
            return {"skipped": "朝%d時前" % MORNING_HOUR}
        try:
            if io.open(GATE, encoding="utf-8").read().strip()[:10] == today:
                return {"skipped": "今日はもう走りました"}
        except OSError:
            pass
    if not lock_take():
        return {"skipped": "前の回がまだ握っています"}
    try:
        res = gather(time.time() + DEADLINE_SEC)
        res["oshidake"] = to_oshidake(res)
        os.makedirs(PUBLIC, exist_ok=True)
        with io.open(OUT_JSON, "w", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False, indent=1))
        # ★取れなかった日はゲートを押さない。「走ったことにして黙る」のが一番まずい。
        if res.get("source") == "admin_stock":
            with io.open(GATE, "w", encoding="utf-8") as f:
                f.write(today)
        return res
    finally:
        lock_free()


def run_job(payload):
    """工場側（gaibu_runner kind=mainichi）から呼ばれる入口。"""
    res = run(force=bool((payload or {}).get("force")))
    res["totalYen"] = 0.0
    res["ok"] = not res.get("red") and not res.get("skipped")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.show:
        try:
            print(io.open(OUT_JSON, encoding="utf-8").read())
        except OSError:
            print("まだ1回も走っていません")
        return 0
    print(json.dumps(run(force=a.force), ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
