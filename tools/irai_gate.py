#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1049番【依頼の門】― 「たまごさんが頼んだものに、これは答えているか」を外のAIに見せる。

■ たまごさんの言葉（2026-09-24・そのまま）
  「ジェミニやグロックやChatGPTに検品してもらって、そういうシステムを作ってテストしてもらって、
    不完全なものが俺に上がってくるのを極力減らしたい。目標はゼロに近づけて。
    俺が確認する手間も省きたい。『違う、そうじゃないから』っていうのが、まずだるい。」

■ 既にある門と、ここが埋める穴
    出典の無い数字     → tools/kazu_gate.py
    書いてある日本語   → tools/oni_gate.py
    絵                 → tools/e_gate.py
    開いて押して動くか → tools/watashi_gate.py ／ tools/sumaho_gate.py
    ★頼んだものに答えているか → **ここ。機械には判定できない。だから外のAIに見せる。**

■ 外のAIに渡すのはこの3つだけ（それ以外を聞かない）
    ① たまごさんが言った言葉（原文そのまま・要約しない）
    ② こちらが渡そうとしているもの
       ★ページなら「開いて実際に画面に出た文字」。コードではない。
         tools/watashi_gate.py の実測記録（status/watashi_gate/<key>.json の text）から取る。
         **記録が無ければ、外のAIに聞く前に落とす**（開いてすらいないものを渡さない）。
    ③ 判定の問い（TOI・1つだけ）
  点数も感想も要らない。**0か1と、1行の理由だけ。**

■ 判定は1行もここに書かない
  規則は全部 tools/hantei.py の irai_han()。同じifを2か所に書かない。

■ 口（実測・2026-09-24 02:12 JST）
  | 口 | 状態 | 実測 |
  |---|---|---|
  | Genspark | ★使える | /Users/mac/.npm-global/bin/gsk（PATHには載っていない）。plan=plus・残1924.937 |
  | Jules    | ★使える | GitHub Issue に `jules` ラベル。鍵は ~/.tamago/gh_token（40字・実在）。こちらの課金0円 |
  | Gemini   | 使えない | **鍵が無い**（gaibu_kuchi.key_status() → gemini: False） |
  | Grok     | 使えない | HTTP 403 permission-denied「team doesn't have any credits or licenses yet」 |
  | ChatGPT  | 使えない | HTTP 429 「You have no credits remaining」 |
  → いま2社そろうのは **Genspark ＋ Jules**。
  → ★Gensparkのプランは 10/4 終了・繰り越しなし。**10/5からは Jules だけで回る。**

■ お金
  ・Gensparkは前払いクレジット（10/4失効・繰り越しなし）＝叩いても追加請求は出ない。
    ただし空回しで溶かさないため、**この門の中に残高の床（CREDIT_YUKA）を持つ。**割ったら止まる。
  ・円がかかる口（OpenAI/Gemini/Grok）は **必ず tools/yosan.py を通す。**上限を超えたら叩かない。

■ 走らせ方
  ［Mac側］外に出られるのはMacだけ。
     python3 tools/irai_gate.py --check "<たまごさんの言葉>" <渡すもの>
     python3 tools/irai_gate.py --demo        # 今日「違う」と言われた3件を入れて落ちるか見る
     python3 tools/irai_gate.py --selftest    # 門が効いているか（AIを呼ばない・0円）
  ［サンドボックス／Dispatch側］
     irai_gate.verdict(irai, target) … 通った記録を引くだけ。
     ★記録が無ければ通さない。「見せていない＝通っていない」。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hantei  # noqa: E402  ★判定はここにしか無い

OUT = os.path.join(REPO, "status", "irai_gate")
LOG = os.path.join(REPO, "status", "irai_gate.log")
WATASHI = os.path.join(REPO, "status", "watashi_gate")

# ★外のAIに渡す問いは、これ1つだけ。増やさない。
TOI = ("この人はこう頼みました。渡そうとしているものは、この頼みに答えていますか。"
       "はい／いいえ。いいえなら、どこが違うかを1行で。")

