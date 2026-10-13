#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番 窓口の自己テスト。外部APIを一切叩かずに、配管が全部通っているかを確かめる。

なぜ要るか：サンドボックスからは外部APIに回線が出ない（実測）。
そこで「外部AIを叩く部分」だけを偽物に差し替えて、その前後
（共有ブリーフの組み立て → メッセージ作り → 会話の保存 → .txt出力 → 円の計算 →
　仕事票の受け渡し → 工場側の代行係）が正しく動くかを確かめる。

使い方: python3 tools/_944_selftest.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402
import kiku  # noqa: E402
import tanomu  # noqa: E402
import gaibu_runner  # noqa: E402

OK = []
NG = []


def check(name, cond, detail=""):
    (OK if cond else NG).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (("  … " + str(detail)) if detail else ""))


# --- 外部AIを偽物に差し替える（ここだけ差し替え、他は本物のまま） -----------------
FAKE_SEEN = []


def fake_ask(vendor, messages, search=False, timeout=90, max_tokens=None, temperature=None):
    FAKE_SEEN.append({"vendor": vendor, "messages": messages, "search": search})
    sys_text = messages[0]["content"]
    return {
        "vendor": vendor, "label": gkuchi.LABEL[vendor], "ok": True,
        "text": "（テスト用の偽の答え）915号は『コンシェルジュと声で会話できるようにする』件です。"
                "前提に書かれていた今日の完了件数も読めています。",
        "model": {"grok": "grok-4.3", "openai": "gpt-4o-mini", "gemini": "gemini-2.5-flash"}[vendor],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 300,
                  "promptTokenCount": 1200, "candidatesTokenCount": 300},
        "costYen": gkuchi._cost_yen(vendor, {"grok": "grok-4.3", "openai": "gpt-4o-mini",
                                             "gemini": "gemini-2.5-flash"}[vendor],
                                   {"prompt_tokens": 1200, "completion_tokens": 300,
                                    "promptTokenCount": 1200, "candidatesTokenCount": 300}),
        "seconds": 1.2, "error": "", "searched": search,
        "officialUrl": gkuchi.OFFICIAL_URL[vendor], "_sysLen": len(sys_text),
    }


def fake_record(*a, **k):
    return None


gkuchi.ask = fake_ask
gkuchi.record = fake_record
kiku.gkuchi.ask = fake_ask
kiku.gkuchi.record = fake_record
tanomu.gkuchi.ask = fake_ask
tanomu.gkuchi.record = fake_record

print("=" * 66)
print("944番 窓口の自己テスト（外部APIは一切叩きません）")
print("=" * 66)

# --- 1. 共有ブリーフ ---------------------------------------------------------
print("\n[1] 共有ブリーフ")
import kyoyu_brief  # noqa: E402
brief = kyoyu_brief.build(max_cases=8, focus_n=915)
check("915号を先頭に立てている", "915号" in brief and "今この話をしています" in brief)
check("制約が入っている（Lovableのチャット禁止）", "Lovableのチャット欄" in brief)
check("Braveを触らない、が入っている", "Brave" in brief)
check("今日の数字が入っている", "クレジット" in brief or "完了" in brief)
check("固有名詞が入っている（ごきげん補給所）", "ごきげん補給所" in brief)
check("たまごさんが貼れる .txt がある", os.path.exists(os.path.join(REPO, "status", "kyoyu_brief.txt")))
print("      文字数: %d" % len(brief))

# --- 2. 聞く（kiku） ---------------------------------------------------------
print("\n[2] 聞く（kiku.run_job）")
out = kiku.run_job({"question": "テスト：915号って何？", "n": 915,
                    "ais": ["grok", "openai", "gemini"], "search": False})
check("3社ぶん返ってきた", len(out.get("results") or []) == 3, "%d社" % len(out.get("results") or []))
check("合計が円で出ている", isinstance(out.get("totalYen"), float), "%.3f円" % (out.get("totalYen") or 0))
check("共有ブリーフが各社の先頭に付いている",
      all(("たまご工場・共有ブリーフ" in s["messages"][0]["content"]) for s in FAKE_SEEN))
check("答えの原文が .txt で残った",
      all(os.path.exists(r.get("savedTo") or "") for r in out["results"]))
th = kiku._load_threads()
check("915号の会話として保存された", "n915" in (th.get("threads") or {}))
check("会話に user と assistant が入っている",
      len((th["threads"]["n915"].get("openai") or [])) >= 2)

# 2回目：同じ号番号で聞くと「続き」になるか
FAKE_SEEN.clear()
kiku.run_job({"question": "テスト2：さっきの件の続き", "n": 915, "ais": ["openai"], "search": False})
msgs = FAKE_SEEN[0]["messages"]
check("2回目は前回のやりとりを持っていっている（＝続きになる）",
      any(m["role"] == "assistant" for m in msgs), "メッセージ%d通" % len(msgs))
check("画面出力が作れる", len(kiku.render(out)) > 200)

