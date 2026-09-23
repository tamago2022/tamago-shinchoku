#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番【本丸】窓口 — Grok / ChatGPT / Gemini に、同じ話を同じ前提で聞く1つの口。

たまごさんの言葉（2026-09-18・原文）:
  「どこに話に行っても話が通じるってことだね。全部が筒になってるっていう状態。」
  「GrokでLINEスタンプ修正したんだけど『誰か申請まで投げれますか？』って言ったら
    『僕ができます』とか『こういうやり方がありました』とか、個別に聞いてるのがめちゃくちゃ面倒くさいのよ。」

■ 何が変わるか
  変更前：たまごさんがGrokを開き、Geminiを開き、ChatGPTを開き、毎回同じ事情を説明し直す。
  変更後：`python3 tools/kiku.py "…"` の1行で、3社に**同じ前提（共有ブリーフ）付きで**同時に聞ける。
          号番号を付ければ**前回の続き**として話せる（＝向こうが「915号ね」と分かる）。

■ 使い方
  python3 tools/kiku.py "この方針どう思う？" --n 915
  python3 tools/kiku.py "今1番伸びてる音楽系サイトは？" --ai gemini --search
  python3 tools/kiku.py "LINEスタンプの申請、代わりに出せる？" --ai grok,openai
  python3 tools/kiku.py --threads              # 今ある会話（号番号ごと）を一覧する
  python3 tools/kiku.py --keys                 # どの社の鍵が有るか（値は出さない）

■ 出るもの
  画面：社名／答え／公式URL／かかった秒数／使った金額（円）と、その合計（円）
  status/kiku_threads.json … 号番号ごとの会話。2回目からは同じスレッドに続く
  status/kiku_log.jsonl    … 1回ごとの記録（誰に何を聞いて何円か）
  status/kiku/<号>/<連番>_<社名>.txt … 答えの原文（たまごさんが読める形）

■ 回線について（2026-09-18 実測）
  サンドボックス（Cowork/Dispatch）からは外部APIに出られない。工場（Mac）からは出られる。
  → このツールは**自分で判定して**、出られない環境なら工場に代行を頼み、結果を待って表示する。
     呼ぶ側は何も意識しなくてよい。工場の便は15秒おきに拾いに来る。
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402
import kyoyu_brief  # noqa: E402
import shigoto_queue as _q  # noqa: E402  ★待ち行列の正本（gaibu_kuchi 経由にしない）
import yosan  # noqa: E402  ★金の栓はここ1か所

THREADS = os.path.join(REPO, "status", "kiku_threads.json")
LOG = os.path.join(REPO, "status", "kiku_log.jsonl")
TEXT_DIR = os.path.join(REPO, "status", "kiku")
# ★2026-09-24 修理：`gaibu_kuchi` が03:38に別物へ書き替えられ、この窓口が頼っていた
#   ask / record / cost_cap_ok / key_status / net_ok / LABEL が**全部消えていた**。
#   実測：kind=kiku の仕事が工場で AttributeError で即死（status/gaibu_jobs/done/20260924-080624-4962.json）。
#   ＝「聞く係」が他人の家に住んでいたのが原因。shigoto_queue.py と同じ直し方をする：
#   **聞く口の定義と金の栓を、この家の中に持つ。**gaibu_kuchi は「codexを叩く道具」としてだけ使う。
ALL_AI = ["codex", "openai", "gemini", "grok"]

# 口ごとの素性。★yen は「1回で実際に出る円」。0円のものは 0.0（憶測で書かない）。
KUCHI = {
    "codex":  dict(label="ChatGPT（codex CLI・gpt-5.6-terra）", saifu="openai", yen=0.0,
                   official="https://openai.com/chatgpt/pricing/",
                   memo="ChatGPTのログインで動く口。1回ごとの課金は出ない（0円）"),
    "openai": dict(label="ChatGPT（OpenAI API）", saifu="openai", yen=1.0,
                   official="https://openai.com/api/pricing/", memo=""),
    "gemini": dict(label="Gemini（Google）", saifu="gemini", yen=0.0,
                   official="https://ai.google.dev/pricing", memo=""),
    "grok":   dict(label="Grok（xAI）", saifu="xai", yen=1.0,
                   official="https://docs.x.ai/docs/models", memo=""),
}
LABEL = {k: v["label"] for k, v in KUCHI.items()}

# ★鍵の置き場は tools/kagi.py が唯一の決定者（1132番）。ここにリストを書かない。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kagi  # noqa: E402
KEYFILES = list(kagi.ALL_FILES)


def find_key(names):
    """鍵を探す。★値は返り値としてしか外に出さない（記録にも画面にも書かない）。"""
    for n in names:
        v = os.environ.get(n)
        if v and v.strip():
            return v.strip()
    for path in KEYFILES:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
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