GSK = "/Users/mac/.npm-global/bin/gsk"   # ★PATHに載っていない（実測 2026-09-24）
CREDIT_YUKA = 300.0          # Gensparkの残高の床。ここを割ったら叩かない
CREDIT_1KAI_MEYASU = 5.0     # 1回の見積り（実測で上書きされる）
MONO_MAX = 6000              # 外のAIに見せる本文の上限（文字）

JULES_REPO = "tamago2022/tamago-shinchoku"   # Issueを立てる先（github_watch と同じ）
GH_TOKEN_FILE = os.path.expanduser("~/.tamago/gh_token")


# ── 記録 ──────────────────────────────────────────────────────────────
def _log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%FT%T"), line))


def key_of(irai, mono):
    """依頼文と中身の両方でひとつの鍵にする。どちらかが変わればもう一度見せる。"""
    h = hashlib.sha256()
    h.update((irai or "").encode("utf-8", "ignore"))
    h.update(b"\x00")
    h.update((mono or "").encode("utf-8", "ignore"))
    return h.hexdigest()[:16]


# ── ② 渡そうとしているもの ────────────────────────────────────────────
def naka(target):
    """渡そうとしているものの中身を取る。

    戻り値: (label, honbun, tomeru)
      tomeru … 空でなければ、外のAIに聞く前にここで落とす理由
    ★HTMLは「実際に開いて画面に出た文字」しか使わない。コードを見せても意味がない。
    """
    if target is None:
        return ("(なし)", "", "渡すものが指定されていません")

    # 生のテキストをそのまま渡された場合
    full = target if os.path.isabs(target) else os.path.join(REPO, target)
    if not os.path.exists(full):
        if "\n" in target or len(target) > 200:
            return ("(その場の文章)", target[:MONO_MAX], "")
        return (target, "", "そんなファイルはありません：%s" % target)

    if os.path.isdir(full):
        names = sorted(os.listdir(full))[:200]
        return (os.path.relpath(full, REPO), "\n".join(names), "")

    rel = os.path.relpath(full, REPO)
    ext = os.path.splitext(full)[1].lower()

    if ext in (".html", ".htm"):
        # ★鍵の作り方を2か所に書かない。渡す門(watashi_gate)のものをそのまま借りる。
        #   最初の版はここで sha256 を独自に書いてしまい、実測3件とも
        #   「まだ一度も開いていません」で落ちた（記録はあったのに引けなかった）。
        import watashi_gate as wg
        p = os.path.join(WATASHI, wg.key_of(full) + ".json")
        if not os.path.exists(p):
            return (rel, "", "このページはまだ一度も実際に開いていません"
                             "（先に `python3 tools/watashi_gate.py --check %s`）。"
                             "★開いていないものを外のAIに見せても意味がありません" % rel)
        d = json.load(io.open(p, encoding="utf-8"))
        txt = (d.get("text") or "").strip()
        if not txt:
            tb = d.get("text_bytes")
            if tb is not None and int(tb or 0) > 0:
                return (rel, "", "この記録は画面の文字を残していない古い形です"
                                 "（tools/watashi_gate.py --check をもう一度通してください）")
            return (rel, "", "開いても画面に文字が1つも出ていません（本文0バイト）")
        stop = list(d.get("stop") or [])
        if stop:
            return (rel, txt[:MONO_MAX],
                    "渡す門（watashi_gate）で既に落ちています：%s" % stop[0])
        return (rel, txt[:MONO_MAX], "")

    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".webm"):
        return (rel, "", "絵・動画そのものの良し悪しは tools/e_gate.py の仕事です"
                         "（この門は文字で答えられるものだけを見ます）")

    try:
        raw = io.open(full, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return (rel, "", "中身が読めません：%s" % e)
    return (rel, raw[:MONO_MAX], "")


def toi_bun(irai, label, mono):
    """外のAIに渡す文。★この3つ以外を書かない。"""
    return (
        "【この人が言った言葉（原文）】\n%s\n\n"
        "【渡そうとしているもの：%s】\n%s\n\n"
        "【問い】\n%s\n\n"
        "答えは次の2行だけで返してください。点数も感想も要りません。\n"
        "1行目: はい　または　いいえ\n"
        "2行目: （いいえのときだけ）どこが違うかを1行で\n"
        % ((irai or "").strip(), label, (mono or "").strip(), TOI)
    )


# ── 返事を はい／いいえ に読む ────────────────────────────────────────
_HAI = re.compile(r"^\s*(はい|ハイ|yes|YES|Yes|○|◯)", re.I)
_IIE = re.compile(r"^\s*(いいえ|イイエ|no|NO|No|×|✕)", re.I)


def yomu(ans):
    """返事を True/False/None にする。★読めないものを「はい」に丸めない。"""
    s = (ans or "").strip()
    if not s:
        return (None, "")
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    head = lines[0] if lines else ""
    riyuu = " ".join(lines[1:])[:300]
    # 1行目に判定が無いときは、全体の先頭300字の中の最初の判定語を拾う
    if _IIE.match(head):
        return (False, riyuu or head)
    if _HAI.match(head):
        return (True, riyuu)
    atama = s[:300]
    i_iie = min([m.start() for m in re.finditer(r"いいえ|^no\b", atama, re.I)] or [10 ** 9])
    i_hai = min([m.start() for m in re.finditer(r"はい|^yes\b", atama, re.I)] or [10 ** 9])
    if i_iie < i_hai:
        return (False, riyuu or atama)
    if i_hai < i_iie:
        return (True, riyuu)
    return (None, s[:200])


# ── 口 ────────────────────────────────────────────────────────────────
def _run(cmd, timeout=240):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def gsk_zandaka():
    """Gensparkの残高（実測）。取れなければ None。値は課金しない。"""
    try:
        rc, so, _ = _run([GSK, "me"], timeout=60)
        if rc != 0:
            return None
        return float(((json.loads(so) or {}).get("data") or {}).get("credit_balance"))
    except Exception:
        return None


def kuchi_genspark(bun):
    """Genspark。★残高の床を割っていたら叩かない。使ったクレジットは実測で返す。"""
    if not os.path.exists(GSK):
        return {"who": "genspark", "yes": None, "why": "", "error": "gskがありません（%s）" % GSK}
    mae = gsk_zandaka()
    if mae is None:
        return {"who": "genspark", "yes": None, "why": "", "error": "残高が読めません（ログイン切れ？）"}
    if mae < CREDIT_YUKA:
        return {"who": "genspark", "yes": None, "why": "",
                "error": "残高%.3fがこの門の床%.0fを割っています＝叩きません" % (mae, CREDIT_YUKA)}
    try:
        # ★--task_name と --instructions の2つが必須（実測・2026-09-24。順に出た
        #   "--task_name" → "--instructions" → "--query"）。3つとも要る。
        rc, so, se = _run([GSK, "task", "create", "super_agent",
                           "--task_name", "依頼の門",
                           "--instructions", bun, "--query", TOI,
                           "--output", "json"], timeout=900)
    except subprocess.TimeoutExpired:
        return {"who": "genspark", "yes": None, "why": "", "error": "時間切れ（10分）"}
    if rc != 0:
        ato = gsk_zandaka()
        tsukatta = None if (mae is None or ato is None) else round(mae - ato, 3)
        return {"who": "genspark", "yes": None, "why": "",
                "error": ("rc=%d %s" % (rc, (se or so)[:200])), "credit": tsukatta}
    # ★ここは非同期。create は「受け付けました」を返すだけ（実測 2026-09-24）。
    #   受領書を答えだと思って読むと「はい」に化ける危険があるので、必ず終わるまで待つ。
    ans = _gsk_matsu(so)
    ato = gsk_zandaka()
    tsukatta = None if (mae is None or ato is None) else round(mae - ato, 3)
    yes, why = yomu(ans)
    return {"who": "genspark", "yes": yes, "why": why, "error": "",
            "credit": tsukatta, "nama": ans[:1200]}


GSK_MACHI_BYOU = 600     # 待つ上限（秒）
GSK_MACHI_KANKAKU = 15


def _gsk_matsu(so):
    """create の返事から札(run_id / project_id)を拾い、終わるまで status を叩いて答えを取る。"""
    try:
        d = json.loads(so)
    except Exception:
        return (so or "").strip()
    fuda = None
    for key in ("run_id", "project_id", "id"):
        v = ((d.get("data") or d) or {}).get(key)
        if isinstance(v, str) and v.strip():
            fuda = v.strip()
            if key == "run_id":
                break
    if not fuda:
        m = re.search(r"sb_task_run::[\w:-]+", so or "")
        fuda = m.group(0) if m else None
    if not fuda:
        return (so or "").strip()
    owari = time.time() + GSK_MACHI_BYOU
    saigo = ""
    while time.time() < owari:
        time.sleep(GSK_MACHI_KANKAKU)
        try:
            rc, s2, _ = _run([GSK, "task", "status", fuda, "--output", "json"], timeout=120)
        except Exception:
            continue
        if rc != 0:
            continue
        saigo = s2
        low = s2.lower()
        if any(w in low for w in ('"completed"', '"finished"', '"success"', '"done"',
                                  '"failed"', '"error"', '"stopped"')):
            break
    return _gsk_honbun(saigo or so)


def _gsk_honbun(so):
    """gskのJSONから答えの本文を掘る。形が変わっても落ちないように広く拾う。"""
    try:
        d = json.loads(so)
    except Exception:
        return (so or "").strip()
    cur = d.get("data", d)
    for k in ("answer", "result", "output", "content", "text", "message", "summary"):
        v = cur.get(k) if isinstance(cur, dict) else None
        if isinstance(v, str) and v.strip():
            return v.strip()
    # 入れ子のどこかにある長い文字列を拾う（最後の手段）
    best = ""
    def horu(x, d_=0):
        nonlocal best
        if d_ > 6:
            return
        if isinstance(x, str):
            if len(x) > len(best):
                best = x
        elif isinstance(x, dict):
            for v in x.values():
                horu(v, d_ + 1)
        elif isinstance(x, list):
            for v in x:
                horu(v, d_ + 1)
    horu(d)
    return best.strip()


def kuchi_jules(bun, matsu=0):
    """Jules。GitHub Issueを立てて `jules` ラベルを貼る。★こちらの課金は0円。

    matsu 秒だけ返事を待つ（0なら立てるだけ）。返事が来ていなければ error で返す
    ＝ hantei.irai_han が「動かなかった口」として扱う（黙って「はい」にしない）。
    """
    tok = None
    try:
        if os.path.exists(GH_TOKEN_FILE):
            tok = io.open(GH_TOKEN_FILE, encoding="utf-8").read().strip()
    except Exception:
        tok = None
    if not tok:
        return {"who": "jules", "yes": None, "why": "",
                "error": "GitHubの鍵がありません（%s）" % GH_TOKEN_FILE}
    import urllib.error
    import urllib.request

    def gh(path, body=None, method="GET"):
        url = "https://api.github.com/repos/%s%s" % (JULES_REPO, path)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "User-Agent": "tamago-irai-gate"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))

    try:
        iss = gh("/issues", {"title": "【依頼の門】頼みに答えているか見てください",
                             "body": bun, "labels": ["jules"]}, "POST")
    except urllib.error.HTTPError as e:
        return {"who": "jules", "yes": None, "why": "",
                "error": "Issueが立ちません HTTP %s %s" % (e.code, e.read().decode("utf-8", "ignore")[:150])}
    except Exception as e:
        return {"who": "jules", "yes": None, "why": "", "error": str(e)[:150]}
    num = iss.get("number")
    owari = time.time() + max(0, matsu)
    while time.time() < owari:
        time.sleep(20)
        try:
            cs = gh("/issues/%s/comments" % num)
        except Exception:
            continue
        for c in cs:
            if "jules" in (((c.get("user") or {}).get("login")) or "").lower():
                yes, why = yomu(c.get("body") or "")
                return {"who": "jules", "yes": yes, "why": why, "error": "",
                        "credit": 0.0, "issue": num, "nama": (c.get("body") or "")[:1200]}
    return {"who": "jules", "yes": None, "why": "", "issue": num,
            "error": "Issue #%s は立てましたが、%d秒では返事が来ていません" % (num, matsu)}


