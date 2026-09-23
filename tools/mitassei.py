#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""未達成の総数を機械で数える（★概算）。

━━ なぜ作ったか（2026-09-24・1054番・たまごさん）━━

  「指示したことが全部終わってるって言うんだったらいいんだよ。
    未達成のものが何百とあるんじゃないの？
    『あれはどうなった、これはどうなった』って、
    いちいち俺が調べて、俺が言わないといけないの。」

  ＝ たまごさんが「あれどうなった？」と聞かなくて済む状態にする。
    そのために必要なのは、報告の文章ではなく **機械が毎日数える1つの数字**。

━━ 出す数字は3つだけ（増やさない）━━

  ① 未達成は全部で◯件
  ② そのうち、こちらだけで終わらせられるのが◯件
  ③ たまごさんにしか押せないのが◯件

  ★全部「概算」。数え方を下に全部書く。手で書いた数字は1つも無い。

━━ 数える場所（これ以外は数えない）━━

  A  status/queue.json       status が done/merged 以外の仕事票
  B  status/queue.json       完了記録（dispatch_outbox.jsonl の ok:true）が無い票
  C  status/daicho.json      潰していない行（＝言われたのに治っていない依頼そのもの）
  D  status/queue.json       題名が重複している票（＝何度も頼まれて何度も落ちた）

  ★A〜Dは重なる。重なりは題名で寄せて1件に数える（二重計上しない）。

━━ ②と③の分け方（機械の条件だけ。人が決めない）━━

  たまごさんにしか押せない ＝ 次のどれかに当たるもの
    ・needsOwnerJudgment が true
    ・costsMoney が true で costApproved が無い（＝金が出る）
    ・題名か中身に「押せない言葉」が入っている
      （鍵・ログイン・契約・課金・プラン・同意・ドメイン・service role・貼る・買う）
  それ以外は全部「こちらだけで終わらせられる」側に倒す。
  ★迷ったら「こちら」に倒す。たまごさんの手を増やす側には倒さない。

━━ 赤の条件（Dispatchにだけ知らせる。たまごさんには出さない）━━

  ・件数が前日より増えた
  ・一番古いものが7日を超えた

━━ 使い方 ━━

    python3 tools/mitassei.py              # 数えて3行出す
    python3 tools/mitassei.py --json       # 機械向け
    python3 tools/mitassei.py --kaku       # status/public/mitassei.json に書く（心臓から呼ぶ）
    python3 tools/mitassei.py --self-test  # 数え方が壊れていないか
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "status", "queue.json")
OUTBOX = os.path.join(ROOT, "status", "dispatch_outbox.jsonl")
DAICHO = os.path.join(ROOT, "status", "daicho.json")
OUT = os.path.join(ROOT, "status", "public", "mitassei.json")

OWARI = {"done", "merged"}  # これだけが「終わった」

# たまごさんにしか押せない言葉（これに当たったら③へ）
TAMAGO_KOTOBA = [
    # ★「キー」単体は入れない。「ホットキー」「モンキー」で誤って拾う（2026-09-24 実測）
    "鍵", "api key", "apikey", "api鍵", "token", "service role", "service_role",
    "ログイン", "login", "sign in", "サインイン", "認証", "oauth", "同意",
    "契約", "課金", "支払", "有料", "プラン", "購入", "買", "クレジット",
    "ドメイン", "貼っ", "貼る", "貼り", "secrets", "secret",
]


def _now() -> datetime:
    return datetime.now(JST)


