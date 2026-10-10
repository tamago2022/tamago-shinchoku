#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gensparkに頼んで、答えを持ち帰る1本（2026-10-09・弾き語り特集で実測して作った）。

たまごさん：「Gensparkとはもうつながった」「許可なしで普通に行き来できるように」

■ 道（ブラウザもポップアップも使わない）
  サンドボックス → status/gaibu_jobs/pending/ に票を置く（kind="gsk"）
  → 工場（Mac）の代行係 gaibu_runner.py が1〜2分おきに拾い、Macに入っている
    Genspark公式CLI `gsk`（ログイン済み）で `task create` を叩く
  → 同じ道で `task status` / `task info` を叩いて、答えの本文を持ち帰る
  ★APIキーもChromeも要らない。たまごさんの操作は0回。
  ★実測 2026-10-09：deep_research 1件 約5分で完了／super_agent（検品）1件 約10分で完了。

■ 使い方（サンドボックスからでもMacからでも同じ）
  python3 tools/genspark_tanomu.py --type deep_research --name "弾き語り 調査" --q-file q.txt --out status/xxx.md
  python3 tools/genspark_tanomu.py --type super_agent   --name "検品" --q "…" --out status/yyy.md
  --wait 秒（既定420）。終わらなければ project_id を出して終わる（後から --project で回収できる）。
  ★2026-10-09：既定を1500→420秒に下げた。Cowork の bash は1回600秒で切られるので、
    1500秒待つと呼んだ側ごと落ちていた（＝「Gensparkが落ちる」の正体の1つ）。
    待ち切れなくても困らない：出した瞬間に status/gsk/irai.jsonl に問いと --out を残すので、
    工場の起こし役（tools/okoshi.py・心臓から5分おき）が答えを --out へ回収する。
    回収に2回失敗／90分終わらない時は、起こし役が同じ問いを1回だけ出し直す。
  python3 tools/genspark_tanomu.py --project <project_id> --out status/yyy.md   # 回収だけ
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from shigoto_queue import enqueue_job, wait_job  # noqa: E402


def _job(payload, wait=420):
    jid = enqueue_job("gsk", payload)
    return wait_job(jid, wait_sec=wait, poll=5)


def kaishuu(pid):
    r = _job({"op": "shigoto_miru", "sub": "info", "id": pid, "timeoutSec": 150})
    if not r or not r.get("ok"):
        return None, "info が取れない：%s" % ((r or {}).get("error") or "時間切れ")
    d = (json.loads(r.get("stdout") or "{}").get("data") or {})
    if d.get("state") not in ("finished", "succeeded", "completed"):
        return None, "まだ終わっていない（state=%s）" % d.get("state")
    c = (d.get("result_content") or {}).get("content")
    t = "\n".join(c) if isinstance(c, list) else (c or "")
    return (t or None), ("" if t else "答えが空（Gensparkが質問で止まった可能性）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", default="deep_research",
                    choices=["deep_research", "super_agent", "website", "docs"])
    ap.add_argument("--name", default="Claudeから")
    ap.add_argument("--q")
    ap.add_argument("--q-file")
    ap.add_argument("--instructions", default="日本語で。出典URLを必ず付ける。推測は推測と明記。")
    ap.add_argument("--out")
    ap.add_argument("--wait", type=int, default=420)
    ap.add_argument("--project")
    a = ap.parse_args()

    pid = a.project
    if not pid:
        q = a.q or (io.open(a.q_file, encoding="utf-8").read() if a.q_file else "")
        if not q.strip():
            sys.exit("--q か --q-file が要ります")
        r = _job({"op": "shigoto_dasu", "taskType": a.type, "query": q,
                  "instructions": a.instructions, "taskName": a.name, "timeoutSec": 200})
        if not r or not r.get("ok"):
            sys.exit("出せなかった：%s" % ((r or {}).get("error") or "工場が拾わない（時間切れ）"))
        pid = r.get("projectId")
        print("GENSPARK 受付: project=%s" % pid, flush=True)
        # 起こし役（tools/okoshi.py）が後から回収・出し直しできるように、問いと置き場所を残す
        try:
            led = os.path.join(REPO, "status", "gsk", "irai.jsonl")
            os.makedirs(os.path.dirname(led), exist_ok=True)
            out_rel = os.path.relpath(os.path.abspath(a.out), REPO) if a.out else None
            io.open(led, "a", encoding="utf-8").write(json.dumps(
                {"pid": pid, "type": a.type, "name": a.name, "q": q[:20000], "out": out_rel,
                 "at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    end = time.time() + a.wait
    while True:
        t, why = kaishuu(pid)
        if t:
            break
        if time.time() > end:
            print("GENSPARK 未完: project=%s（%s）。起こし役が5分おきに見に行き、終わり次第 %s へ回収します"
                  % (pid, why, a.out or ("status/gsk/kaishuu/%s.md" % pid)))
            sys.exit(2)
        time.sleep(60)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        io.open(a.out, "w", encoding="utf-8").write(
            "<!-- Genspark %s の答え原文（要約なし）project=%s -->\n%s" % (a.type, pid, t))
        print("GENSPARK 完了: %s（%d字）" % (a.out, len(t)))
    else:
        print(t)


if __name__ == "__main__":
    main()
