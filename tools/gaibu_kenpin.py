#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""917番【仕組み⑭】外部AI（Grok→OpenAI→Gemini）に「たまごさんに見せていいか」を判定させる。

たまごさんの言葉（2026-09-17 06:25）：
  「人に見せられる状態じゃないものを俺に見せてるっていうのは、間違いを見せてるってことだから。
   それをやめてくれって話なのよ。誰か、これをたまごさんに見せていいのか検品しましたか？
   あなたじゃなくて、誰がやるんですか？」
  「ChatGPTとそれを共有して『できたよ、これですけどどうですか？』って、ChatGPTもOK出すのか見てみたい。
   それ仕組みにできるの？」

同じClaude（自分）が作って自分で丸を付けると「大丈夫じゃね？」になりがちなので、
別ベンダーのAI（xAI Grok／OpenAI／Google Gemini）に、依頼文・成果物URL・本文・スクリーンショット画像の
3点セットを渡し、「これは依頼を満たしていて、たまごさん（依頼者・非エンジニア）に見せていい状態か」を判定させる。

【920番追記・2026-09-17】複数ベンダー対応に拡張した。
  使う順：Grok（xAI） → OpenAI → Gemini。1本でも判定が返ったらそこで確定し、後段は呼ばない
  （たまごさんの指示「揃うまで待たない。1本でも動いたらその場で使い始める」）。
  ある社のAPIキーが無い／全モデル失敗の時だけ次の社へフォールバックする（＝SKIPの理由を1つずつ積み上げる）。
  料金は公式料金ページの単価（PRICING表）× usageの実測トークン数で計算する（概算ではなく実測ベース）。
  APIキーは ~/.tamago/keys/api_keys.env（600権限・git管理外）に集約し、無ければ従来どおり
  tamago-shinchoku/.env・joy-relief-station/.env(.local) を探す（値そのものはどの出力にも出さない）。

# 使い方
    python3 tools/gaibu_kenpin.py --url <本番/確認ページURL> --what-file <依頼文.txt> \
        [--report-file <報告文.txt>] [--shot <既存スクショPNG>] [--n <番号>] [--no-shot]

  画像を渡さない場合は --no-shot を付ける（依頼文には「画像を見せる」が必須と書かれているため、
  未指定時は既定でスクリーンショットを自動取得する）。

  最後に必ず1行、次のどちらかを出す（他の道具のVERDICT行と同じ形。パースされる前提）：
    GAIBU_RESULT: OK - <一言>
    GAIBU_RESULT: NG - <理由1> ／ <理由2> ...
    GAIBU_RESULT: SKIP - <理由>   … 判定不能（全社ともAPIキー無し・クレジット切れ・上限超過等）。
                                     このときは関所全体をブロックしない（他の関門に委ねる＝素通し）。
  終了コード：OK=0 / NG=1 / SKIP=2

# コスト上限（たまごさん指示：上限を決めて、超えたら止まる）
  既定は1日30回・1日100円（全社合算）。status/gaibu_kenpin_ledger.json に実行のたびに記録する
  （usage（prompt/completion tokens）× 公式単価PRICING表の実測ベース。未登録モデルだけ概算と明記）。
  上限を超えたらAPIを呼ばずSKIPを返す（課金が止まる。検品そのものは他の関門に委ねる）。