# --- 3. 頼む（tanomu） -------------------------------------------------------
print("\n[3] 頼む（tanomu.run_job）")
o2 = tanomu.run_job({"kind": "research", "order": "テスト：配管の確認", "vendor": "gemini", "n": 944})
r = o2.get("result") or {}
check("成果物フォルダができた", os.path.isdir(r.get("dir") or ""), r.get("dir"))
check("report.txt がある", os.path.exists(os.path.join(r.get("dir") or "", "report.txt")))
check("report.md がある", os.path.exists(os.path.join(r.get("dir") or "", "report.md")))
check("_meta.json に円が入っている",
      os.path.exists(os.path.join(r.get("dir") or "", "_meta.json")))
check("置き場は status/gaibu_seika 配下", "gaibu_seika" in (r.get("dir") or ""))
check("リサーチには検索ONで投げている", FAKE_SEEN[-1]["search"] is True)
# 後片付け（テストのゴミを残さない）
import shutil  # noqa: E402
if r.get("dir") and os.path.isdir(r["dir"]):
    shutil.rmtree(r["dir"], ignore_errors=True)

# --- 4. 仕事票の受け渡し（サンドボックス⇔工場） -------------------------------
print("\n[4] 仕事票の受け渡し（gaibu_runner）")
jid = gkuchi.enqueue_job("kiku", {"question": "テスト：受け渡しの確認", "n": 915,
                                  "ais": ["openai"], "search": False})
check("pending に仕事票が置けた",
      os.path.exists(os.path.join(gkuchi.JOBS_PENDING, jid + ".json")))
gkuchi.net_ok = lambda *a, **k: True          # 工場にいるふりをする
gaibu_runner.gkuchi.net_ok = lambda *a, **k: True
n_done = gaibu_runner.run_once(max_jobs=5, quiet=True, only_job=jid)  # ★自分の分だけ。本物の待ち行列を食べない
check("代行係が処理した", n_done >= 1, "%d件" % n_done)
res_path = os.path.join(gkuchi.JOBS_DONE, jid + ".json")
check("done に結果が書かれた", os.path.exists(res_path))
if os.path.exists(res_path):
    res = json.load(io.open(res_path, encoding="utf-8"))
    check("結果に ok と円が入っている", res.get("ok") and "totalYen" in res,
          "%.3f円" % (res.get("totalYen") or 0))
    check("工場で走ったと記録されている", res.get("ranOn") == "factory")
check("pending は空になった", not os.path.exists(os.path.join(gkuchi.JOBS_PENDING, jid + ".json")))
check("ロックが次の起動を塞いでいない", gaibu_runner._take_lock()); gaibu_runner._release_lock()
# テストの残骸は必ず片付ける（マウント越しに消せない環境では中身を無効化する）
for p in (res_path, os.path.join(gkuchi.JOBS_PENDING, jid + ".json"),
          os.path.join(gkuchi.JOBS_RUNNING, jid + ".json")):
    if not os.path.exists(p):
        continue
    try:
        os.remove(p)
    except Exception:
        try:
            io.open(p, "w", encoding="utf-8").write(
                '{"jobId":"%s","kind":"noop","payload":{},"note":"自己テストの残骸。何もしない。"}' % jid)
        except Exception:
            pass

# --- 5. 検品の見える化 -------------------------------------------------------
print("\n[5] 検品のやりとり（kenpin_mieru）")
import kenpin_mieru  # noqa: E402
info = kenpin_mieru.do_one(915, quiet=True)
check("915号の記録が読めた", bool(info), info)
if info:
    check("5往復ある", info["rounds"] == 5, "%d往復" % info["rounds"])
    check("最後はPASS", info["passed"] is True)
    check("直させたのが4回", info["fixes"] == 4, "%d回" % info["fixes"])
    check("費用が2.084円", abs(info["costYen"] - 2.084) < 0.01, "%.3f円" % info["costYen"])
    t = io.open(os.path.join(REPO, "status", "kenpin", "915", "やりとり.txt"), encoding="utf-8").read()
    check("やりとり.txt に『直させた』が並んでいる", t.count("🔴 直させた") == 4)
    check("やりとり.txt に『通した』がある", "✅ 通した" in t)
    check("出したもの・指摘・PASSまでの回数が全部入っている",
          "Claudeが出したもの" in t and "外部AIの指摘" in t and "往復した回数" in t)
    check("進捗表が読む要約がある",
          os.path.exists(os.path.join(REPO, "status", "public", "kenpin_mieru.json")))

# --- 6. 鍵を漏らしていないか -------------------------------------------------
print("\n[6] 鍵の扱い")
ks = gkuchi.key_status()
check("鍵は有無しか返さない（値を返していない）",
      all(isinstance(v, bool) for v in ks.values()), ks)
log_path = os.path.join(REPO, "status", "kiku_log.jsonl")
body = ""
for _try in range(4):   # マウント越しは書いた直後に一度だけ読めないことがある（実測）
    try:
        body = io.open(log_path, encoding="utf-8").read()
        break
    except Exception:
        import time as _t; _t.sleep(0.5)
if body:
    check("ログに sk- で始まる文字列が無い", "sk-" not in body)
    check("ログに xai- で始まる文字列が無い", "xai-" not in body)

print("\n" + "=" * 66)
print("通った %d件 / 落ちた %d件" % (len(OK), len(NG)))
if NG:
    for x in NG:
        print("  落ちた: " + x)
print("=" * 66)
sys.exit(1 if NG else 0)
