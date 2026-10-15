#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
895番：【仕組み④】他のAIとつながる — 外に出した仕事の台帳＋お金の見張り。

背景（たまごさんの言葉 2026-09-16）：
  「もう一回言うけど、仕組み作りが1番大事だからね。」
  「他のAIとの連携がどんどんスムーズになる仕組み。工場が回り続ける仕組み。」

問題：どのAIに何を頼んだか、どこまで進んだかが1か所に無く、たまごさんが覚えている状態だった。
   実害：Devinで$0.99使ったのを、たまごさんが先にクレジット消費に気づいて一時停止させた
   （devin-13ab0ee3d02e49a2893af8d14dade1e3「joy-relief-station unused cleanup」）。

台帳: status/gaibu.json（正本・git管理）
表示: money.html「🤝 外に出した仕事」セクション／index.html 進捗表の1行

外に出す基準（このファイルが実装として体現する判断基準）：
  出してよい：正解が機械で測れるもの（ビルドが通る／件数が数えられる／サイズが減る）
  出さない：仕様が固まっていないもの（見た目・コピー・たまごさんの好み）
  → 間違った仕様を外注すると、間違ったものが速くできるだけ（今日の教訓）。

使い方（CLI）:
  python3 tools/gaibu_ledger.py --sync-devin
      Devin APIのsessions一覧を取り込み、items（ai=Devin分）をマージ更新する。
      新しくPRが見つかった項目は status/dispatch_outbox.jsonl へ1行通知する（冪等）。

  python3 tools/gaibu_ledger.py --add --ai ChatGPT --what "曲コピーの下書き100本" \
      --status requested [--url URL] [--cost-usd 0] [--note "..."]
      ChatGPT/Grokなど、APIで自動取得できないAIへ依頼した時に手で1件記録する。

  python3 tools/gaibu_ledger.py --summary
      件数・費用合計（AI別・円）をJSONで標準出力する（進捗表からも直接 status/gaibu.json を読める）。

Devin APIの使用量（コスト）について（2026-09-16に実機確認済み）：
  /v1/usage, /v1/billing, /v1/account, /v1/organization/usage, /v1/usage/summary は
  いずれも404で存在しない。セッション一覧・詳細レスポンスにも ACU/コスト情報は含まれない。
  → costUsd はAPIから自動取得できない。手動記録（--add の --cost-usd、または既存項目への
     --update-cost）でのみ埋まる。空欄は「未申告」であり0円ではない（他の台帳の既存方針と同一）。