def key_status():
    return {"codex": gkuchi.codex_aru(),
            "openai": bool(find_key(("OPENAI_API_KEY", "CHATGPT_API_KEY"))),
            "gemini": bool(find_key(("GEMINI_API_KEY", "GOOGLE_AI_API_KEY",
                                     "GOOGLE_GENAI_API_KEY", "GOOGLE_API_KEY"))),
            "grok": bool(find_key(("XAI_API_KEY", "GROK_API_KEY")))}


def net_ok():
    """外部AIに回線が出るか。★サンドボックスからは出ない（実測 000）。"""
    import socket as _s
    try:
        _s.getaddrinfo("api.openai.com", 443)
        return True
    except Exception:
        return False


def _post_json(url, body, headers, timeout=120):
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return getattr(e, "code", 0), None, "%s: %s" % (type(e).__name__, str(e)[:160])


def ask(vendor, msgs, search=False, timeout=120, models=None):
    """1社に聞く。戻り値は必ず同じ形。★失敗しても例外を出さず、理由を必ず入れて返す。"""
    t0 = time.time()
    k = KUCHI.get(vendor) or {}
    out = {"vendor": vendor, "label": k.get("label") or vendor, "model": "",
           "ok": False, "text": "", "error": "", "costYen": 0.0, "seconds": 0.0,
           "searched": False, "officialUrl": k.get("official") or ""}

    # ★金が出る前に栓を通す。0円の口も通す（台帳に載らない口を作らない）。
    ok, why = yosan.mitsumori(k.get("saifu") or "openai", k.get("yen") or 0.0,
                              what="944番 窓口で%sに1回聞く" % out["label"])
    if not ok:
        out["error"] = "予算の栓：" + why
        out["seconds"] = round(time.time() - t0, 1)
        return out

    sysmsg = "\n\n".join(m["content"] for m in msgs if m["role"] == "system")
    usermsg = "\n\n".join(m["content"] for m in msgs if m["role"] != "system")

    if vendor == "codex":
        d, who, err = gkuchi.kiku_codex(
            sysmsg, usermsg + '\n\n★返すのはJSONひとつだけ：{"answer": "本文"}',
            timeout=timeout, model=models)
        out["model"] = who or "codex"
        if d is None:
            out["error"] = err or "codexが答えを返しませんでした"
        else:
            out["ok"] = True
            out["text"] = d.get("answer") or json.dumps(d, ensure_ascii=False)
    elif vendor == "openai":
        key = find_key(("OPENAI_API_KEY", "CHATGPT_API_KEY"))
        if not key:
            out["error"] = "OpenAIの鍵が置かれていません"
        else:
            out["model"] = models or "gpt-5.1"
            c, d, err = _post_json("https://api.openai.com/v1/chat/completions",
                                   {"model": out["model"], "messages": msgs},
                                   {"Authorization": "Bearer " + key}, timeout)
            if d and (d.get("choices") or []):
                out["ok"] = True
                out["text"] = d["choices"][0]["message"]["content"]
            else:
                out["error"] = "OpenAIが %s（%s）" % (c, err or "本文が空")
    elif vendor == "gemini":
        key = find_key(("GEMINI_API_KEY", "GOOGLE_AI_API_KEY",
                        "GOOGLE_GENAI_API_KEY", "GOOGLE_API_KEY"))
        if not key:
            out["error"] = "Geminiの鍵が無い（Google AI Studioで無料発行して鍵ファイルへ）"
        else:
            out["model"] = models or "gemini-2.5-flash"
            c, d, err = _post_json(
                "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
                % (out["model"], key),
                {"system_instruction": {"parts": [{"text": sysmsg}]},
                 "contents": [{"parts": [{"text": usermsg}]}]}, {}, timeout)
            try:
                out["text"] = d["candidates"][0]["content"]["parts"][0]["text"]
                out["ok"] = True
            except Exception:
                out["error"] = "Geminiが %s（%s）" % (c, err or "本文が空")
    elif vendor == "grok":
        key = find_key(("XAI_API_KEY", "GROK_API_KEY"))
        if not key:
            out["error"] = "xAIの鍵が置かれていません"
        else:
            out["model"] = models or "grok-4"
            c, d, err = _post_json("https://api.x.ai/v1/chat/completions",
                                   {"model": out["model"], "messages": msgs},
                                   {"Authorization": "Bearer " + key}, timeout)
            if d and (d.get("choices") or []):
                out["ok"] = True
                out["text"] = d["choices"][0]["message"]["content"]
            else:
                out["error"] = "xAIが %s（%s）" % (c, err or "本文が空")
    else:
        out["error"] = "知らない口です: %s" % vendor

    out["seconds"] = round(time.time() - t0, 1)
    if out["ok"] and (k.get("yen") or 0) > 0:
        out["costYen"] = float(k["yen"])
        yosan.tsukatta(k.get("saifu"), out["costYen"], what="944番 窓口(kiku.py)",
                       src="tools/kiku.py")
    return out


