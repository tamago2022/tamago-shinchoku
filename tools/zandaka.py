#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1034番【財布の残高を叩いて確かめる口】工場（Mac）側でだけ走る。

たまごさん（2026-09-23・原文）:
  「今いくらあるんだっけ。クレジットがあるのかなとか、ジェミニもさあ、どこの財布で
    払うのかよくわかんないね。今いくらかかってるのかが知りたいな。雑にやると
    いきなり何千円だとか請求が来るとびっくりするから、そこをまとめて。」

■ なぜ要るか（2026-09-23 実測）
  サンドボックス（Dispatch/Cowork）からは api.x.ai / api.openai.com /
  rest.alpha.fal.ai / api.devin.ai すべて **curl が 000**（回線が出ない）。
  鍵も届かない（~/.tamago/keys/api_keys.env はマウント外）。
  → 「残高を読む」コードは工場側で走らせる。この1本がその窓口。
  gaibu_runner.py の kind="zandaka" から呼ばれる。

■ 守っていること（★お金の話なので固く）
  ・**GETだけ。** POST/PUT/DELETE を1本も書いていない。課金も解約も押せない。
  ・**白名簿の外に出られない。** ALLOW の前方一致に当たらないURLは叩かずに落とす。
  ・**鍵の値を返さない。** 頭7文字＋…だけ。本文も危なそうな文字は伏せる。
  ・**AIを1回も呼ばない。** 残高の読み取りAPIは無料。この調査自体の課金は0円。
  ・取れなかったものは「取れない」と HTTPコードと本文つきで返す。**黙って飲み込まない。**

■ 使い方
    python3 tools/zandaka.py            # 工場の上で直接（回線が出る所）
    python3 tools/zandaka.py --json     # 機械が読む形
  サンドボックスからは：
    gaibu_kuchi.enqueue_job("zandaka", {}) → wait_job
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATUS = os.path.join(REPO, "status")
OUT_JSON = os.path.join(STATUS, "1034_zandaka_jissoku.json")

# ★白名簿。ここに前方一致しないURLは叩かない。全部GET。
ALLOW = (
    "https://api.x.ai/v1/",
    "https://api.openai.com/v1/",
    "https://rest.alpha.fal.ai/",
    "https://api.fal.ai/",
    "https://api.devin.ai/v1/",
    "https://generativelanguage.googleapis.com/v1beta/",
    "https://api.github.com/",
)

# ★鍵の置き場（gaibu_kuchi と同じ場所を見る）。値は外に出さない。
# ★鍵の置き場は tools/kagi.py が唯一の決定者（1132番）。ここにリストを書かない。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kagi  # noqa: E402
KEY_FILES = list(kagi.ALL_FILES)

SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|xai-[A-Za-z0-9_\-]{8,}|"
                       r"gh[pousr]_[A-Za-z0-9]{8,}|AIza[A-Za-z0-9_\-]{8,}|"
                       r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[A-Za-z0-9]{8,})")


def _mask(s):
    """本文に鍵らしき文字が混ざっていたら伏せる。"""
    return SECRET_RE.sub("〈伏せました〉", s or "")


def find_key(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    for path in KEY_FILES:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].strip()
                for n in names:
                    if line.startswith(n + "="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            continue
    return None


def get(url, headers=None, timeout=15):
    """GETだけ。白名簿の外なら叩かない。返すのは HTTPコード＋本文（伏せ字つき）。"""
    if not any(url.startswith(p) for p in ALLOW):
        return {"url": url, "code": None, "body": "", "error": "白名簿の外なので叩いていません"}
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(20000).decode("utf-8", "ignore")
            return {"url": url, "code": r.getcode(), "body": _mask(body)[:4000],
                    "sec": round(time.time() - t0, 2)}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(20000).decode("utf-8", "ignore")
        except Exception:
            body = ""
        return {"url": url, "code": e.code, "body": _mask(body)[:4000],
                "sec": round(time.time() - t0, 2)}
    except Exception as e:
        return {"url": url, "code": 0, "body": "", "error": "%s: %s" % (type(e).__name__, e),
                "sec": round(time.time() - t0, 2)}


def run_cmd(cmd, timeout=40):
    """CLIを1本だけ。白名簿（gsk のみ）。"""
    if not cmd or cmd[0] not in ("gsk",):
        return {"cmd": " ".join(cmd or []), "error": "白名簿の外なので走らせていません"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"cmd": " ".join(cmd), "exit": r.returncode,
                "stdout": _mask(r.stdout or "")[:3000], "stderr": _mask(r.stderr or "")[:1500]}
    except FileNotFoundError:
        return {"cmd": " ".join(cmd), "error": "そのコマンドが入っていません（FileNotFound）"}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "error": "%d秒で返りませんでした" % timeout}
    except Exception as e:
        return {"cmd": " ".join(cmd), "error": "%s: %s" % (type(e).__name__, e)}