def kuchi_api(vendor, bun):
    """円がかかる口（openai / gemini / grok）。★必ず tools/yosan.py を通す。"""
    try:
        import gaibu_kuchi as gk
        import yosan
    except Exception as e:
        return {"who": vendor, "yes": None, "why": "", "error": "道具が読めません：%s" % e}
    if not gk.find_key(vendor):
        return {"who": vendor, "yes": None, "why": "", "error": "鍵がありません"}
    ok, why = yosan.mitsumori(vendor, 3.0, "依頼の門1回")
    if not ok:
        return {"who": vendor, "yes": None, "why": "", "error": "予算の栓で止まりました：%s" % why}
    try:
        r = gk.chat(vendor, [{"role": "user", "content": bun}])
    except Exception as e:
        return {"who": vendor, "yes": None, "why": "", "error": str(e)[:180]}
    if not (r or {}).get("ok"):
        return {"who": vendor, "yes": None, "why": "", "error": str((r or {}).get("error"))[:180]}
    try:
        yosan.tsukatta(vendor, float(r.get("yen") or 0.0), "依頼の門1回")
    except Exception:
        pass
    yes, w = yomu(r.get("text") or "")
    return {"who": vendor, "yes": yes, "why": w, "error": "",
            "yen": r.get("yen"), "nama": (r.get("text") or "")[:1200]}


