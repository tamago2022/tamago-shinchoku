#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""919番 ゲート1: falに発注する前に、プロンプト案をGrok/OpenAI/Geminiへ検品させる。
テキストのみ（画像なし）で「たまごさんの依頼内容_原文.md」「発注前検品_外部AIへの依頼文.md」を
そのまま渡し、7つの観点に答えてもらう。1本でもNG（直したほうがいいと明言）ならゲート不通過。

使い方:
  python3 tools/_919_gate_prompt_review.py --what-file <依頼文全文.md> --review-file <検品依頼文.md> \
      --out status/919_gate1_result.json

3本そろわなくてもよい（依頼原文どおり）。キーが無いAIはSKIPとして記録し、ブロックしない。
最後に1行:
  GATE_RESULT: PASS - 通過したAI一覧
  GATE_RESULT: NG - 指摘したAI一覧と理由
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYSTEM_PROMPT = (
    "あなたは動画生成AI(fal.ai経由)への発注プロンプトを検品する担当です。"
    "依頼者（たまごさん）は非エンジニアです。渡された依頼文・前回の失敗実測値・発注予定のプロンプト案を読み、"
    "verdictはこの1点だけで決めてください：\n"
    "『このまま送信すると、①カメラが動いてしまう ②本当のループにならず逆再生でごまかされる "
    "③動いてはいけない被写体（石のオブジェ等）が動いたり形を変えたりする ④16:9で構図が壊れる、"
    "のいずれかが高い確率で起きる致命的な欠陥（blocking issue）があるか』。\n"
    "文体・言い回しの好み・語順・『念のためもっと強調したほうがよい』『保証が弱い』"
    "『明確さに欠ける』といった、具体的にどの一文をどう直せば直るのかを示せない抽象的な指摘は"
    "verdictをNGにする理由にしないでください（blockersが無ければOKを返す）。"
    "このプロンプトは既に5回、外部AIの指摘を受けて改訂されています。"
    "NGにするなら、プロンプト文中のどの単語・どの一文が原因で、どう書き換えればよいかを"
    "reasonsに一言一句レベルで具体的に書いてください。それができないならOKにしてください。"
    "念のための改善案があれば reasons ではなく nice_to_have に書いてください。\n"
    "必ずJSON形式で次のキーだけを返してください：\n"
    '{"verdict": "OK"または"NG", "reasons": ["致命的な欠陥1", ...], '
    '"nice_to_have": ["あれば良い程度の改善案", ...], '
    '"answers": ["観点への回答（簡潔に）"]}\n'
    "OKなら reasons は空配列。NGは blocking issue があるときだけ使い、必ず①〜④のどれに該当するか明記すること。"
)


