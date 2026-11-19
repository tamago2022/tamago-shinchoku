#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番 ゲート2（納品前・成果物検品）: 完成した2本の動画を、機械実測値＋3フレーム(最初/中間/最後)の
画像で外部AI(Grok→OpenAI→Gemini、動いた分から)に検品させる。917/920番のgaibu_kenpin.pyの鍵探索・
料金記録の仕組みをそのまま流用し、複数画像を渡せるように拡張したもの（別物を新しく作らない方針）。"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gaibu_kenpin as gk

SYSTEM_PROMPT = (
    "あなたは「ごきげん補給所／卵商店街」という日本語プロジェクトの外部検品担当AIです。"
    "依頼者（たまごさん）は非エンジニアです。今回はループ静止画から作った5秒の動画1本を検品します。"
    "渡すもの：①依頼原文 ②前回(9/12)の失敗の記録（逆再生でループを偽装していた）③今回機械で実測した数値"
    "（幅高さ・秒数・最初と最後のフレームの差RMSE・往復度スコア）④動画から抜き出した最初/中間/最後の"
    "3枚の静止画。\n"
    "判定してほしい観点（依頼原文の完了条件に基づく）：\n"
    "1. 16:9/1920x1080になっているか（実測値を見て判断してよい）\n"
    "2. 3枚の静止画を比較して、カメラが動いた形跡がないか（構図・画角が同一に見えるか）\n"
    "3. 意図した被写体だけが動いていそうか（石のオブジェクト・岩・崖などが変形/消失していないか）\n"
    "4. 実測値（最初と最後のフレームの差が小さい＝continuity、往復度スコアが大きい＝逆再生でごまかして"
    "いない）から見て、本物のループになっていそうか\n"
    "5. たまごさんにこのまま見せてよい状態か\n"
    "必ずJSON形式 {\"verdict\": \"OK\"または\"NG\", \"reasons\": [\"理由1\", ...]} で日本語で返してください"
    "（OKのときはreasonsは空配列でよい）。"
)


def _prompt_text(what_text, metrics_text):
    return (
        "【依頼原文】\n%s\n\n"
        "【今回の機械実測値】\n%s\n"
    ) % (what_text, metrics_text)


def _content_with_images(text, image_paths):
    parts = [{"type": "text", "text": text}]
    for p in image_paths:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    return parts


def call_openai_multi(what_text, metrics_text, image_paths, api_key=None):
    api_key = api_key or gk._find_env_key(("OPENAI_API_KEY",))
    if not api_key:
        return None, [], "", None, "OpenAIの鍵が見つかりません"
    body_base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _content_with_images(_prompt_text(what_text, metrics_text), image_paths)},
        ],
        "response_format": {"type": "json_object"},
    }
    err_list = []
    for model in gk.OPENAI_MODEL_CANDIDATES:
        body = dict(body_base)
        body["model"] = model
        try:
            req = urllib.request.Request(
                gk.OPENAI_URL,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = j.get("usage") or {}
            parsed = json.loads(content)
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", [f"応答形式が不明: {content[:200]}"])
            return verdict, parsed.get("reasons") or [], model, usage, ""
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append(f"{model}: HTTP {e.code} {err_body[:200]}")
            continue
        except Exception as e:
            err_list.append(f"{model}: {e}")
            continue
    return None, [], "", None, f"OpenAI：全モデル失敗（{' / '.join(err_list)}）"


def call_grok_multi(what_text, metrics_text, image_paths, api_key=None):
    api_key = api_key or gk._find_env_key(("XAI_API_KEY",))
    if not api_key:
        return None, [], "", None, "Grokの鍵が見つかりません"
    body_base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _content_with_images(_prompt_text(what_text, metrics_text), image_paths)},
        ],
        "response_format": {"type": "json_object"},
    }
    err_list = []
    for model in gk.GROK_MODEL_CANDIDATES:
        body = dict(body_base)
        body["model"] = model
        try:
            req = urllib.request.Request(
                gk.XAI_URL,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = j.get("usage") or {}
            parsed = json.loads(content)
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", [f"応答形式が不明: {content[:200]}"])
            return verdict, parsed.get("reasons") or [], model, usage, ""
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append(f"{model}: HTTP {e.code} {err_body[:200]}")
            continue
        except Exception as e:
            err_list.append(f"{model}: {e}")
            continue
    return None, [], "", None, f"Grok：全モデル失敗（{' / '.join(err_list)}）"


def _gemini_content_with_images(text, image_paths):
    parts = [{"text": text}]
    for p in image_paths:
        try:
            parts.append({"inline_data": {"mime_type": "image/png", "data": gk._image_b64(p)}})
        except Exception:
            pass
    return parts


def call_gemini_multi(what_text, metrics_text, image_paths, api_key=None):
    api_key = api_key or gk._find_env_key(("GEMINI_API_KEY",))
    if not api_key:
        return None, [], "", None, "Geminiの鍵(GEMINI_API_KEY)が見つかりません"
    body_base = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": _gemini_content_with_images(
            _prompt_text(what_text, metrics_text), image_paths)}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    err_list = []
    for model in gk.GEMINI_MODEL_CANDIDATES:
        api_url = gk.GEMINI_URL_TMPL % (model, api_key)
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(body_base).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            cand = (j.get("candidates") or [{}])[0]
            content = ""
            for p in (cand.get("content") or {}).get("parts", []):
                content += p.get("text", "")
            usage = j.get("usageMetadata") or {}
            parsed = json.loads(content)
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", [f"応答形式が不明: {content[:200]}"])
            return verdict, parsed.get("reasons") or [], model, usage, ""
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append(f"{model}: HTTP {e.code} {err_body[:200]}")
            continue
        except Exception as e:
            err_list.append(f"{model}: {e}")
            continue
    return None, [], "", None, f"Gemini：全モデル失敗（{' / '.join(err_list)}）"