KUCHI = {"genspark": kuchi_genspark, "jules": kuchi_jules,
         "gemini": lambda b: kuchi_api("gemini", b),
         "openai": lambda b: kuchi_api("openai", b),
         "grok": lambda b: kuchi_api("grok", b)}
KIHON = ["genspark", "gemini"]   # ★10/5からは ["jules", "gemini"] に入れ替える


# ── 門そのもの ────────────────────────────────────────────────────────
def check(irai, target, shas=None, jules_matsu=0):
    """★これが門。たまごさんに渡す前に必ず通る。

    戻り値: dict(ok, stop, note, key, …)。ok が False なら**たまごさんに渡さない。**
    """
    label, mono, tomeru = naka(target)
    k = key_of(irai, mono or str(target))
    if tomeru:
        r = {"ok": False, "stop": ["渡す前に落ちました：%s" % tomeru], "note": "",
             "key": k, "label": label, "irai": irai, "at": time.strftime("%FT%T"),
             "answers": [], "gaibu": False}
        _save(r)
        _log("🔴 %s %s ｜ %s" % (k, label, tomeru))
        return r

    bun = toi_bun(irai, label, mono)
    names = list(shas or KIHON)
    answers = []
    for n in names:
        f = KUCHI.get(n)
        if not f:
            answers.append({"who": n, "yes": None, "why": "", "error": "そんな口はありません"})
            continue
        try:
            answers.append(f(bun, jules_matsu) if n == "jules" else f(bun))
        except Exception as e:
            answers.append({"who": n, "yes": None, "why": "", "error": str(e)[:180]})

    han = hantei.irai_han(answers)          # ★判定はここでしかしない
    r = dict(han)
    r.update({"key": k, "label": label, "irai": irai, "at": time.strftime("%FT%T"),
              "answers": answers, "gaibu": True,
              "credit": round(sum(float(a.get("credit") or 0) for a in answers), 3),
              "yen": round(sum(float(a.get("yen") or 0) for a in answers), 3)})
    _save(r)
    mark = "✅" if r["ok"] else "🔴"
    _log("%s %s %s ｜ %s%s" % (mark, k, label,
                              ("／".join(r["stop"])[:300] if r["stop"] else "通しました"),
                              ("　" + r["note"] if r.get("note") else "")))
    return r


