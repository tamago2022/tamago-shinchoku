#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番【本丸】外部AIへの「口」— Grok / ChatGPT(OpenAI) / Gemini を同じ形で叩く土台。

たまごさんの言葉（2026-09-18・原文）:
  「あなたがセンターになるって意味だよ。俺がわざわざGrok開いてジェミニ開いていつもやってることを、
    あなたを通してできるようになるのかっていう。」

■ このファイルの役割
  kiku.py（聞く）と tanomu.py（頼む）の**両方が使う共通部分**だけを持つ。
  ・鍵の探索（値は絶対に返り値以外に出さない・ログにも書かない）
  ・各社を「メッセージ配列を投げて文字列が返る」という同じ形に揃える
  ・使ったトークン→円の計算（単価は tools/gaibu_kenpin.py の PRICING を再利用。2箇所に書かない）
  ・検索（リサーチ）をONにする指定。GrokはLive Search、Geminiはgoogle_search grounding。

■ ★回線についての実測事実（2026-09-18）
  Cowork/Dispatchのサンドボックスからは api.openai.com / api.x.ai /
  generativelanguage.googleapis.com へ**出られない**（DNSで落ちる）。
  たまごさんのMac（＝工場）からは**出られる**（tools/kenpin_gate.py が実際に5往復している）。
  → このファイルを使うコードは「工場側で動く」前提で書く。
     サンドボックスから使う場合は tools/gaibu_runner.py 経由で工場に代行させる
     （kiku.py / tanomu.py が自動でそちらへ回すので、呼ぶ側は意識しなくてよい）。