def record(n, what, res, note=""):
    """1回ごとの記録。★書けなくても答えを捨てない（_append_line が飲み込む）。"""
    _append_line(os.path.join(REPO, "status", "kiku_log.jsonl"), json.dumps(
        {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "n": n, "what": what, "note": note,
         "vendor": res.get("vendor"), "ok": res.get("ok"), "model": res.get("model"),
         "yen": res.get("costYen"), "sec": res.get("seconds"),
         "error": (res.get("error") or "")[:200]}, ensure_ascii=False) + "\n")

# 会話が長くなると毎回のトークンが増えて金がかかる。直近の往復だけ持っていく。
KEEP_TURNS = 6


def _load_threads():
    try:
        return json.load(io.open(THREADS, encoding="utf-8"))
    except Exception:
        return {"threads": {}}


def _save_threads(t):
    os.makedirs(os.path.dirname(THREADS), exist_ok=True)
    tmp = THREADS + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=1)
    os.replace(tmp, THREADS)


def _thread_key(n):
    return ("n%s" % n) if n else "free"


def _append_line(path, line):
    """★記録の追記でコケても、聞いた結果そのものを捨てない。
    実測（2026-09-18・Coworkのマウント越し）：作られた直後のファイルへの追記が一度だけ
    FileNotFoundError になり、その例外で**外部AIに聞いた答えごと失われた**。
    答えは既にお金を払って手に入れたもの。記録の失敗で捨ててはいけない。"""
    for i in range(3):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with io.open(path, "a", encoding="utf-8") as f:
                f.write(line)
            return True
        except Exception:
            time.sleep(0.3 * (i + 1))
    return False


def build_messages(question, n, vendor, threads, search):
    """共有ブリーフ＋その社との過去のやりとり＋今回の質問。"""
    brief = kyoyu_brief.build(max_cases=12, focus_n=n)
    sys_msg = brief
    if search:
        sys_msg += "\n\n■ 追加指示：**必ずWeb検索して、実在するURLだけを出してください。**" \
                   "検索できない場合は『検索できませんでした』と最初に書いてください。"
    msgs = [{"role": "system", "content": sys_msg}]
    hist = ((threads.get("threads") or {}).get(_thread_key(n)) or {}).get(vendor) or []
    for m in hist[-KEEP_TURNS:]:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": question})
    return msgs


