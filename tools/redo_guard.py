#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""797番：やり直し合計2回で自動発車を止める共通ガード。

たまごさんの言葉（2026-09-13）：
  「クロマティはもっとバンバンタスク常に回し続けてバンバンさばいてたし、
   クレジットこんなビクビク気にしないでよかったよ。」
  「まず同じことを2回やって、絶対に厳守して、タスクを殴らせないってこと。」

実測（status/queue.json・status/cost_by_task.json）：
  769番＝11回・686番＝8回（$22.31）・771番＝6回・770番＝5回・741/723/464/513番＝各5回。
既存の3つの仕組み（679番のredoCount＝URLなし自動やり直し／416番のaiVerifyFailCount＝
AI検品NG／680番のownerRedoCount＝たまごさんの「直ってない」指摘）は、それぞれ**単独では**
3回目でようやく人の目へ回す設計だった。3つを別々に見ていたせいで、合計では大きく回って
いても個々のカウンタは常に3未満のまま、という抜け道があった。

ここでは3つの合計が2に達した時点で、理由（reasons）を残しつつ status を "stuck" にして
自動発車の対象から外す（auto_launcher.py の launchable フィルタは status=="waiting" だけを
拾うので、"stuck" という値を1つ増やすだけで自然に除外される＝新しい安全弁を足すだけでよい）。

停止したことは必ず dispatch_outbox.jsonl と status/failures.md の両方に残す
（「止まっていました」ではなく「止まっていたので止めました」を最初から出せる状態にする）。
"""
import io
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUCK_REDO_TOTAL = 2   # ここが797番の核。3ではなく2で止める。


def redo_total(it):
    """カウンタの合計（Noneは0扱い）。この数字が2に達したらstuck化する。
    800番：3段検品の2段目「触る検品」（touchCheckFailCount）も同じ合計へ合流させる。
    ここに合流させないと、触る検品だけで無限にやり直しループする穴が残るため。"""
    return (int(it.get("redoCount") or 0)
            + int(it.get("ownerRedoCount") or 0)
            + int(it.get("aiVerifyFailCount") or 0)
            + int(it.get("touchCheckFailCount") or 0))


def note_fail_reason(it, reason):
    """このやり直しの理由を1行、failReasonsへ積む（stuck化した時にDispatchへ渡す材料）。
    直近5件だけ保持すれば十分（古い理由まで見せてもDispatchは読み切れない）。"""
    reasons = list(it.get("failReasons") or [])
    reasons.append((reason or "(理由不明)").strip()[:200])
    it["failReasons"] = reasons[-5:]


def should_stuck(it):
    return redo_total(it) >= STUCK_REDO_TOTAL


def mark_stuck(it, log=None):
    """status を stuck にし、dispatch_outbox.jsonl・failures.md へ1回だけ記録する。
    呼び出し側はこの直後に status を "waiting"/"hold" 等で上書きしないこと
    （このまま queue.json へ保存されて初めて実際に自動発車から外れる）。"""
    n = it.get("n")
    title = it.get("title") or it.get("label") or ""
    total = redo_total(it)
    reasons = it.get("failReasons") or []
    reason_text = " ／ ".join(reasons[-2:]) if reasons else "(理由の記録なし・件数だけ2回に到達)"
    it["status"] = "stuck"
    it["stuckAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    it["stuckReasonSummary"] = reason_text
    it["stuckRedoTotal"] = total
    message = (
        "🛑%s番「%s」、2回やって同じ所で落ちています。"
        "手段を変えるか、要件を1行決めてください。理由：%s"
        % (n, title, reason_text)
    )
    try:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "n": "%s-stuck" % n,
            "type": "stuck_escalation",
            "title": title,
            "message": message,
            "redoTotal": total,
            "reasons": reasons,
        }
        with io.open(os.path.join(REPO, "status", "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        with io.open(os.path.join(REPO, "status", "failures.md"), "a", encoding="utf-8") as f:
            f.write(
                "\n\n---\n\n## 797番自動記録：%s番「%s」がやり直し合計%d回でstuckになった\n\n"
                "- **症状**：redoCount＋ownerRedoCount＋aiVerifyFailCountの合計が%dに達しました。\n"
                "- **理由**：%s\n"
                "- **対応**：自動発車の対象から外しました（status=stuck）。"
                "手段を変えるか要件を1行決めてから、進捗表の🛑手を止めた仕事から列へ戻してください。\n"
                "- **日付**：%s\n"
                % (n, title, total, reason_text, time.strftime("%Y-%m-%d %H:%M"))
            )
    except Exception:
        pass
    if log:
        try:
            log("🛑 stuck化 %s番「%s」（合計%d回・理由:%s）" % (n, title, total, reason_text))
        except Exception:
            pass
    return message
