#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番 窓口の「なぜ通らないか」を工場側で調べる診断係。

■ なぜ要るか（2026-09-19 実測）
  窓口(kiku.py)が実接続で通ったが、3社のうち **ChatGPTしか返らなかった**。
    Grok   … 全モデルで HTTP 410（Gone＝そのモデル名はもう無い）
    Gemini … 鍵が見つからない
  「Grokは使えませんでした」で終わらせない。**向こうに何が有るのかを聞きに行く。**
  サンドボックスからは回線が出ないので、工場（Mac）側でこれを走らせる。

■ 絶対に守ること
  鍵の**値は何があっても出さない**。名前の有無と、先頭数文字の形（sk- / xai- など）だけ。
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402


def _get(url, headers, timeout=30):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def key_files_report():
    """鍵ファイルに **どんな名前** が書いてあるか。値は絶対に出さない。"""
    out = []
    for path in gkuchi.EXTRA_KEY_FILES + [os.path.expanduser("~/.env"),
                                          os.path.join(os.path.dirname(HERE), ".env")]:
        if not os.path.exists(path):
            out.append({"path": path, "exists": False})
            continue
        names = []
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].strip()
                nm = line.split("=", 1)[0].strip()
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                names.append({"name": nm, "len": len(val), "head": val[:4] + "…" if val else ""})
        except Exception as e:
            out.append({"path": path, "exists": True, "error": str(e)})
            continue
        out.append({"path": path, "exists": True, "keys": names})
    envnames = [k for k in os.environ
                if any(w in k.upper() for w in ("API_KEY", "GEMINI", "GOOGLE", "XAI", "GROK", "OPENAI"))]
    out.append({"path": "(環境変数)", "exists": True, "keys": [{"name": k, "len": len(os.environ[k]), "head": ""} for k in envnames]})
    return out


def list_models(vendor):
    key = gkuchi.find_key(vendor)
    if not key:
        return {"vendor": vendor, "ok": False, "error": "鍵なし"}
    try:
        if vendor == "grok":
            d = _get("https://api.x.ai/v1/models", {"Authorization": "Bearer " + key})
            ids = [m.get("id") for m in (d.get("data") or [])]
        elif vendor == "openai":
            d = _get("https://api.openai.com/v1/models", {"Authorization": "Bearer " + key})
            ids = sorted(m.get("id") for m in (d.get("data") or []))
        else:
            d = _get("https://generativelanguage.googleapis.com/v1beta/models?key=" + key, {})
            ids = [m.get("name") for m in (d.get("models") or [])]
        return {"vendor": vendor, "ok": True, "models": ids}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:400]
        except Exception:
            pass
        return {"vendor": vendor, "ok": False, "error": "HTTP %s %s" % (e.code, body)}
    except Exception as e:
        return {"vendor": vendor, "ok": False, "error": repr(e)[:300]}


def try_gemini_with(value):
    """★「鍵が無い」で諦めない。手元にある別のGoogleの鍵が Gemini でも通るか実際に試す。
    （Google AI Studio の鍵も YouTube Data API の鍵も同じ AIza… 形式。同じプロジェクトで
      Generative Language API が有効なら、そのまま通ることがある）"""
    try:
        d = _get("https://generativelanguage.googleapis.com/v1beta/models?key=" + value, {})
        return {"ok": True, "models": [m.get("name") for m in (d.get("models") or [])][:40]}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        return {"ok": False, "error": "HTTP %s %s" % (e.code, body)}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:200]}


def _read_named(path, name):
    try:
        for line in io.open(path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def run_job(payload):
    which = payload.get("vendors") or ["grok", "openai", "gemini"]
    out = {"ok": True, "keyFiles": key_files_report(),
           "models": [list_models(v) for v in which], "totalYen": 0.0}
    trials = payload.get("tryGemini") or []
    if trials:
        res = []
        for t in trials:
            val = _read_named(t["path"], t["name"])
            if not val:
                res.append({"from": t["name"], "ok": False, "error": "その名前の値が無い"})
                continue
            r = try_gemini_with(val)
            r["from"] = t["name"]
            res.append(r)
        out["geminiTrials"] = res
    return out


if __name__ == "__main__":
    print(json.dumps(run_job({}), ensure_ascii=False, indent=1))