def main():
    name = sys.argv[1]  # chashitsu / kuroihama
    what_text = open(sys.argv[2], encoding="utf-8").read()
    metrics_text = sys.argv[3]
    frame_dir = "/Users/mac/tamago/tamago-shinchoku/share/check/assets/919-zen/frames"
    images = [f"{frame_dir}/{name}_first.png", f"{frame_dir}/{name}_mid.png", f"{frame_dir}/{name}_last.png"]

    # ★34649号対応：依頼名が「Grok/OpenAI/Geminiで検品」と3社を名指ししているため、
    #   1社通れば確定する従来のフォールバック(gaibu_kenpin.judge)ではなく、
    #   3社全部に実際に聞いて、全部の判定を記録する（走った事実を実測で残す）。
    chain = [("Grok", call_grok_multi), ("OpenAI", call_openai_multi), ("Gemini", call_gemini_multi)]
    results = []
    skip_reasons = []
    for provider, fn in chain:
        verdict, reasons, model, usage, err = fn(what_text, metrics_text, images)
        if verdict is None:
            skip_reasons.append(f"{provider}: {err}")
            print(f"[{provider}] SKIP: {err}")
            results.append({"provider": provider, "verdict": "SKIP", "reasons": [err], "model": ""})
            continue
        row = gk.record_cost(919, f"919-{name}", provider, model, usage, verdict,
                              note="動画3フレーム検品(ゲート2・34649号34649_919_gate2_all3)")
        print(json.dumps({"provider": provider, "model": model, "verdict": verdict,
                          "reasons": reasons, "ledger": row}, ensure_ascii=False, indent=2))
        results.append({"provider": provider, "verdict": verdict, "reasons": reasons, "model": model})

    out_path = f"/Users/mac/tamago/tamago-shinchoku/share/check/assets/919-zen/{name}_gate2_all3.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"name": name, "results": results, "at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00")},
                   f, ensure_ascii=False, indent=2)

    ran = [r for r in results if r["verdict"] != "SKIP"]
    if not ran:
        print(f"GATE2_RESULT: SKIP - {' ／ '.join(skip_reasons)}")
        return
    if all(r["verdict"] == "OK" for r in ran):
        print(f"GATE2_RESULT: OK - " + ", ".join(f"{r['provider']}/{r['model']}" for r in ran))
    else:
        ngs = [r for r in ran if r["verdict"] != "OK"]
        print("GATE2_RESULT: NG - " + " ／ ".join(
            f"{r['provider']}: {' / '.join(r['reasons'])}" for r in ngs))


if __name__ == "__main__":
    main()