"""
import argparse
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LEDGER = os.path.join(REPO, "status", "gaibu.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
ENV_PATH = os.path.join(REPO, ".env")

# 為替換算はfal_cost_ledger.pyと同じ暫定レート（実測記録が無い時だけ使う概算）。
USD_TO_YEN_FALLBACK = 150.0

# 月間の暫定上限（AI別・USD）。具体額の出典が無いため「使いすぎに気づける」目的でAI側が暫定設定。
# 実績を見ながらこの定数を書き換えれば反映される（fal_cost_ledger.pyの方針と同一）。
DEFAULT_MONTHLY_CAP_USD = {"Devin": 20.0, "ChatGPT": 10.0, "Grok": 10.0}

AI_LIST = ["Devin", "ChatGPT", "Grok"]
STATUS_LABELS = {
    "requested": "依頼中",
    "running": "作業中",
    "pr_open": "PR待ち",
    "done": "完了",
    "failed": "失敗",
    "stopped": "一時停止",
}


def now_jst():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def load_devin_key():
    if not os.path.exists(ENV_PATH):
        return None
    with io.open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if line.startswith("DEVIN_API_KEY="):
                return line.strip().split("=", 1)[1]
    return None


def load_ledger():
    default = {
        "schemaVersion": 1,
        "purpose": (
            "895番：外に出した仕事の台帳＋お金の見張り。誰に／何を／いつ出した／今の状態／"
            "結果URL／使った金額を1か所に集約し、たまごさんが覚えておく必要をゼロにする。"
        ),
        "policy": {
            "outsourceOk": "正解が機械で測れるもの（ビルドが通る／件数が数えられる／サイズが減る）",
            "outsourceNg": "仕様が固まっていないもの（見た目・コピー・たまごさんの好み）",
            "lesson": "間違った仕様を外注すると、間違ったものが速くできるだけ（2026-09-16）",
        },
        "monthlyCapUsd": dict(DEFAULT_MONTHLY_CAP_USD),
        "usdToYenFallback": USD_TO_YEN_FALLBACK,
        "items": [],
        "notifiedPrIds": [],
    }
    if not os.path.exists(LEDGER):
        return default
    try:
        with io.open(LEDGER, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in default.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return default


def _atomic_save(data):
    tmp = LEDGER + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LEDGER)


def compute_summary(data):
    items = data.get("items") or []
    rate = data.get("usdToYenFallback", USD_TO_YEN_FALLBACK)
    by_ai = {}
    for ai in AI_LIST:
        ai_items = [it for it in items if it.get("ai") == ai]
        cost_usd = round(sum(it.get("costUsd") or 0 for it in ai_items), 4)
        cap = (data.get("monthlyCapUsd") or {}).get(ai, DEFAULT_MONTHLY_CAP_USD.get(ai, 0))
        by_ai[ai] = {
            "count": len(ai_items),
            "openCount": len([it for it in ai_items if it.get("status") in ("requested", "running", "pr_open")]),
            "costUsd": cost_usd,
            "costYen": round(cost_usd * rate, 0),
            "capUsd": cap,
            "capYen": round(cap * rate, 0),
            "warn": cap > 0 and cost_usd >= cap * 0.8,
            "over": cap > 0 and cost_usd >= cap,
        }
    total_cost_usd = round(sum(v["costUsd"] for v in by_ai.values()), 4)
    return {
        "totalCount": len(items),
        "openCount": sum(v["openCount"] for v in by_ai.values()),
        "totalCostUsd": total_cost_usd,
        "totalCostYen": round(total_cost_usd * rate, 0),
        "byAi": by_ai,
    }


def sync_devin(data, quiet=False):
    key = os.environ.get("DEVIN_API_KEY") or load_devin_key()
    if not key:
        if not quiet:
            print("DEVIN_API_KEYが.envに見つかりません。Devin分の同期はスキップします。")
        return data, []

    req = urllib.request.Request(
        "https://api.devin.ai/v1/sessions",
        headers={"Authorization": "Bearer %s" % key},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            payload = json.load(res)
    except urllib.error.HTTPError as e:
        if not quiet:
            print("Devin APIエラー %s" % e.code)
        return data, []
    except Exception as e:
        if not quiet:
            print("Devin APIに繋がりませんでした: %s" % e)
        return data, []

    sessions = payload.get("sessions") or []
    items = data.get("items") or []
    by_id = {it.get("id"): it for it in items if it.get("ai") == "Devin"}
    notified = set(data.get("notifiedPrIds") or [])
    new_pr_events = []

    for s in sessions:
        sid = s.get("session_id") or ""
        if not sid:
            continue
        status_enum = s.get("status_enum") or s.get("status") or "?"
        status_map = {
            "finished": "done",
            "running": "running",
            "blocked": "running",
            "suspended": "stopped",
        }
        status = status_map.get(status_enum, status_enum)
        pr = s.get("pull_request") or {}
        pr_url = pr.get("url") if isinstance(pr, dict) else None
        if pr_url:
            status = "pr_open" if status != "done" else "done"

        existing = by_id.get(sid)
        item = existing or {
            "id": sid,
            "ai": "Devin",
            "costUsd": None,
            "costSource": "api_unavailable",
            "note": "",
        }
        item["what"] = s.get("title") or item.get("what") or "(無題)"
        item["requestedAt"] = s.get("created_at") or item.get("requestedAt")
        item["updatedAt"] = s.get("updated_at") or item.get("updatedAt")
        item["status"] = status
        item["resultUrl"] = pr_url or ("https://app.devin.ai/sessions/%s" % sid)
        item["sessionUrl"] = "https://app.devin.ai/sessions/%s" % sid

        if pr_url and sid not in notified:
            new_pr_events.append({"id": sid, "title": item["what"], "prUrl": pr_url})
            notified.add(sid)

        by_id[sid] = item

    other_items = [it for it in items if it.get("ai") != "Devin"]
    data["items"] = other_items + list(by_id.values())
    data["notifiedPrIds"] = sorted(notified)
    return data, new_pr_events


def notify_pr(events):
    """新しく見つかったDevinのPRをDispatchの受信箱(dispatch_outbox.jsonl)へ1行ずつ通知する。"""
    if not events:
        return
    with io.open(OUTBOX, "a", encoding="utf-8") as f:
        for ev in events:
            line = {
                "ts": now_jst(),
                "n": "gaibu-%s" % ev["id"][:12],
                "type": "gaibu_pr",
                "title": "【外部AI】Devinのプルリクエストが出ました：%s" % ev["title"],
                "message": "🤝Devinが作業を終え、PRを出しました：%s\n%s" % (ev["title"], ev["prUrl"]),
                "urls": [ev["prUrl"]],
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def add_manual(data, ai, what, status="requested", url=None, cost_usd=None, note=""):
    if ai not in AI_LIST:
        raise SystemExit("--ai は %s のどれかにしてください" % ", ".join(AI_LIST))
    raw = "%s|%s|%s" % (ai, what, datetime.now().strftime("%Y-%m-%d"))
    item_id = "%s-%s" % (ai.lower(), hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10])
    items = data.get("items") or []
    item = {
        "id": item_id,
        "ai": ai,
        "what": what,
        "requestedAt": now_jst(),
        "updatedAt": now_jst(),
        "status": status if status in STATUS_LABELS else "requested",
        "resultUrl": url,
        "costUsd": cost_usd,
        "costSource": "manual" if cost_usd is not None else None,
        "note": note or "",
    }
    items.append(item)
    data["items"] = items
    return data, item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync-devin", action="store_true")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--update-cost", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--ai")
    ap.add_argument("--what")
    ap.add_argument("--status", default="requested")
    ap.add_argument("--url")
    ap.add_argument("--cost-usd", type=float)
    ap.add_argument("--note", default="")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    data = load_ledger()
    changed = False

    if args.sync_devin:
        data, events = sync_devin(data, quiet=args.quiet)
        notify_pr(events)
        changed = True
        if not args.quiet and events:
            print("Devinの新しいPRを%d件、Dispatchへ通知しました" % len(events))

    if args.add:
        if not args.ai or not args.what:
            raise SystemExit("--add には --ai と --what が必須です")
        data, item = add_manual(
            data, args.ai, args.what, status=args.status, url=args.url,
            cost_usd=args.cost_usd, note=args.note,
        )
        changed = True
        if not args.quiet:
            print("台帳に追加しました: %s" % item["id"])

    if args.update_cost:
        if not args.id or args.cost_usd is None:
            raise SystemExit("--update-cost には --id と --cost-usd が必須です")
        items = data.get("items") or []
        found = False
        for it in items:
            if it.get("id") == args.id:
                it["costUsd"] = args.cost_usd
                it["costSource"] = "manual"
                if args.note:
                    it["note"] = args.note
                it["updatedAt"] = now_jst()
                found = True
                break
        if not found:
            raise SystemExit("id %s が台帳に見つかりません" % args.id)
        data["items"] = items
        changed = True
        if not args.quiet:
            print("金額を更新しました: %s = $%.2f" % (args.id, args.cost_usd))

    if changed:
        data["updatedAt"] = now_jst()
        data["summary"] = compute_summary(data)
        _atomic_save(data)

    if args.summary or not (args.sync_devin or args.add):
        data["summary"] = compute_summary(data)
        print(json.dumps(data["summary"], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
