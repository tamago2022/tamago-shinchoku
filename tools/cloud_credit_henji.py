#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""クラウドセッションクレジット($248・11/5 16:59 JST期限)の問い合わせの返事を見張る（2026-10-15）

━━ なぜ ━━
  たまごさん「ずっと減らない。どうやって使うのか運営に問い合わせて」（10回近く言われた）。
  2026-10-15 03:49 JST に support@anthropic.com へ送信（Gmail threadId 1a13bbf5804e4282）。
━━ 仕組み ━━
  シェルは Gmail を読めない（鍵を工場に置かない）。だから「気づく役」は心臓、「読む役」は Dispatch（Gmailコネクタ）。
  心臓が4時間おきに呼ぶ → 1日1回だけ status/dispatch_outbox.jsonl に1行
  「Gmail で threadId 1a13bbf5804e4282 に返事が来たか見て、来たら要点をたまごさんへ」。
  返事を読んだら `--done "要点"` で止める（status/cloud_credit/henji.json）。期限(11/5)を過ぎたら自動で止まる。
  AIを呼ばない・外へ出ない＝0円。
━━ 使い方 ━━
  python3 tools/cloud_credit_henji.py            # 1日1回 outbox に1行
  python3 tools/cloud_credit_henji.py --done "要点"
  python3 tools/cloud_credit_henji.py --self-test
"""
import io, json, os, sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status", "cloud_credit")
STATE = os.path.join(ST, "henji.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
JST = timezone(timedelta(hours=9))
THREAD = "1a13bbf5804e4282"
KIGEN = datetime(2026, 11, 5, 16, 59, tzinfo=JST)


def load(p):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {}


def save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(json.dumps(o, ensure_ascii=False, indent=1))


def tick(now, state_p=STATE, outbox_p=OUTBOX):
    s = load(state_p)
    if s.get("done") or now > KIGEN:
        return "stop"
    today = now.strftime("%Y-%m-%d")
    if s.get("last") == today:
        return "skip"
    line = {"ts": now.isoformat(timespec="seconds"), "n": "cloud-credit-henji", "type": "gmail_henji_mihari",
            "title": "クラウドクレジット問い合わせの返事を確認",
            "message": f"Gmail search_threads で threadId {THREAD}（件名 'Cloud session credit ($248 of $250 left)'）に support@mail.anthropic.com から返事が来たか見る。"
                       f"来ていたら要点3行をたまごさんへ送り、`python3 tools/cloud_credit_henji.py --done \"要点\"` で止める。期限 11/5 16:59 JST。"}
    os.makedirs(os.path.dirname(outbox_p), exist_ok=True)
    io.open(outbox_p, "a", encoding="utf-8").write(json.dumps(line, ensure_ascii=False) + "\n")
    s["last"] = today
    save(state_p, s)
    return "wrote"


def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    sp, op = os.path.join(d, "s.json"), os.path.join(d, "o.jsonl")
    t = datetime(2026, 10, 16, 9, 0, tzinfo=JST)
    assert tick(t, sp, op) == "wrote"
    assert tick(t, sp, op) == "skip"
    assert tick(t + timedelta(days=1), sp, op) == "wrote"
    assert tick(datetime(2026, 11, 6, tzinfo=JST), sp, op) == "stop"
    save(sp, {"done": "x"})
    assert tick(t + timedelta(days=3), sp, op) == "stop"
    print("self-test OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--self-test"]:
        self_test()
    elif a[:1] == ["--done"]:
        s = load(STATE); s["done"] = " ".join(a[1:]) or "返事確認済み"
        s["done_at"] = datetime.now(JST).isoformat(timespec="seconds"); save(STATE, s); print("done")
    else:
        print(tick(datetime.now(JST)))