def _save(r):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, r["key"] + ".json")
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def verdict(irai, target):
    """★サンドボックス／Dispatch側の窓口。通った記録を引くだけ。

    戻り値: 止める理由の一覧（空なら渡してよい）。
    **記録が無ければ通さない。**ここが緩むと、また「頼みと違うもの」がたまごさんに届く。
    """
    _l, mono, tomeru = naka(target)
    if tomeru:
        return ["渡す前に落ちました：%s" % tomeru]
    p = os.path.join(OUT, key_of(irai, mono or str(target)) + ".json")
    if not os.path.exists(p):
        return ["この依頼とこの中身の組は、まだ外のAIに1度も見せていません。"
                "Mac側で `python3 tools/irai_gate.py --check \"<言われた言葉>\" <渡すもの>` を通すこと。"]
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        return ["通った記録が読めません：%s" % e]
    return list(d.get("stop") or [])


def selftest():
    """門が効いているか。★AIを1回も呼ばない・0円。"""
    r = hantei.irai_kanmon()
    print(r.get("line") or r.get("why"))
    # 読み取りの試験（返事を「はい」に丸めていないか）
    miru = [("はい", True), ("いいえ\n絵本ではなく静止画の羅列です", False),
            ("Yes", True), ("No\nnot what was asked", False),
            ("うーん、難しいところですね", None), ("", None)]
    for s, hazu in miru:
        got, _ = yomu(s)
        if got is not hazu:
            print("🔴 返事の読み取りがずれました：%r → %s（%s のはず）" % (s, got, hazu))
            return 1
    print("✅ 返事の読み取り … 見本%d本すべて想定どおり" % len(miru))
    return 0 if not r.get("red") else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", nargs=2, metavar=("言われた言葉", "渡すもの"))
    ap.add_argument("--sha", default=",".join(KIHON), help="見せる口（カンマ区切り）")
    ap.add_argument("--jules-matsu", type=int, default=0, help="Julesの返事を待つ秒数")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if a.demo:
        return demo([s for s in a.sha.split(",") if s], a.jules_matsu)
    if a.check:
        r = check(a.check[0], a.check[1], [s for s in a.sha.split(",") if s], a.jules_matsu)
        print(("✅ 通りました" if r["ok"] else "🔴 落ちました") + "　key=%s" % r["key"])
        for s in r["stop"]:
            print("  ・" + s)
        if r.get("note"):
            print("  " + r["note"])
        if r.get("credit"):
            print("  使ったクレジット：%.3f" % r["credit"])
        return 0 if r["ok"] else 1
    ap.print_help()
    return 0


