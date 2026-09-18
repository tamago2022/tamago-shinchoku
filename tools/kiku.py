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

THREADS = os.path.join(REPO, "status", "kiku_threads.json")
LOG = os.path.join(REPO, "status", "kiku_log.jsonl")
TEXT_DIR = os.path.join(REPO, "status", "kiku")
ALL_AI = ["grok", "openai", "gemini"]

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

    ok, why = gkuchi.cost_cap_ok()
    if not ok:
        return {"ok": False, "error": "コスト上限：" + why, "results": []}

    results = []
    for vendor in ais:
        msgs = build_messages(question, n, vendor, threads, search)
        res = gkuchi.ask(vendor, msgs, search=search, timeout=120,
                         models=(payload.get("models") or {}).get(vendor))
        gkuchi.record(n or 0, "kiku:" + question[:40], res, note="944番 窓口(kiku.py)")
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
    ap.add_argument("--ai", default="grok,openai,gemini", help="grok,openai,gemini から選ぶ")
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
        ks = gkuchi.key_status()
        print("鍵の有無（値は表示しません）：")
        for v in ALL_AI:
            print("  %-22s %s" % (gkuchi.LABEL[v], "あり ✅" if ks[v] else "なし ❌"))
        print("回線（api.openai.comが引けるか）：%s" % ("出られる ✅" if gkuchi.net_ok() else "出られない ❌（工場に代行させます）"))
        return 0

    if not a.question:
        ap.print_help()
        return 2

    ais = [x.strip() for x in a.ai.split(",") if x.strip() in ALL_AI]
    if not ais:
        print("--ai は grok / openai / gemini から選んでください")
        return 2

    payload = {"question": a.question, "n": a.n, "ais": ais, "search": a.search}

    if a.local or gkuchi.net_ok():
        out = run_job(payload)
    else:
        jid = gkuchi.enqueue_job("kiku", payload)
        print("この環境からは外部AIに回線が出ないので、工場（Mac側）に代行を頼みました。")
        print("  job: %s / 便は15秒おきに拾いに来ます。最大%d秒待ちます…" % (jid, a.wait))
        sys.stdout.flush()
        out = gkuchi.wait_job(jid, wait_sec=a.wait)
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