def run_job(payload=None):
    payload = payload or {}
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    res = {"ok": True, "at": now, "totalYen": 0.0, "keys": {}, "probes": [], "cmds": []}

    xai = find_key("XAI_API_KEY", "GROK_API_KEY")
    oai = find_key("OPENAI_API_KEY", "CHATGPT_API_KEY")
    oai_admin = find_key("OPENAI_ADMIN_KEY", "OPENAI_ADMIN_API_KEY")
    gem = find_key("GEMINI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_GENAI_API_KEY")
    fal = find_key("FAL_KEY", "FAL_API_KEY", "FAL_ADMIN_KEY")
    dev = find_key("DEVIN_API_KEY")
    gh = find_key("GITHUB_TOKEN", "GH_TOKEN")

    for name, v in (("xai", xai), ("openai", oai), ("openai_admin", oai_admin),
                    ("gemini", gem), ("fal", fal), ("devin", dev), ("github", gh)):
        res["keys"][name] = {"ある": bool(v), "頭": (v[:7] + "…") if v else ""}

    P = res["probes"].append
    # ---- xAI：鍵がどのチームのものか（残高のAPIは公式に無い）----
    if xai:
        P({"財布": "xAI", "何を見るか": "この鍵がどのチームのものか",
           **get("https://api.x.ai/v1/api-key", {"Authorization": "Bearer " + xai})})
    else:
        P({"財布": "xAI", "何を見るか": "鍵", "code": None, "body": "",
           "error": "鍵が置かれていません"})

    # ---- OpenAI：残高APIは公式に無い。生きているか＋実額（管理鍵が要る）----
    if oai:
        P({"財布": "OpenAI", "何を見るか": "鍵が生きているか（モデル一覧）",
           **get("https://api.openai.com/v1/models", {"Authorization": "Bearer " + oai})})
    key_for_cost = oai_admin or oai
    if key_for_cost:
        month0 = int(time.mktime(time.strptime(time.strftime("%Y-%m-01"), "%Y-%m-%d")))
        P({"財布": "OpenAI", "何を見るか": "今月の実額（costs）",
           **get("https://api.openai.com/v1/organization/costs?start_time=%d&bucket_width=1d&limit=40"
                 % month0, {"Authorization": "Bearer " + key_for_cost})})

    # ---- Gemini：鍵があるか／生きているか ----
    if gem:
        P({"財布": "Gemini", "何を見るか": "鍵が生きているか（モデル一覧）",
           **get("https://generativelanguage.googleapis.com/v1beta/models?key=" + gem)})
    else:
        P({"財布": "Gemini", "何を見るか": "鍵", "code": None, "body": "",
           "error": "鍵が置かれていません（＝この口からは1円も出ていない）"})

    # ---- fal：残高。★user_balance は今日が初回（前回は user_spending/billing で404）----
    if fal:
        for u in ("https://rest.alpha.fal.ai/billing/user_balance",
                  "https://rest.alpha.fal.ai/billing/user_spending"):
            P({"財布": "fal", "何を見るか": "残高", **get(u, {"Authorization": "Key " + fal})})
    else:
        P({"財布": "fal", "何を見るか": "残高", "code": None, "body": "",
           "error": "鍵が置かれていません"})

    # ---- Devin：残高の口は403（前回実測）。生きているかだけ見る ----
    if dev:
        P({"財布": "Devin", "何を見るか": "鍵が生きているか（セッション一覧）",
           **get("https://api.devin.ai/v1/sessions?limit=1", {"Authorization": "Bearer " + dev})})
        today = time.strftime("%Y-%m-%d")
        P({"財布": "Devin", "何を見るか": "使用量（consumption）",
           **get("https://api.devin.ai/v1/enterprise/consumption?start_date=%s-01&end_date=%s"
                 % (time.strftime("%Y-%m"), today), {"Authorization": "Bearer " + dev})})
    else:
        P({"財布": "Devin", "何を見るか": "残高", "code": None, "body": "",
           "error": "鍵が置かれていません"})

    # ---- GitHub Actions：無料枠をいくら使ったか ----
    if gh:
        P({"財布": "GitHub Actions", "何を見るか": "今月の分（Actions）",
           **get("https://api.github.com/users/tamago2022/settings/billing/actions",
                 {"Authorization": "Bearer " + gh, "Accept": "application/vnd.github+json"})})
    else:
        P({"財布": "GitHub Actions", "何を見るか": "今月の分", "code": None, "body": "",
           "error": "トークンが置かれていません（gh auth login が要る）"})

    # ---- Genspark：公式CLI ----
    res["cmds"].append(run_cmd(["gsk", "me"]))
    res["cmds"].append(run_cmd(["gsk", "--version"], timeout=20))

    try:
        os.makedirs(STATUS, exist_ok=True)
        with io.open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        res["savedTo"] = os.path.relpath(OUT_JSON, REPO)
    except Exception as e:
        res["saveError"] = str(e)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = run_job({})
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print("財布の実測 %s" % out["at"])
    for k, v in out["keys"].items():
        print("  鍵 %-13s %s %s" % (k, "ある" if v["ある"] else "ない", v["頭"]))
    for p in out["probes"]:
        print("  [%s] %s -> %s %s" % (p.get("財布"), p.get("何を見るか"),
                                      p.get("code"), (p.get("error") or "")))
        if p.get("body"):
            print("      " + p["body"][:300].replace("\n", " "))
    for c in out["cmds"]:
        print("  $ %s -> %s %s" % (c.get("cmd"), c.get("exit"), c.get("error") or ""))
        if c.get("stdout"):
            print("      " + c["stdout"][:300].replace("\n", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