def run_job(payload):
    """★工場側で実行される本体。gaibu_runner.py からも呼ばれる。"""
    question = payload["question"]
    n = payload.get("n")
    ais = payload.get("ais") or ALL_AI
    search = bool(payload.get("search"))
    threads = _load_threads()


    results = []
    for vendor in ais:
        msgs = build_messages(question, n, vendor, threads, search)
        res = ask(vendor, msgs, search=search, timeout=120,
                         models=(payload.get("models") or {}).get(vendor))
        record(n or 0, "kiku:" + question[:40], res, note="944番 窓口(kiku.py)")
        results.append(res)

    # 会話を保存（次に同じ号番号で聞いたとき「続き」になる）
    tk = _thread_key(n)
    threads.setdefault("threads", {}).setdefault(tk, {})
    for res in results:
        if not res.get("ok"):
            continue
        h = threads["threads"][tk].setdefault(res["vendor"], [])
        h.append({"role": "user", "content": question})
        h.append({"role": "assistant", "content": res["text"]})
        threads["threads"][tk][res["vendor"]] = h[-(KEEP_TURNS * 2):]
    threads["threads"][tk]["_lastAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    threads["threads"][tk]["_lastQuestion"] = question[:120]
    _save_threads(threads)

    # 答えの原文を .txt で残す（たまごさんが読める形・mdは向こうで開けない）
    d = os.path.join(TEXT_DIR, str(n) if n else "free")
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for res in results:
        if not res.get("ok"):
            continue
        p = os.path.join(d, "%s_%s.txt" % (stamp, res["vendor"]))
        with io.open(p, "w", encoding="utf-8") as f:
            f.write("【聞いたこと】%s\n【相手】%s / %s\n【かかった時間】%s秒\n【費用】%.3f円\n\n%s\n"
                    % (question, res["label"], res["model"], res["seconds"], res["costYen"], res["text"]))
        res["savedTo"] = p

    total = round(sum(r.get("costYen") or 0 for r in results), 3)
    _append_line(LOG, json.dumps({
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "n": n, "question": question,
            "ais": ais, "search": search, "totalYen": total,
            "per": [{"vendor": r["vendor"], "ok": r["ok"], "model": r.get("model"),
                     "yen": r.get("costYen"), "sec": r.get("seconds"),
                     "error": (r.get("error") or "")[:200]} for r in results],
        }, ensure_ascii=False) + "\n")
    return {"ok": True, "results": results, "totalYen": total, "n": n, "question": question}


def render(out):
    """画面に出す。社名・答え・公式URL・秒数・円。"""
    L = []
    A = L.append
    if not out.get("ok"):
        A("⚠️ " + (out.get("error") or "失敗しました"))
        return "\n".join(L)
    A("=" * 68)
    A("【聞いたこと】%s" % out.get("question"))
    if out.get("n"):
        A("【号番号】%s号（次も --n %s を付ければ続きとして話せます）" % (out["n"], out["n"]))
    A("=" * 68)
    for r in out["results"]:
        A("")
        A("──【%s】%s" % (r["label"], r.get("model") or ""))
        if not r.get("ok"):
            A("　✗ %s" % r.get("error"))
            A("　所要 %s秒 / 0円" % r.get("seconds"))
            continue
        for line in (r.get("text") or "").splitlines():
            A("　" + line)
        A("")
        A("　公式料金ページ：%s" % r.get("officialUrl"))
        A("　検索した：%s / 所要 %s秒 / %.3f円" % ("はい" if r.get("searched") else "いいえ",
                                                r.get("seconds"), r.get("costYen") or 0))
        if r.get("savedTo"):
            A("　原文：%s" % r["savedTo"])
    A("")
    A("=" * 68)
    A("合計 %.3f円" % (out.get("totalYen") or 0))
    return "\n".join(L)


def cmd_threads():
    t = _load_threads().get("threads") or {}
    if not t:
        print("まだ会話はありません。")
        return 0
    print("いま続いている会話：")
    for k, v in sorted(t.items()):
        n = k[1:] if k.startswith("n") else "（号番号なし）"
        vendors = [x for x in v.keys() if not x.startswith("_")]
        print("  %s号  最終 %s  相手 %s" % (n, v.get("_lastAt") or "?", "・".join(vendors) or "なし"))
        if v.get("_lastQuestion"):
            print("      直前の質問：%s" % v["_lastQuestion"])
    return 0


def main():
    ap = argparse.ArgumentParser(description="外部AI（Grok/ChatGPT/Gemini）に同じ前提で聞く窓口")
    ap.add_argument("question", nargs="?", default=None)
    ap.add_argument("--ai", default="codex,openai,gemini,grok", help="codex,openai,gemini,grok から選ぶ")
    ap.add_argument("--n", type=int, default=None, help="号番号。付けると続きとして話せる")
    ap.add_argument("--search", action="store_true", help="Web検索させる（Grok/Gemini）")
    ap.add_argument("--wait", type=int, default=420, help="工場に代行させるとき待つ秒数")
    ap.add_argument("--local", action="store_true", help="回線判定を飛ばして必ずこの場で叩く")
    ap.add_argument("--threads", action="store_true")
    ap.add_argument("--keys", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.threads:
        return cmd_threads()
    if a.keys:
        ks = key_status()
        print("鍵の有無（値は表示しません）：")
        for v in ALL_AI:
            print("  %-22s %s" % (LABEL[v], "あり ✅" if ks[v] else "なし ❌"))
        print("回線（api.openai.comが引けるか）：%s" % ("出られる ✅" if net_ok() else "出られない ❌（工場に代行させます）"))
        return 0

    if not a.question:
        ap.print_help()
        return 2

    ais = [x.strip() for x in a.ai.split(",") if x.strip() in ALL_AI]
    if not ais:
        print("--ai は codex / openai / gemini / grok から選んでください")
        return 2

    payload = {"question": a.question, "n": a.n, "ais": ais, "search": a.search}

    if a.local or net_ok():
        out = run_job(payload)
    else:
        jid = _q.enqueue_job("kiku", payload)
        print("この環境からは外部AIに回線が出ないので、工場（Mac側）に代行を頼みました。")
        print("  job: %s / 便は15秒おきに拾いに来ます。最大%d秒待ちます…" % (jid, a.wait))
        sys.stdout.flush()
        out = _q.wait_job(jid, wait_sec=a.wait)
        if out is None:
            print("⚠️ 時間内に工場から結果が返りませんでした。")
            print("   あとで見る： status/gaibu_jobs/done/%s.json" % jid)
            return 1

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(render(out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