def _norm(s: str) -> str:
    """題名を寄せる（重複を見つけるため）。記号と空白と番号を落とす。"""
    s = (s or "").strip().lower()
    s = re.sub(r"^\s*[\[【(]?\s*(n?\s*=?\s*\d+\s*番?)\s*[\]】)]?\s*[:：]?", "", s)
    s = re.sub(r"[\s　]+", "", s)
    s = re.sub(r"[「」『』【】\[\]()（）・,.。、:：/\\\-—ー_*★☆✅🟡🟠🛑]", "", s)
    return s


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _owari_zumi_n() -> set:
    """dispatch_outbox.jsonl で ok:true が付いた n（＝完了記録がある）。"""
    ok = set()
    try:
        with open(OUTBOX, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("ok") is True and r.get("n") is not None:
                    ok.add(r["n"])
    except FileNotFoundError:
        pass
    return ok


def _tamago_dake(item: dict) -> tuple[bool, str]:
    """たまごさんにしか押せないか。（機械の条件だけ）"""
    if item.get("needsOwnerJudgment") is True:
        return True, "needsOwnerJudgment"
    if item.get("costsMoney") is True and not item.get("costApproved"):
        return True, "金が出る（未承認）"
    # ★題名と「止まっている理由」だけを見る。中身の長文は見ない。
    #   長文には「買う」「貼る」がただの説明として必ず出てくる＝たまごさん待ちが水膨れする。
    hay = " ".join(
        str(item.get(k) or "")
        for k in ("title", "fullTitle", "holdNote", "blockedNote",
                  "stuckReasonSummary", "irai")
    ).lower()
    for w in TAMAGO_KOTOBA:
        if w in hay:
            return True, f"押せない言葉「{w}」"
    return False, ""


def _hi_kara(ts: str) -> int | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=JST)
        return max(0, (_now() - t).days)
    except Exception:
        return None


def kazoeru() -> dict:
    q = _load_json(QUEUE, {"items": []})
    items = q.get("items", []) if isinstance(q, dict) else (q if isinstance(q, list) else [])
    ok_n = _owari_zumi_n()
    d = _load_json(DAICHO, {"rows": []})
    rows = d.get("rows", []) if isinstance(d, dict) else []

    # 題名で寄せる箱。key -> 1件
    ken: dict[str, dict] = {}
    moto = Counter()

    def tsumu(key: str, mi: dict):
        cur = ken.get(key)
        if cur is None:
            ken[key] = mi
        else:
            cur["moto"] = sorted(set(cur["moto"]) | set(mi["moto"]))
            # たまごさん待ちは強い側を残す
            if mi["tamago"] and not cur["tamago"]:
                cur["tamago"] = True
                cur["riyuu"] = mi["riyuu"]
            hi_new, hi_old = mi.get("hi"), cur.get("hi")
            if hi_new is not None and (hi_old is None or hi_new > hi_old):
                cur["hi"] = hi_new

    # A：終わっていない仕事票
    title_count = Counter(_norm(x.get("title") or x.get("fullTitle") or "") for x in items)
    for x in items:
        st = (x.get("status") or x.get("state") or "").lower()
        title = (x.get("title") or x.get("fullTitle") or "").strip()
        key = _norm(title) or f"n{x.get('n')}"
        tam, riyuu = _tamago_dake(x)
        hi = _hi_kara(x.get("createdAt") or x.get("startedAt") or "")
        m = []
        if st not in OWARI:
            m.append(f"A:仕事票 {st or 'なし'}")
            moto["A"] += 1
        # B：完了記録が無い
        if st in OWARI and x.get("n") not in ok_n:
            m.append("B:完了記録なし")
            moto["B"] += 1
        # D：題名が重複
        if key and title_count[key] >= 2:
            m.append(f"D:同じ題名 {title_count[key]}本")
            moto["D"] += 1
        if not m:
            continue
        tsumu(key, {"na": title or f"n={x.get('n')}", "n": x.get("n"), "moto": m,
                    "tamago": tam, "riyuu": riyuu, "hi": hi, "st": st})

    # C：台帳の潰していない行
    for r in rows:
        if r.get("jotai") == "潰した" or r.get("url"):
            continue
        title = (r.get("irai") or "").strip()
        key = _norm(title) or r.get("id") or ""
        if not key:
            continue
        tam, riyuu = _tamago_dake(r)
        if r.get("senshu") == "tamago" or r.get("jotai") == "たまごさんの1手":
            tam, riyuu = True, "台帳がたまごさんの1手にしている"
        moto["C"] += 1
        tsumu(key, {"na": title, "n": None, "moto": [f"C:台帳 {r.get('kaisu')}回"],
                    "tamago": tam, "riyuu": riyuu,
                    "hi": r.get("naotteinai"), "st": r.get("jotai") or ""})

    kensu = list(ken.values())
    tamago = [k for k in kensu if k["tamago"]]
    kochira = [k for k in kensu if not k["tamago"]]
    furui = sorted((k for k in kensu if k.get("hi") is not None),
                   key=lambda k: -k["hi"])

    return {
        "asof": _now().isoformat(timespec="seconds"),
        "gaisan": True,
        "zenbu": len(kensu),
        "kochira": len(kochira),
        "tamago": len(tamago),
        "ichiban_furui": ({"hi": furui[0]["hi"], "na": furui[0]["na"]} if furui else None),
        "moto_naiwake": dict(moto),
        "kazoeta_basho": {
            "A_owatteinai_shigotohyou": moto.get("A", 0),
            "B_kanryou_kiroku_nashi": moto.get("B", 0),
            "C_daicho_tsubushiteinai": moto.get("C", 0),
            "D_onaji_daimei": moto.get("D", 0),
            "note": "A〜Dは重なる。題名で寄せて1件に数えている（＝合計は足し算にならない）",
        },
        "kensu": sorted(kensu, key=lambda k: (-(k.get("hi") or 0), k["na"]))[:200],
    }