def _find_key(names):
    for name in names:
        v = os.environ.get(name)
        if v:
            return v
    candidates = [
        os.path.join(REPO, ".env"),
        os.path.join(REPO, ".env.local"),
        "/Users/mac/Desktop/joy-relief-station/.env.local",
        "/Users/mac/Desktop/joy-relief-station/.env",
        "/Users/mac/Desktop/joy-relief-station/tools/gpt-roundtable-local/.env.local",
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for name in names:
                    if line.startswith(name + "="):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
        except Exception:
            continue
    return None


def _build_user_text(what_text, review_text):
    return (
        "【依頼内容の原文】\n%s\n\n"
        "【検品してほしい観点・前回の失敗・プロンプト案】\n%s\n"
    ) % (what_text[:12000], review_text[:12000])


def _parse_json_response(content):
    try:
        return json.loads(content)
    except Exception:
        pass
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    verdict = "OK" if re.search(r"\bOK\b", content or "") else "NG"
    return {"verdict": verdict, "reasons": [content[:400]] if verdict == "NG" else [], "answers": []}


def call_grok(user_text):
    api_key = _find_key(["XAI_API_KEY"])
    if not api_key:
        return "SKIP", [], "XAI_API_KEYが見つかりません", {}
    models = ["grok-4", "grok-4-fast", "grok-4-0709", "grok-3"]
    body_base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "response_format": {"type": "json_object"},
    }
    errs = []
    for model in models:
        body = dict(body_base)
        body["model"] = model
        try:
            req = urllib.request.Request(
                "https://api.x.ai/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_response(content)
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", ["応答形式が不明: %s" % content[:200]])
            return verdict, parsed.get("reasons") or [], "", {"model": model, "raw": parsed}
        except urllib.error.HTTPError as e:
            try:
                eb = e.read().decode("utf-8", "ignore")
            except Exception:
                eb = ""
            errs.append("%s: HTTP %s %s" % (model, e.code, eb[:150]))
            continue
        except Exception as e:
            errs.append("%s: %s" % (model, e))
            continue
    return "SKIP", [], "全モデル候補で失敗: %s" % " / ".join(errs), {}


def call_openai(user_text):
    api_key = _find_key(["OPENAI_API_KEY"])
    if not api_key:
        return "SKIP", [], "OPENAI_API_KEYが見つかりません", {}
    models = ["gpt-4o", "gpt-4o-mini"]
    errs = []
    for model in models:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_response(content)
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", ["応答形式が不明: %s" % content[:200]])
            return verdict, parsed.get("reasons") or [], "", {"model": model, "raw": parsed}
        except urllib.error.HTTPError as e:
            try:
                eb = e.read().decode("utf-8", "ignore")
            except Exception:
                eb = ""
            errs.append("%s: HTTP %s %s" % (model, e.code, eb[:150]))
            continue
        except Exception as e:
            errs.append("%s: %s" % (model, e))
            continue
    return "SKIP", [], "全モデル候補で失敗: %s" % " / ".join(errs), {}


def call_gemini(user_text):
    api_key = _find_key(["GEMINI_API_KEY"])
    if not api_key:
        return "SKIP", [], "GEMINI_API_KEYが見つかりません", {}
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, api_key)
    body = {
        "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_text}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("utf-8", "ignore")
        j = json.loads(raw)
        content = j["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _parse_json_response(content)
        verdict = (parsed.get("verdict") or "").upper()
        if verdict not in ("OK", "NG"):
            verdict = "NG"
            parsed.setdefault("reasons", ["応答形式が不明: %s" % content[:200]])
        return verdict, parsed.get("reasons") or [], "", {"model": model, "raw": parsed}
    except urllib.error.HTTPError as e:
        try:
            eb = e.read().decode("utf-8", "ignore")
        except Exception:
            eb = ""
        return "SKIP", [], "HTTP %s %s" % (e.code, eb[:200]), {}
    except Exception as e:
        return "SKIP", [], str(e), {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--what-file", required=True)
    ap.add_argument("--review-file", required=True)
    ap.add_argument("--out", default=os.path.join(REPO, "status", "919_gate1_result.json"))
    ap.add_argument("--label", default="ゲート1")
    args = ap.parse_args()

    what_text = io.open(args.what_file, encoding="utf-8").read()
    review_text = io.open(args.review_file, encoding="utf-8").read()
    user_text = _build_user_text(what_text, review_text)

    results = {}
    for name, fn in (("Grok", call_grok), ("OpenAI", call_openai), ("Gemini", call_gemini)):
        verdict, reasons, err, detail = fn(user_text)
        results[name] = {"verdict": verdict, "reasons": reasons, "error": err, "detail": detail,
                          "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00")}
        print("=== %s: %s ===" % (name, verdict))
        for r in reasons:
            print("  - %s" % r)
        if err:
            print("  (%s)" % err)

    out = {"label": args.label, "results": results, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00")}
    with io.open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    ng = [n for n, r in results.items() if r["verdict"] == "NG"]
    ok = [n for n, r in results.items() if r["verdict"] == "OK"]
    skip = [n for n, r in results.items() if r["verdict"] == "SKIP"]
    if ng:
        print("GATE_RESULT: NG - NGを出したAI: %s / OK: %s / SKIP: %s" % (ng, ok, skip))
        sys.exit(1)
    if not ok:
        print("GATE_RESULT: NG - OKを出したAIが1本も無い（全%s）" % skip)
        sys.exit(1)
    print("GATE_RESULT: PASS - OK: %s / SKIP: %s" % (ok, skip))
    sys.exit(0)


if __name__ == "__main__":
    main()
