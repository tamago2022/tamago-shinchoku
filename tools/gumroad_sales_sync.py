#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
670番：Gumroadの売上を money.html の「今月の売上」に出す。

.env（リポジトリルート）の GUMROAD_ACCESS_TOKEN を読み、Gumroad API
(`GET /v2/sales`) を叩いて今月分の件数・通貨別合計を status/sales.json に書く。
トークンが無い時はエラーにせず configured:false で正直に書いて終わる
（650番 money.html の既存方針＝「分からない数字は未登録と出す」と同じ）。

新しい売上（前回実行時点で見ていなかった売上）を見つけたら、Obsidian Vaultの
見張り番ログへ日本語で1行ずつ追記する（既存内容は消さず末尾に追記のみ）。

書式・冪等の作り（tmpファイル→os.replaceで原子的に置換、再実行しても安全）は
tools/fal_cost_ledger.py と同じにしてある。

使い方（CLI）:
  python3 tools/gumroad_sales_sync.py
"""
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ENV_PATH = os.path.join(REPO, ".env")
SALES_JSON = os.path.join(REPO, "status", "sales.json")
LAST_SEEN_JSON = os.path.join(REPO, "status", "gumroad_last_seen.json")
VAULT_LOG = (
    "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
    "tamago_brain/AI出力/_ルール/見張り番ログ.md"
)

GUMROAD_SALES_URL = "https://api.gumroad.com/v2/sales"


def _load_env(path):
    """`KEY=VALUE` 形式の .env を読む（外部ライブラリ不使用・標準ライブラリのみ）。"""
    values = {}
    if not os.path.exists(path):
        return values
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def _load_json(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _atomic_save(path, data):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _now_iso():
    return datetime.now().astimezone().isoformat()


def _fetch_sales(token):
    """ページネーション（next_page_url）を辿って全件取得する。"""
    sales = []
    url = GUMROAD_SALES_URL + "?access_token=" + urllib.parse.quote(token)
    page = 0
    while url and page < 30:
        req = urllib.request.Request(url, headers={"User-Agent": "tamago-shinchoku/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if body.get("success") is False:
            raise RuntimeError(body.get("message") or "Gumroad APIがエラーを返しました")
        sales.extend(body.get("sales") or [])
        next_url = body.get("next_page_url")
        if next_url and next_url.startswith("/"):
            next_url = "https://api.gumroad.com" + next_url
        url = next_url
        page += 1
    return sales


def _to_local_dt(created_at):
    """Gumroadの created_at（ISO8601・末尾Z）をこの端末のローカル日時に変換する。"""
    if not created_at:
        return None
    try:
        s = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt
    except Exception:
        return None


def _sale_amount(sale):
    price_cents = sale.get("price") or 0
    currency = (sale.get("currency") or "USD").upper()
    return float(price_cents) / 100.0, currency


def _format_by_currency(by_currency):
    parts = []
    for cur, amt in by_currency.items():
        parts.append("%.2f%s" % (amt, cur))
    return "、".join(parts) if parts else "0円"


def _append_vault_log(lines):
    if not lines:
        return
    try:
        os.makedirs(os.path.dirname(VAULT_LOG), exist_ok=True)
        existing_ends_nl = True
        if os.path.exists(VAULT_LOG):
            with io.open(VAULT_LOG, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size > 0:
                    f.seek(-1, os.SEEK_END)
                    existing_ends_nl = f.read(1) == b"\n"
        with io.open(VAULT_LOG, "a", encoding="utf-8") as f:
            if not existing_ends_nl:
                f.write("\n")
            for line in lines:
                f.write(line + "\n")
    except Exception:
        # Vaultログへの追記に失敗しても、status/sales.json の更新は止めない。
        pass


def main():
    env = _load_env(ENV_PATH)
    token = (env.get("GUMROAD_ACCESS_TOKEN") or "").strip()

    if not token:
        _atomic_save(SALES_JSON, {
            "configured": False,
            "updatedAt": _now_iso(),
            "note": "GUMROAD_ACCESS_TOKENが.envに未設定",
        })
        return

    try:
        sales = _fetch_sales(token)
    except Exception as e:
        _atomic_save(SALES_JSON, {
            "configured": True,
            "error": str(e),
            "updatedAt": _now_iso(),
        })
        return

    now = datetime.now()
    ym = now.strftime("%Y-%m")

    this_month_count = 0
    by_currency = {}
    for s in sales:
        dt = _to_local_dt(s.get("created_at"))
        if dt is None or dt.strftime("%Y-%m") != ym:
            continue
        amount, currency = _sale_amount(s)
        by_currency[currency] = round(by_currency.get(currency, 0.0) + amount, 2)
        this_month_count += 1

    recent_sales = []
    for s in sales[:5]:
        amount, currency = _sale_amount(s)
        recent_sales.append({
            "name": s.get("product_name") or s.get("name") or "(不明な商品)",
            "price": amount,
            "currency": currency,
            "createdAt": s.get("created_at"),
        })

    # 新規売上の検出：Gumroad APIは新しい順で返ってくる前提。
    # 前回のlast_seen id より手前（＝新しい）ものだけを「新しい売上」とする。
    last_seen = _load_json(LAST_SEEN_JSON, {"lastSeenId": None})
    last_seen_id = last_seen.get("lastSeenId")
    ids_in_order = [s.get("id") for s in sales]

    new_sales = []
    if last_seen_id is None:
        # 初回実行：全履歴をログへ流すとVaultログが荒れるため、
        # 今回はbaselineだけ記録し、次回以降の差分から通知する。
        new_sales = []
    elif last_seen_id in ids_in_order:
        idx = ids_in_order.index(last_seen_id)
        new_sales = sales[:idx]
    else:
        # last_seen idがページ範囲外（古すぎる等）で見つからない場合は、
        # 二重通知を避けるため新規扱いにしない。
        new_sales = []

    if new_sales:
        # 古い順（時系列）にログへ積む。
        for s in reversed(new_sales):
            dt = _to_local_dt(s.get("created_at")) or now
            amount, currency = _sale_amount(s)
            name = s.get("product_name") or s.get("name") or "(不明な商品)"
            line = "- %s 【売れました】%s / %.2f%s / 今月の累計 %d件 %s" % (
                dt.strftime("%Y-%m-%d %H:%M"),
                name,
                amount,
                currency,
                this_month_count,
                _format_by_currency(by_currency),
            )
            _append_vault_log([line])

    if sales:
        _atomic_save(LAST_SEEN_JSON, {"lastSeenId": sales[0].get("id"), "updatedAt": _now_iso()})

    _atomic_save(SALES_JSON, {
        "configured": True,
        "updatedAt": _now_iso(),
        "thisMonth": {"count": this_month_count, "byCurrency": by_currency},
        "recentSales": recent_sales,
    })


if __name__ == "__main__":
    main()