# ── 実演：今日たまごさんに「違う」と言われた3件 ────────────────────────
DEMO = [
    # ① 絵本の夜（2026-09-23 に渡した3本）。たまごさん「お手本の10分の1」
    ("お手本と同じ水準の絵本を作って。手描きの絵本みたいに。",
     "share/check/ehon-01-hanabi.html",
     "『お手本の10分の1』と言われた"),
    # ② 1046-live2d.html。たまごさん「表示されすらしない」
    ("絵本のページを作って。開いたら動いて見えるようにして。",
     "share/ohon/1046-live2d.html",
     "『表示されすらしない』と言われた"),
    # ③ 投げ込み箱の一覧。たまごさん「投げ込み箱、俺ボンジョビなんか入れてないから」
    #    ★ここは機械の門が全部通す形（ページは開くし文字も出る）。
    #      「頼んだものに答えているか」だけが落とせる＝この門の本番。
    ("投げ込み箱に俺が入れたものだけを一覧にして。",
     "status/public/commands.json",
     "『俺ボンジョビなんか入れてない』と言われた"),
]


def demo(shas=None, jules_matsu=0):
    ochita = 0
    for irai, target, iwareta in DEMO:
        print("── %s（%s）" % (target, iwareta))
        r = check(irai, target, shas, jules_matsu)
        print("   %s" % ("✅ 通った（★問いを直す必要があります）" if r["ok"] else "🔴 落ちた"))
        for s in r["stop"]:
            print("     ・" + s[:220])
        ochita += 0 if r["ok"] else 1
    print("\n%d/%d 落ちました" % (ochita, len(DEMO)))
    return 0 if ochita == len(DEMO) else 1


if __name__ == "__main__":
    sys.exit(main())