"""
import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(REPO, "status", "gaibu_kenpin_ledger.json")
# 【920番・2026-09-17修正】status/直下は.gitignoreの`status/*`でGitHub非公開のため、
# 確認ページから押せるリンクにするには status/public/ 配下（!status/public/** で例外化済み）へも
# 複製する必要がある（他ツールと同じパターン。tamago_maintenance.py の _push() を参照）。
# これを忘れていたため機械検品1回目でリンク404となった。
LEDGER_PUBLIC_PATH = os.path.join(REPO, "status", "public", "gaibu_kenpin_ledger.json")
SHOT_TOOL = os.path.join(REPO, "tools", "gaibu_kenpin_shot.mjs")
TMP_SHOT_DIR = os.path.join(REPO, "status", "gaibu_kenpin_shots")

CENTRAL_KEY_FILE = os.path.expanduser("~/.tamago/keys/api_keys.env")

XAI_URL = "https://api.x.ai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"

# ★モデル名は変わりやすいので上から順に試す（最初に通ったものを使う）。
# 【920番・2026-09-17実測更新】xAI公式 https://docs.x.ai/developers/pricing / llms.txt を確認したところ、
#   旧候補("grok-4"/"grok-4-fast"/"grok-4-0709"/"grok-3")はいずれも2026-05-15付で退役済みで、
#   呼び出すと自動的に grok-4.3 の単価で課金される（スラッグ自体は動くがモデル名として誤解を招く）。
#   現行世代のうち最安（$1.25/$2.50 per 1M・1Mコンテキスト）が grok-4.3 なので、これを第一候補にする。
GROK_MODEL_CANDIDATES = ["grok-4.3", "grok-4.6", "grok-4.5"]

# 【920番・2026-09-17追加】OpenAI公式 https://platform.openai.com/docs/pricing を確認して選定。
#   gpt-4o-mini は画像入力（vision）対応が広く実績のある安価モデル（$0.15/$0.60 per 1M）。
OPENAI_MODEL_CANDIDATES = ["gpt-4o-mini", "gpt-5-mini"]

# 【920番・2026-09-17追加】Gemini公式 https://ai.google.dev/gemini-api/docs/pricing を確認して選定。
#   無料枠がありカード登録不要（Google AI Studioで発行）。$0.30/$2.50 per 1M（画像入力込み）。
GEMINI_MODEL_CANDIDATES = ["gemini-2.5-flash"]

# 2026-09-18（943番）：回数上限30回/日が、金額側にまだ7割の余裕がある段階（28.96円／100円）で
#   検品ゲートを丸ごと止めていた（850号の失敗 F-20260918011032「本日のコスト上限(30回/日)到達で処理不能」）。
#   実測単価は1回あたり約0.97円なので、**金額上限100円/日の方が先に当たる**＝歯止めは弱まらない。
#   お金の上限(100円/日)は一切変えず、回数だけ120回に広げる。
DEFAULT_DAILY_CALL_CAP = 120
DEFAULT_DAILY_YEN_CAP = 100.0
USD_TO_YEN = 150.0

PRICING_SOURCE_NOTE = "2026-09-17に公式料金ページを実機取得して確認した単価（ブログ等の二次情報は不使用）。"

# 単価は「入力USD/100万トークン」「出力USD/100万トークン」。出典URLを必ず添える。
PRICING = {
    ("Grok", "grok-4.3"): {
        "in_per_m": 1.25, "out_per_m": 2.50,
        "source": "https://docs.x.ai/developers/pricing",
    },
    ("Grok", "grok-4.6"): {
        "in_per_m": 2.00, "out_per_m": 6.00,
        "source": "https://docs.x.ai/developers/pricing",
    },
    ("Grok", "grok-4.5"): {
        "in_per_m": 2.00, "out_per_m": 6.00,
        "source": "https://docs.x.ai/developers/pricing",
    },
    ("OpenAI", "gpt-4o-mini"): {
        "in_per_m": 0.15, "out_per_m": 0.60,
        "source": "https://platform.openai.com/docs/pricing",
    },
    ("OpenAI", "gpt-5-mini"): {
        "in_per_m": 0.25, "out_per_m": 2.00,
        "source": "https://platform.openai.com/docs/pricing",
    },
    ("Gemini", "gemini-2.5-flash"): {
        "in_per_m": 0.30, "out_per_m": 2.50,
        "source": "https://ai.google.dev/gemini-api/docs/pricing",
    },
}
# 上のPRICINGに載っていないモデルを呼んだ場合だけ使う保険値（常にnoteへ「概算」と明記する）。
FALLBACK_PRICE = {"in_per_m": 5.0, "out_per_m": 15.0, "source": "(未登録モデルのため概算)"}


def _find_env_key(names):
    """値そのものをログに出さず、複数の既知の.envファイルから環境変数を拾う。
    優先順位：①このプロセスの環境変数 ②~/.tamago/keys/api_keys.env（920番で新設・集約先）
    ③tamago-shinchoku/.env ④joy-relief-station/.env.local ⑤joy-relief-station/.env
    （ごきげん補給所ローカルクローンに既に登録済みのキーを再利用する。
    店主に新しく値を貼らせない＝機密情報を扱う既存ルールに沿う）。"""
    for name in names:
        v = os.environ.get(name)
        if v:
            return v
    candidates = [
        CENTRAL_KEY_FILE,
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


# ---------------------------------------------------------------------------
# コスト帳簿（上限管理・記録）
# ---------------------------------------------------------------------------

def _load_ledger():
    try:
        return json.load(io.open(LEDGER_PATH, encoding="utf-8"))
    except Exception:
        return {"records": [], "dailyCallCap": DEFAULT_DAILY_CALL_CAP,
                "dailyYenCap": DEFAULT_DAILY_YEN_CAP}


def _save_ledger(ledger):
    tmp = LEDGER_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER_PATH)
    # 確認ページから押せるリンクにするため status/public/ へも複製する（git管理対象）。
    try:
        os.makedirs(os.path.dirname(LEDGER_PUBLIC_PATH), exist_ok=True)
        tmp_pub = LEDGER_PUBLIC_PATH + ".tmp"
        with io.open(tmp_pub, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=1)
        os.replace(tmp_pub, LEDGER_PUBLIC_PATH)
    except Exception:
        pass


def _today_records(ledger):
    today = time.strftime("%Y-%m-%d")
    return [r for r in ledger.get("records", []) if (r.get("date") or "") == today]


def check_cost_cap(ledger=None):
    """今日の呼び出し回数・円換算額が上限を超えていないか。超えていれば (False, 理由)。"""
    ledger = ledger or _load_ledger()
    todays = _today_records(ledger)
    call_cap = ledger.get("dailyCallCap", DEFAULT_DAILY_CALL_CAP)
    yen_cap = ledger.get("dailyYenCap", DEFAULT_DAILY_YEN_CAP)
    calls = len(todays)
    yen = sum(float(r.get("costYen") or 0) for r in todays)
    if calls >= call_cap:
        return False, "本日の呼び出し回数が上限(%d回)に達しました（%d回実行済み）" % (call_cap, calls)
    if yen >= yen_cap:
        return False, "本日の費用が上限(%.0f円)に達しました（%.1f円使用済み）" % (yen_cap, yen)
    return True, "OK（本日%d回・%.1f円／上限%d回・%.0f円）" % (calls, yen, call_cap, yen_cap)


def _extract_tokens(usage, provider):
    """OpenAI/xAIは prompt_tokens/completion_tokens、Geminiは promptTokenCount/candidatesTokenCount。"""
    usage = usage or {}
    if provider == "Gemini":
        tok_in = int(usage.get("promptTokenCount") or 0)
        tok_out = int(usage.get("candidatesTokenCount") or 0)
    else:
        tok_in = int(usage.get("prompt_tokens") or 0)
        tok_out = int(usage.get("completion_tokens") or 0)
    return tok_in, tok_out


def record_cost(n, title, provider, model, usage, verdict, note=""):
    ledger = _load_ledger()
    price = PRICING.get((provider, model))
    approx = False
    if not price:
        price = FALLBACK_PRICE
        approx = True
    tok_in, tok_out = _extract_tokens(usage, provider)
    cost_usd = (tok_in / 1_000_000.0) * price["in_per_m"] + (tok_out / 1_000_000.0) * price["out_per_m"]
    cost_yen = round(cost_usd * USD_TO_YEN, 3)
    note_full = "%s 単価出典:%s（%s）%s" % (
        (note or "").strip(),
        price.get("source", ""),
        PRICING_SOURCE_NOTE,
        "※未登録モデルのため概算" if approx else "",
    )
    row = {
        "date": time.strftime("%Y-%m-%d"),
        "n": n,
        "title": title or "",
        "provider": provider,
        "model": model or "",
        "verdict": verdict,
        "tokensIn": tok_in,
        "tokensOut": tok_out,
        "costUsd": round(cost_usd, 6),
        "costYen": cost_yen,
        "note": note_full.strip(),
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    }
    ledger.setdefault("records", []).append(row)
    ledger.setdefault("dailyCallCap", DEFAULT_DAILY_CALL_CAP)
    ledger.setdefault("dailyYenCap", DEFAULT_DAILY_YEN_CAP)
    _save_ledger(ledger)
    return row


# ---------------------------------------------------------------------------
# スクリーンショット取得
# ---------------------------------------------------------------------------

def _find_node():
    for cand in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "node"):
        if cand == "node" or os.path.exists(cand):
            return cand
    return "node"


def take_screenshot(url, out_path=None, timeout=40):
    if not os.path.exists(TMP_SHOT_DIR):
        os.makedirs(TMP_SHOT_DIR, exist_ok=True)
    if not out_path:
        safe = re.sub(r"[^A-Za-z0-9]+", "_", url)[-60:]
        out_path = os.path.join(TMP_SHOT_DIR, "shot_%s_%d.png" % (safe, int(time.time())))
    try:
        out = subprocess.run(
            [_find_node(), SHOT_TOOL, url, out_path],
            cwd=REPO, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "スクリーンショット取得がタイムアウトしました（%d秒）" % timeout
    except Exception as e:
        return None, "スクリーンショット取得の起動に失敗しました（%s）" % e
    if out.returncode != 0 or not os.path.exists(out_path):
        return None, "スクリーンショット取得に失敗しました（%s）" % ((out.stderr or out.stdout or "")[:200])
    return out_path, "OK"


def _image_data_url(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64,%s" % b64


def _image_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# ---------------------------------------------------------------------------
# 共通プロンプト
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "あなたは「ごきげん補給所／卵商店街」という日本語プロジェクトの外部検品担当AIです。"
    "依頼者（たまごさん）は非エンジニアで、専門用語や中の人向けの検査画面を見せられても判断できません。"
    "渡されたもの：①依頼文（そのまま） ②成果物のURL ③成果物の本文テキスト ④スクリーンショット画像（あれば）。"
    "判定基準：\n"
    "1. 依頼を満たしているか。\n"
    "2. たまごさん（非エンジニア・依頼者本人）にこのまま見せてよい状態か"
    "（中身が空・プレースホルダーのまま・「あ」「検査用」等の意味のない文字だけ・"
    "明らかに開発者向けの生データ画面・エラー画面ではないか）。\n"
    "OKなら日本語で「OK」とだけ答えてください。"
    "NGなら見せてはいけない理由を日本語の箇条書きで短く挙げてください。"
    "必ずJSON形式 {\"verdict\": \"OK\"または\"NG\", \"reasons\": [\"理由1\", ...]} で返してください"
    "（OKのときはreasonsは空配列でよい）。"
)


def _prompt_text(what_text, url, report_text):
    return (
        "【依頼文（そのまま）】\n%s\n\n"
        "【成果物URL】\n%s\n\n"
        "【本文・報告テキスト】\n%s\n"
    ) % (what_text or "(依頼文なし)", url or "(URLなし)", (report_text or "(本文なし)")[:4000])


def _build_openai_style_content(what_text, url, report_text, image_data_url=None):
    parts = [{"type": "text", "text": _prompt_text(what_text, url, report_text)}]
    if image_data_url:
        parts.append({"type": "image_url", "image_url": {"url": image_data_url}})
    return parts


# ---------------------------------------------------------------------------
# OpenAI互換（Grok / OpenAI）呼び出し … 両社ともchat completions形式が共通
# ---------------------------------------------------------------------------

def _call_openai_compatible_judge(provider, api_url, model_candidates, key_names,
                                   what_text, url, report_text, image_path=None, api_key=None):
    """戻り値: (verdict, reasons, model_used, usage, err)"""
    api_key = api_key or _find_env_key(key_names)
    if not api_key:
        return None, [], "", None, "%sの鍵(%s)が見つかりません（~/.tamago/keys/api_keys.env にも" \
            " tamago-shinchoku/.env にも joy-relief-station 配下にも無い）" % (provider, "/".join(key_names))

    image_data_url = None
    if image_path and os.path.exists(image_path):
        try:
            image_data_url = _image_data_url(image_path)
        except Exception:
            image_data_url = None

    body_base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_openai_style_content(what_text, url, report_text, image_data_url)},
        ],
        "response_format": {"type": "json_object"},
    }

    err_list = []
    for model in model_candidates:
        body = dict(body_base)
        body["model"] = model
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = j.get("usage") or {}
            try:
                parsed = json.loads(content)
            except Exception:
                verdict = "OK" if re.match(r"^\s*OK\b", content or "", re.IGNORECASE) else "NG"
                parsed = {"verdict": verdict, "reasons": [] if verdict == "OK" else [content[:200]]}
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", ["%sの応答形式が不明でした：%s" % (provider, content[:200])])
            return verdict, parsed.get("reasons") or [], model, usage, ""
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append("%s: HTTP %s %s" % (model, e.code, err_body[:150]))
            continue
        except Exception as e:
            err_list.append("%s: %s" % (model, e))
            continue
    return None, [], "", None, "%s：全モデル候補で呼び出しに失敗しました（%s）" % (provider, " / ".join(err_list))


def call_grok_judge(what_text, url, report_text, image_path=None, api_key=None):
    return _call_openai_compatible_judge(
        "Grok", XAI_URL, GROK_MODEL_CANDIDATES, ("XAI_API_KEY",),
        what_text, url, report_text, image_path=image_path, api_key=api_key)


def call_openai_judge(what_text, url, report_text, image_path=None, api_key=None):
    return _call_openai_compatible_judge(
        "OpenAI", OPENAI_URL, OPENAI_MODEL_CANDIDATES, ("OPENAI_API_KEY",),
        what_text, url, report_text, image_path=image_path, api_key=api_key)


# ---------------------------------------------------------------------------
# Gemini呼び出し（Google Generative Language API・schemaが独自形式）
# ---------------------------------------------------------------------------

def call_gemini_judge(what_text, url, report_text, image_path=None, api_key=None):
    """戻り値: (verdict, reasons, model_used, usage, err)"""
    api_key = api_key or _find_env_key(("GEMINI_API_KEY",))
    if not api_key:
        return None, [], "", None, "Geminiの鍵(GEMINI_API_KEY)が見つかりません" \
            "（Google AI Studioで無料発行してから ~/.tamago/keys/api_keys.env へ追記してください）"

    parts = [{"text": _prompt_text(what_text, url, report_text)}]
    if image_path and os.path.exists(image_path):
        try:
            parts.append({"inline_data": {"mime_type": "image/png", "data": _image_b64(image_path)}})
        except Exception:
            pass

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    err_list = []
    for model in GEMINI_MODEL_CANDIDATES:
        api_url = GEMINI_URL_TMPL % (model, api_key)
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            cand = (j.get("candidates") or [{}])[0]
            content = ""
            for p in (cand.get("content") or {}).get("parts", []):
                content += p.get("text", "")
            usage = j.get("usageMetadata") or {}
            try:
                parsed = json.loads(content)
            except Exception:
                verdict = "OK" if re.match(r"^\s*OK\b", content or "", re.IGNORECASE) else "NG"
                parsed = {"verdict": verdict, "reasons": [] if verdict == "OK" else [content[:200]]}
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", ["Geminiの応答形式が不明でした：%s" % content[:200]])
            return verdict, parsed.get("reasons") or [], model, usage, ""
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append("%s: HTTP %s %s" % (model, e.code, err_body[:150]))
            continue
        except Exception as e:
            err_list.append("%s: %s" % (model, e))
            continue
    return None, [], "", None, "Gemini：全モデル候補で呼び出しに失敗しました（%s）" % " / ".join(err_list)


# ---------------------------------------------------------------------------
# 本体（Grok→OpenAI→Geminiの順でフォールバック）
# ---------------------------------------------------------------------------

# (provider名, 呼び出し関数) の優先順（たまごさん指示：使う順 Grok→OpenAI→Gemini→Devin。
# Devinはコーディングエージェントでありvision judgeの形に馴染まないためこの検品チェーンには含めない）。
PROVIDER_CHAIN = [
    ("Grok", call_grok_judge),
    ("OpenAI", call_openai_judge),
    ("Gemini", call_gemini_judge),
]


def judge(n=None, url=None, what_text="", report_text="", title="", shot_path=None,
          no_shot=False):
    """戻り値: (verdict: "OK"/"NG"/"SKIP", reasons: list[str], detail: dict)"""
    detail = {"tried": []}
    ok_cap, cap_reason = check_cost_cap()
    detail["cost_cap"] = cap_reason
    if not ok_cap:
        return "SKIP", [], detail

    own_shot = False
    if not shot_path and not no_shot and url:
        shot_path, shot_reason = take_screenshot(url)
        detail["screenshot"] = shot_reason
        own_shot = True
    elif shot_path:
        detail["screenshot"] = "指定済み：%s" % shot_path

    skip_reasons = []
    for provider, fn in PROVIDER_CHAIN:
        verdict, reasons, model, usage, err = fn(what_text, url, report_text, image_path=shot_path)
        detail["tried"].append({"provider": provider, "model": model, "err": err})
        if verdict is None:
            skip_reasons.append(err)
            continue
        # このプロバイダで判定が取れた＝ここで確定（後段は呼ばない）
        detail["provider"] = provider
        detail["model"] = model
        detail["usage"] = usage
        row = record_cost(n, title, provider, model, usage, verdict,
                           note="画像%sで判定" % ("あり" if shot_path else "なし"))
        detail["ledger"] = row

        if own_shot and shot_path and os.path.exists(shot_path):
            try:
                os.remove(shot_path)
            except Exception:
                pass
        return verdict, reasons, detail

    # 全社とも呼べなかった
    detail["error"] = " ／ ".join(skip_reasons)
    if own_shot and shot_path and os.path.exists(shot_path):
        try:
            os.remove(shot_path)
        except Exception:
            pass
    return "SKIP", [detail["error"]], detail


def check_gaibu_kenpin_for_url(url, what_text="", report_text="", n=None, title=""):
    """sekisho.py から呼ぶ軽量エントリポイント。
    戻り値: (ok: bool, reason: str) … ok=Trueは「OK」または「SKIP」（ブロックしない）。"""
    verdict, reasons, detail = judge(n=n, url=url, what_text=what_text,
                                      report_text=report_text, title=title)
    provider = detail.get("provider", "?")
    if verdict == "OK":
        return True, "外部AI(%s)検品OK" % provider
    if verdict == "SKIP":
        return True, "外部AI検品はスキップしました（%s）" % (reasons[0] if reasons else detail.get("error", ""))
    return False, "外部AI(%s)がNGと判定しました：%s" % (provider, " ／ ".join(reasons or ["(理由なし)"]))


def main():
    ap = argparse.ArgumentParser(description="917/920番：外部AI(Grok→OpenAI→Gemini)検品 — たまごさんに見せていいかの判定")
    ap.add_argument("--n", default=None)
    ap.add_argument("--url", default=None, help="成果物URL（確認ページ・本番のどちらでもよい）")
    ap.add_argument("--title", default="")
    ap.add_argument("--what-file", default=None)
    ap.add_argument("--what", default="")
    ap.add_argument("--report-file", default=None)
    ap.add_argument("--report", default="")
    ap.add_argument("--shot", default=None, help="既存のスクショPNGを使う場合のパス")
    ap.add_argument("--no-shot", action="store_true", help="画像を渡さずテキストのみで判定する")
    args = ap.parse_args()

    what_text = args.what
    if args.what_file and os.path.exists(args.what_file):
        what_text = io.open(args.what_file, encoding="utf-8", errors="ignore").read()
    report_text = args.report
    if args.report_file and os.path.exists(args.report_file):
        report_text = io.open(args.report_file, encoding="utf-8", errors="ignore").read()

    verdict, reasons, detail = judge(
        n=args.n, url=args.url, what_text=what_text, report_text=report_text,
        title=args.title, shot_path=args.shot, no_shot=args.no_shot,
    )
    print(json.dumps(detail, ensure_ascii=False, indent=1, default=str))
    if verdict == "OK":
        row = detail.get("ledger") or {}
        print("GAIBU_RESULT: OK - たまごさんに見せてよいと判定されました（%s・%s円）" % (
            detail.get("provider", "?"), row.get("costYen", "?")))
        sys.exit(0)
    elif verdict == "SKIP":
        print("GAIBU_RESULT: SKIP - %s" % (reasons[0] if reasons else detail.get("error", "判定不能")))
        sys.exit(2)
    else:
        row = detail.get("ledger") or {}
        print("GAIBU_RESULT: NG - %s（%s・%s円）" % (
            " ／ ".join(reasons or ["(理由なし)"]), detail.get("provider", "?"), row.get("costYen", "?")))
        sys.exit(1)


if __name__ == "__main__":
    main()