"""
import io
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kenpin as gk  # noqa: E402  単価表・円換算・課金台帳をそのまま再利用する

XAI_URL = "https://api.x.ai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"

# 会話用に使うモデル。検品(gaibu_kenpin)より少し賢いものを先頭に置く。
# 先頭から順に試し、その鍵で通ったものを使う（アカウントによって使えるモデルが違うため）。
CHAT_MODELS = {
    "grok": ["grok-4.3", "grok-4.6", "grok-4.5"],
    "openai": ["gpt-4o-mini", "gpt-5-mini", "gpt-4o"],
    "gemini": ["gemini-2.5-flash", "gemini-2.0-flash"],
}
KEY_NAMES = {
    "grok": ("XAI_API_KEY", "GROK_API_KEY"),
    "openai": ("OPENAI_API_KEY", "CHATGPT_API_KEY"),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_GENAI_API_KEY"),
}
LABEL = {"grok": "Grok(xAI)", "openai": "ChatGPT(OpenAI)", "gemini": "Gemini(Google)"}
VENDOR_PROVIDER = {"grok": "Grok", "openai": "OpenAI", "gemini": "Gemini"}
OFFICIAL_URL = {
    "grok": "https://docs.x.ai/developers/pricing",
    "openai": "https://platform.openai.com/docs/pricing",
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
}

# たまごさんの鍵の置き場。gaibu_kenpin._find_env_key が見る場所に、たまごさんが言った
# ~/Documents/AI作業/_鍵/keys.env を足す（あちらを壊さないようここで足し込む）。
EXTRA_KEY_FILES = [
    os.path.expanduser("~/Documents/AI作業/_鍵/keys.env"),
    os.path.expanduser("~/Documents/AI作業/_鍵/.env"),
    os.path.expanduser("~/.tamago/keys/api_keys.env"),
]


def find_key(vendor):
    """鍵を探す。**見つかった値は返り値としてしか外に出さない**（printもlogもしない）。"""
    names = KEY_NAMES[vendor]
    v = gk._find_env_key(names)
    if v:
        return v
    for path in EXTRA_KEY_FILES:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].strip()
                for name in names:
                    if line.startswith(name + "="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            continue
    return None


def key_status():
    """どの社の鍵があるか。**有無だけ**を返す（値は返さない）。"""
    return {v: bool(find_key(v)) for v in ("grok", "openai", "gemini")}


def net_ok(host="api.openai.com", timeout=4):
    """外部APIへ回線が出るか。出ないサンドボックスと出る工場を見分けるのに使う。"""
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo(host, 443)
        return True
    except Exception:
        return False


def _post_json(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def _err_text(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            b = e.read().decode("utf-8", "ignore")
        except Exception:
            b = ""
        return "HTTP %s %s" % (e.code, b[:300])
    return "%s: %s" % (type(e).__name__, e)


# ---------------------------------------------------------------------------
# 1社に1回聞く。戻り値は必ずこの形（呼ぶ側が社ごとに分岐しないで済むように）
#   {"vendor","label","ok","text","model","usage","costYen","seconds","error","searched"}
# ---------------------------------------------------------------------------

def ask(vendor, messages, search=False, timeout=90, max_tokens=None, temperature=None,
        models=None):
    """models を渡すと、その社の既定リスト（安い順）ではなく指定したモデルを先頭から試す。
    ★2026-09-19 実測：既定は gpt-4o-mini が先頭で、返ってくる答えが浅く「検索できませんでした」
      で終わる。難しい問いのときは賢いモデルを指名できる口が要る。"""
    t0 = time.time()
    base = {"vendor": vendor, "label": LABEL[vendor], "ok": False, "text": "",
            "model": "", "usage": {}, "costYen": 0.0, "seconds": 0.0,
            "error": "", "searched": False, "officialUrl": OFFICIAL_URL[vendor]}
    key = find_key(vendor)
    if not key:
        base["error"] = "%sの鍵が見つかりません（%s のいずれかが .env / ~/.tamago/keys/api_keys.env / " \
                        "~/Documents/AI作業/_鍵/keys.env に必要）" % (LABEL[vendor], "・".join(KEY_NAMES[vendor]))
        base["seconds"] = round(time.time() - t0, 1)
        return base

    errs = []
    for model in (models or CHAT_MODELS[vendor]):
        try:
            if vendor == "gemini":
                text, usage, searched = _call_gemini(key, model, messages, search, timeout)
            else:
                url = XAI_URL if vendor == "grok" else OPENAI_URL
                text, usage, searched = _call_openai_style(
                    key, url, model, messages, search, timeout, vendor, max_tokens, temperature)
            base.update({"ok": True, "text": text, "model": model,
                         "usage": usage, "searched": searched})
            base["costYen"] = _cost_yen(vendor, model, usage)
            base["seconds"] = round(time.time() - t0, 1)
            return base
        except Exception as e:
            errs.append("%s → %s" % (model, _err_text(e)))
            continue
    base["error"] = "全モデルで失敗： " + " ／ ".join(errs)
    base["seconds"] = round(time.time() - t0, 1)
    return base


def _call_openai_style(key, url, model, messages, search, timeout, vendor, max_tokens, temperature):
    body = {"model": model, "messages": messages}
    if max_tokens:
        # gpt-5系は max_completion_tokens しか受け付けないので両対応（片方が弾かれたら再送）
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    searched = False
    if search and vendor == "grok":
        # xAI Live Search。使えないアカウントだと400で落ちるので、その時は検索無しで再送する。
        body["search_parameters"] = {"mode": "auto", "return_citations": True}
        searched = True
    try:
        j = _post_json(url, body, {"Content-Type": "application/json",
                                   "Authorization": "Bearer %s" % key}, timeout)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")
        except Exception:
            pass
        retried = False
        if "search_parameters" in body and e.code in (400, 404, 422):
            body.pop("search_parameters", None)
            searched = False
            retried = True
        if "max_tokens" in detail and "max_completion_tokens" in detail:
            body["max_completion_tokens"] = body.pop("max_tokens", None)
            retried = True
        if "temperature" in detail and body.get("temperature") is not None:
            body.pop("temperature", None)
            retried = True
        if not retried:
            # ★2026-09-23 実測で直した穴：ここで素の `raise` をすると、
            #   上の e.read() で本文（＝断られた理由）を既に吸い出してしまっているため、
            #   _err_text がもう一度 read() しても**空**になる。
            #   結果、画面に出るのは「HTTP 429 」だけで、
            #   「回数の出しすぎ（待てば通る）」なのか
            #   「残高切れ insufficient_quota（お金の話＝たまごさんの判断）」なのかが分からない。
            #   ＝直せるものを直せなくする穴なので、理由を持たせて投げ直す。
            raise RuntimeError("HTTP %s %s" % (e.code, (detail or "")[:400]))
        j = _post_json(url, body, {"Content-Type": "application/json",
                                   "Authorization": "Bearer %s" % key}, timeout)
    ch = (j.get("choices") or [{}])[0]
    text = (ch.get("message") or {}).get("content") or ""
    cits = j.get("citations") or []
    if cits:
        text += "\n\n【出典】\n" + "\n".join("・" + str(c) for c in cits[:10])
    return text, (j.get("usage") or {}), searched


def _call_gemini(key, model, messages, search, timeout):
    """OpenAI形式のmessagesをGeminiのcontents形式に変換して投げる。"""
    sys_parts = [m["content"] for m in messages if m.get("role") == "system"]
    contents = []
    for m in messages:
        if m.get("role") == "system":
            continue
        contents.append({"role": "model" if m["role"] == "assistant" else "user",
                         "parts": [{"text": m.get("content") or ""}]})
    body = {"contents": contents}
    if sys_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(sys_parts)}]}
    searched = False
    if search:
        body["tools"] = [{"google_search": {}}]
        searched = True
    url = GEMINI_URL % (model, key)
    try:
        j = _post_json(url, body, {"Content-Type": "application/json"}, timeout)
    except urllib.error.HTTPError as e:
        if searched and e.code in (400, 404):
            body.pop("tools", None)
            searched = False
            j = _post_json(url, body, {"Content-Type": "application/json"}, timeout)
        else:
            raise
    cand = (j.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    gm = cand.get("groundingMetadata") or {}
    chunks = gm.get("groundingChunks") or []
    if chunks:
        srcs = []
        for c in chunks[:10]:
            w = c.get("web") or {}
            if w.get("uri"):
                srcs.append("・%s %s" % (w.get("title") or "", w["uri"]))
        if srcs:
            text += "\n\n【出典（Google検索）】\n" + "\n".join(srcs)
    return text, (j.get("usageMetadata") or {}), searched


def _cost_yen(vendor, model, usage):
    provider = VENDOR_PROVIDER[vendor]
    tok_in, tok_out = gk._extract_tokens(usage, provider)
    price = gk.PRICING.get((provider, model)) or gk.FALLBACK_PRICE
    usd = (tok_in / 1_000_000.0) * price["in_per_m"] + (tok_out / 1_000_000.0) * price["out_per_m"]
    return round(usd * gk.USD_TO_YEN, 3)


def record(n, title, res, note=""):
    """gaibu_kenpin の課金台帳（status/gaibu_kenpin_ledger.json）に1件足す。
    金の記録を2箇所に散らかさないため、既存の台帳に相乗りする。"""
    if not res.get("ok"):
        return
    try:
        gk.record_cost(n, title, VENDOR_PROVIDER[res["vendor"]], res["model"],
                       res.get("usage") or {}, "ASK", note=note)
    except Exception:
        pass


def cost_cap_ok():
    try:
        return gk.check_cost_cap()
    except Exception:
        return True, "（台帳が読めないため上限チェックを飛ばしました）"


# ---------------------------------------------------------------------------
# 「工場に代行させる」受け渡し（サンドボックス⇔Mac）
#
# なぜ要るか：Cowork/Dispatchのサンドボックスからは外部APIに回線が出ない。
# 一方、たまごさんのMacでは5分おきの便（tools/machine_status_push.sh）が回っていて、
# その中の15秒おきの軽い巡回（quick_tick）から tools/gaibu_runner.py が呼ばれる。
# だから「やってほしいこと」をファイルで置いておけば、工場が代わりに叩いて結果を書く。
# たまごさんが画面から画面へ文章を運ぶ必要は無い（＝伝書鳩ゼロ化・kenpin_gateと同じ思想）。
# ---------------------------------------------------------------------------
JOBS_DIR = os.path.join(REPO, "status", "gaibu_jobs")
JOBS_PENDING = os.path.join(JOBS_DIR, "pending")
JOBS_DONE = os.path.join(JOBS_DIR, "done")
JOBS_RUNNING = os.path.join(JOBS_DIR, "running")


def _job_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-%04d" % (int(time.time() * 1000) % 10000)


def enqueue_job(kind, payload):
    """工場にやらせる仕事を1件置く。戻り値: job_id"""
    for d in (JOBS_PENDING, JOBS_DONE, JOBS_RUNNING):
        os.makedirs(d, exist_ok=True)
    jid = _job_id()
    job = {"jobId": jid, "kind": kind, "payload": payload,
           "queuedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "queuedFrom": socket.gethostname()}
    path = os.path.join(JOBS_PENDING, jid + ".json")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return jid


def wait_job(jid, wait_sec=420, poll=5, on_tick=None):
    """結果が出るまで待つ。戻り値: 結果dict / None（時間切れ）"""
    done_path = os.path.join(JOBS_DONE, jid + ".json")
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if os.path.exists(done_path):
            for _ in range(5):  # 書き込み途中を掴まないよう軽くリトライ
                try:
                    return json.load(io.open(done_path, encoding="utf-8"))
                except Exception:
                    time.sleep(0.4)
        if on_tick:
            on_tick(int(deadline - time.time()))
        time.sleep(poll)
    return None


def write_job_result(jid, result):
    os.makedirs(JOBS_DONE, exist_ok=True)
    path = os.path.join(JOBS_DONE, jid + ".json")
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