def aka(new: dict) -> list[str]:
    """赤の条件。Dispatchにだけ知らせる。"""
    riyuu = []
    old = _load_json(OUT, None)
    if isinstance(old, dict) and isinstance(old.get("zenbu"), int):
        if new["zenbu"] > old["zenbu"]:
            riyuu.append(f"前回より増えた（{old['zenbu']} → {new['zenbu']}件）")
    f = new.get("ichiban_furui")
    if f and (f.get("hi") or 0) > 7:
        riyuu.append(f"一番古いのが{f['hi']}日（7日超）：{f['na'][:40]}")
    return riyuu


def sanko(d: dict) -> str:
    f = d.get("ichiban_furui") or {}
    return (
        f"未達成＝概算{d['zenbu']}件"
        f"（こちらだけで終わるのが{d['kochira']}件／たまごさん待ちが{d['tamago']}件）\n"
        f"一番古いのは{f.get('hi', '?')}日前の「{(f.get('na') or '?')[:48]}」\n"
        f"数えた場所：仕事票{d['kazoeta_basho']['A_owatteinai_shigotohyou']}／"
        f"完了記録なし{d['kazoeta_basho']['B_kanryou_kiroku_nashi']}／"
        f"台帳{d['kazoeta_basho']['C_daicho_tsubushiteinai']}／"
        f"同題名{d['kazoeta_basho']['D_onaji_daimei']}（題名で寄せて重複を外した）"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--kaku", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        assert _norm("【123番】 補給所の本番が古い") == _norm("補給所の本番が古い"), "寄せが壊れている"
        assert _tamago_dake({"title": "Supabaseのservice role鍵が無い"})[0] is True
        assert _tamago_dake({"title": "ページの余白を直す"})[0] is False
        assert _tamago_dake({"costsMoney": True})[0] is True
        assert _tamago_dake({"costsMoney": True, "costApproved": True})[0] is False
        d = kazoeru()
        assert d["zenbu"] == d["kochira"] + d["tamago"], "①≠②+③"
        assert d["zenbu"] > 0
        print(json.dumps({"ok": True, "zenbu": d["zenbu"],
                          "kochira": d["kochira"], "tamago": d["tamago"]},
                         ensure_ascii=False))
        return 0

    d = kazoeru()
    if a.kaku:
        d["aka"] = aka(d)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        print(sanko(d))
        if d.get("aka"):
            print("🔴 " + " / ".join(d["aka"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
