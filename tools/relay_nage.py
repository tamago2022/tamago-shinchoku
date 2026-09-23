#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1038番：スマホの代わりに中継所へ1本投げる「試し投げ」。

なぜ要るか（2026-09-23 の実測）:
  投げ込み箱（share/nagekomi-….html）は、スマホ → 中継所(/cmd) → command_ingest →
  nagekomi.py という道を通る。中継所が古いコードのまま走っていると、この道の
  真ん中で「使えない指示: nagekomi」になって静かに落ちる。**箱を見ただけでは分からない。**
  だから「たまごさんに試させる」前に、こちらが同じ道を1本通しておく。

  ★サンドボックス（Cowork/Dispatch）からは外へ出られない（curl 000 を実測）。
  だから工場（Mac）側で走らせる＝gaibu_runner の kind="relaytest" から呼ばれる。

  ★このファイルは **GET/POST を中継所へ1本投げるだけ**。Lovableの棚には触らない。
  行き先は status/relay.json に書いてある中継所（外の道／家の中の道）だけ。

使い方（工場の中で）:
  python3 tools/relay_nage.py --action nagekomi --target "https://..." --memo "試し投げ"
"""
import argparse
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RJSON = os.path.join(REPO, "status", "relay.json")


def relay_urls():
    """外の道 → 家の中の道 の順で試す先を返す。"""
    out = []
    try:
        d = json.load(io.open(RJSON, encoding="utf-8"))
        for k in ("url", "lanUrl"):
            if d.get(k):
                out.append(d[k].rstrip("/"))
    except Exception:
        pass
    out.append("http://127.0.0.1:8788")   # 最後の頼み（受け口そのもの）
    return out


def post(commands, timeout=25):
    """スマホと同じ形で /cmd へ投げる。通った1本目の結果を返す。"""
    body = json.dumps({"commands": commands}).encode("utf-8")
    tried = []
    for base in relay_urls():
        req = urllib.request.Request(
            base + "/cmd", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "bypass-tunnel-reminder": "1",
                     "User-Agent": "tamago-relay-nage/1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read().decode("utf-8", "replace")
                return {"ok": True, "via": base, "httpCode": r.status,
                        "body": json.loads(txt), "tried": tried}
        except Exception as e:
            tried.append({"url": base, "error": str(e)[:200]})
    return {"ok": False, "error": "どの道も通りませんでした", "tried": tried}


def run_job(payload):
    """工場側（gaibu_runner kind=relaytest）から呼ばれる入口。"""
    p = payload or {}
    cmd = {"action": p.get("action") or "nagekomi",
           "target": p.get("target") or "",
           "id": p.get("id") or "relaytest"}
    if p.get("memo"):
        cmd["memo"] = p["memo"]
    if p.get("label"):
        cmd["label"] = p["label"]
    out = post([cmd])
    out["totalYen"] = 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", default="nagekomi")
    ap.add_argument("--target", required=True)
    ap.add_argument("--memo", default="")
    args = ap.parse_args()
    print(json.dumps(run_job({"action": args.action, "target": args.target,
                              "memo": args.memo}), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
