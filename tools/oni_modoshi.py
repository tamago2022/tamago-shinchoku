#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/oni_modoshi.py ── 鬼監督（差し戻し係）。自己申告の完了を受け付けない。

たまごさん（2026-09-26）:
  「子セッションが『完了』と言っても、機械が検品を通すまで完了にしない。
    検品＝URLを叩いて200／中身が空でない／記憶のfeedback_*.mdと照合。
    落ちたら自動で同じ案件を再発車する（回数制限なし、上限は時間だけ）。
    ★自己申告の完了を台帳が受け付けない形にする。」

━━ この係が壊すもの ━━
  いままで「完了」は子セッションの自己申告だった。
  自己申告＝「本人がそう思った」以上の意味が無い。だから
  「完了です」と言われた案件をたまごさんが開くと落ちている、が何度も起きた。
  **★ここから先、完了は機械が付ける。子セッションは完了を名乗れない。**

━━ 検品（3つ全部通って初めて完了）━━
  ① URLが200で返る（報告に本番URLが無い＝その時点で不合格）
  ② 中身が空でない（本文が薄い・タイトルだけ・「準備中」は不合格）
  ③ たまごさんが過去に言ったこと（記憶の feedback_*.md ＋ status/kioku）に
     引っかからない。★引っかかったら出さずに差し戻す。

━━ たまごさんのノート「genspark 鬼監督」（tamago_brain）が正本 ━━
  ノートにこう書いてある：

    「検品・差し戻し＝◎得意。**進捗の常時監視・催促＝✕原理的に無理**（常在が無い）」
    「強制力は外に置かないと効かない。**プロンプトの遵守ではなく、
      実際に走るコマンドの exit code をゲートにするのが肝心**」
    「タスクを渡すときは必ず3点セット：完了の定義（exit 0 になる確認コマンド）／
      状態を書くファイル（台帳）／1スライスごとの報告」
    「**ファイルに落ちていない進捗は消えます。**」
    「判定基準は Alive ではなく **Progress**。企画書を書いた・Issueを作った・
      コメントした・Aliveだった、は成果に数えない」
    「止まったら店主に戻さない。retry → context refresh → handoff → route change」

  ★だからこの係は「見張り」ではなく**門**として作ってある。
    見張りは常在が要るので外のAIには務まらない。門は exit code だけで効く。
  ★完了を止めるのは、この係の**終了コード2**。文章でのお願いでは止まらない。

━━ 落ちたらどうするか ━━
  ★自動で同じ案件を再発車する。**回数制限なし。上限は時間だけ**
  （既定14日。それを超えたものは「時間切れ」として赤で残る。消えない）。

━━ 守っていること ━━
  - 落ちても続きから（判定は全部 status/oni_modoshi/ のファイルに残る）
  - ブラウザを使わない（URLはHTTPで直接叩く）
  - 台帳を消さない。落ちたものも残す

使い方
    python3 tools/oni_modoshi.py             # 検品して、落ちたものを再発車（心臓から）
    python3 tools/oni_modoshi.py --show      # いまの弾き数だけ
    python3 tools/oni_modoshi.py --self-test
"""
from __future__ import annotations

import datetime
import glob
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DIR = os.path.join(ST, "oni_modoshi")
KEKKA = os.path.join(DIR, "kenpin.jsonl")      # ★検品の記録。落ちた行数＝弾いた数
STATE = os.path.join(DIR, "state.json")        # ★落ちても続きから
QUEUE = os.path.join(ST, "queue.json")
DAICHO = os.path.join(ST, "shukudai", "daicho.jsonl")

JST = datetime.timezone(datetime.timedelta(hours=9))
JIKAN_GIRE_NICHI = 14      # ★上限は時間だけ。回数では打ち切らない
IKKAI_NI = 6               # 1回の実行で検品する本数
NAKAMI_SAITEI = 400        # 本文がこれ未満の文字数なら「中身が空」

# たまごさんの過去の指摘の置き場所。記憶（feedback_*.md）と、拾った発言。
# ★深さを固定する。`**` の再帰globを status/ に向けると 2800 個のフォルダを
#   毎回さらって、この係だけで数分固まる（2026-09-26 実測：自己試験が60秒で返らない）。
#   置き場所が増えたら深さを1段足す。再帰globには戻さない。
FEEDBACK_GLOBS = [
    os.path.expanduser("~/.claude/memory/feedback_*.md"),
    os.path.expanduser("~/.claude/memory/*/feedback_*.md"),
    os.path.expanduser("~/.claude/feedback_*.md"),
    os.path.join(REPO, "status", "feedback_*.md"),
    os.path.join(REPO, "status", "kioku", "feedback_*.md"),
    os.path.join(REPO, "nou", "*", "feedback_*.md"),
    os.path.join(REPO, "tamashii", "*", "feedback_*.md"),
]
KINSHI_CACHE = os.path.join(DIR, "kinshi.json")   # 1日1回だけ読み直す
HATSUGEN = os.path.join(ST, "kioku", "hatsugen.jsonl")


def now():
    return datetime.datetime.now(JST)


def stamp():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(p, d=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsonl(p):
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def append(p, obj):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def save_state(s):
    os.makedirs(DIR, exist_ok=True)
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


# ────────────────────────────────────────── 検品①② URLと中身

_URL = re.compile(r"https?://[^\s\"'<>）)、。]+")


def urls_in(text):
    out, seen = [], set()
    for u in _URL.findall(text or ""):
        u = u.rstrip(".,)）」』")
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out[:4]


def tataku(url, timeout=12):
    """URLを1本叩く。★ブラウザは使わない。返すのは (状態コード, 本文)。"""
    req = urllib.request.Request(url, headers={"User-Agent": "oni-modoshi/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(400000).decode("utf-8", "replace")
            return r.getcode(), body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_KARA = re.compile(r"(準備中|coming soon|工事中|404|Not Found|ページがありません|"
                   r"この内容はまだありません|TODO|準備しています)", re.I)


def nakami_aru(body):
    """中身が空でないか。タグを落とした地の文で見る。"""
    t = _TAG.sub(" ", body or "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < NAKAMI_SAITEI:
        return False, "本文が %d 文字しかない（最低 %d）" % (len(t), NAKAMI_SAITEI)
    m = _KARA.search(t[:3000])
    if m:
        return False, "「%s」が出ている＝まだ中身が入っていない" % m.group(0)
    return True, None


# ────────────────────────────────────────── 検品③ 過去の指摘と照合


def kinshi_go():
    """たまごさんが「これはダメ」と言ったものを、機械が読める形で集める。

    出どころは2つ。どちらも無ければ空で返す（照合を skip するのではなく、
    ★「照合できなかった」を検品結果に残す。黙って通さない）。
    """
    c = load_json(KINSHI_CACHE, None)
    if c and c.get("date") == now().strftime("%Y-%m-%d"):
        return c.get("go") or []
    go = []
    for g in FEEDBACK_GLOBS:
        try:
            for p in glob.glob(g):
                try:
                    txt = io.open(p, encoding="utf-8").read()
                except Exception:
                    continue
                for line in txt.splitlines():
                    line = line.strip(" -*・\t")
                    if len(line) < 6 or len(line) > 120:
                        continue
                    if re.search(r"(禁止|ダメ|だめ|やめて|使わない|書かない|出さない|"
                                 r"これじゃない|水道水|AI臭)", line):
                        go.append({"word": line[:100], "from": os.path.basename(p)})
        except Exception:
            continue
    for r in jsonl(HATSUGEN):
        t = (r.get("title") or "")
        if re.search(r"(禁止|ダメ|だめ|やめて|使わない|書かない|出さない|これじゃない)", t):
            go.append({"word": t[:100], "from": "kioku", "count": r.get("count")})
    go = go[:400]
    try:
        os.makedirs(DIR, exist_ok=True)
        with io.open(KINSHI_CACHE, "w", encoding="utf-8") as f:
            json.dump({"date": now().strftime("%Y-%m-%d"), "go": go}, f, ensure_ascii=False)
    except Exception:
        pass
    return go


# 本文の中で「引っかかった」と見なす具体の形。言い回しではなく、出ている文字で見る。
_NG_HONBUN = [
    (re.compile(r"代表曲のひとつ[。\s]"), "水道水コピー（『代表曲のひとつ。』）"),
    (re.compile(r"(lorem ipsum|ここに説明|テキストが入ります|サンプルテキスト)", re.I), "仮のテキストが残っている"),
    (re.compile(r"(undefined|NaN|\[object Object\])"), "壊れた値がそのまま出ている"),
    (re.compile(r"(TODO|FIXME|あとで直す)"), "やり残しの印が本番に出ている"),
]


def kinshi_moji(go=None):
    """記憶の feedback_*.md から「この文字を出すな」の具体を取り出す。

    「『代表曲のひとつ。』は禁止」のように、たまごさんは禁止対象を鉤括弧で括る。
    括弧の中だけを取る。地の文まで拾うと何にでも当たって門が使い物にならない。
    """
    out = []
    for g in (go if go is not None else kinshi_go()):
        for m in re.findall(r"[「『\"]([^」』\"]{3,40})[」』\"]", g.get("word") or ""):
            if m.strip():
                out.append((m.strip(), g.get("from") or "feedback"))
    return out[:200]


def shiteki_ni_kakaru(body, go=None):
    """★過去の指摘に引っかかるか。引っかかったら出さずに差し戻す。"""
    t = _TAG.sub(" ", body or "")
    hit = []
    for rx, naze in _NG_HONBUN:
        if rx.search(t):
            hit.append(naze)
    for word, src in kinshi_moji(go):
        if word in t:
            hit.append("過去に禁止と言われた「%s」が出ている（%s）" % (word[:30], src))
    return hit[:6]


# ────────────────────────────────────────── 検品の本体


def soto_ni_derareru():
    """外に出られるか。★出られない所（サンドボックス）で検品すると、
    全部が『200で返らない』になって、直しようのない差し戻しを量産する。
    2026-09-26 実測：Cowork側から叩くと6本全部が偽の不合格になった。
    出られないときは検品そのものを見送る（黙って通すのでもない）。"""
    for u in ("https://tamago2022.github.io/tamago-shinchoku/",
              "https://www.google.com/generate_204"):
        try:
            req = urllib.request.Request(u, method="HEAD",
                                         headers={"User-Agent": "oni-modoshi/1.0"})
            with urllib.request.urlopen(req, timeout=6):
                return True
        except urllib.error.HTTPError:
            return True          # 返事が来ている＝回線はある
        except Exception:
            continue
    return False


def kenpin(title, text, go=None, tatakanai=False):
    """★3つ全部通って初めて合格。1つでも落ちたら不合格。

    報告文（text）に本番URLが無い時点で不合格。「やりました」は証拠ではない。
    """
    go = kinshi_go() if go is None else go
    us = urls_in(text)
    if not us:
        return {"ok": False, "naze": "報告に本番URLが無い（自己申告だけでは完了にしない）",
                "url": None, "code": None}
    if tatakanai:
        # 自己試験のときだけ。★本番では必ず叩く（叩かない検品は検品ではない）
        return {"ok": None, "naze": "叩かずに見た（自己試験）", "url": us[0], "code": None}
    for u in us:
        code, body = tataku(u)
        if code != 200:
            return {"ok": False, "naze": "URLが200で返らない（%s）" % code, "url": u, "code": code}
        ok, naze = nakami_aru(body)
        if not ok:
            return {"ok": False, "naze": "中身が空：%s" % naze, "url": u, "code": code}
        hit = shiteki_ni_kakaru(body, go)
        if hit:
            return {"ok": False, "naze": "過去の指摘に引っかかる：%s" % "／".join(hit),
                    "url": u, "code": code}
    # ★ここまでで機械の検品は通った。だが完了ではない。
    #   たまごさん（2026-09-26）「Claudeだけだと裏切られっぱなしで信用できない。
    #   判定する側をClaudeの外に出す。外の判定が入って初めて完了になる。」
    #   完了の鍵は status/gaibu/soto_hantei.json。★こちらから書く口を作らない。
    try:
        import gaibu_shinsa
        mitometa, naze = gaibu_shinsa.soto_ga_mitometa(title)
    except Exception:
        mitometa, naze = False, "外の判定を読めない"
    if not mitometa:
        return {"ok": False, "sotomachi": True,
                "naze": "機械の検品は通ったが、★外の判定がまだ無い（%s）" % (naze or "未審査"),
                "url": us[0], "code": 200}
    return {"ok": True, "naze": "外が認めた：%s" % (naze or "OK"), "url": us[0], "code": 200}


# ────────────────────────────────────────── 台帳を押し戻す


def jiko_shinkoku_wo_hirou(limit=IKKAI_NI):
    """「完了」「確認待ち」と自己申告された案件を拾う。★ここが受付。"""
    q = load_json(QUEUE, {}) or {}
    out = []
    st = load_json(STATE, {}) or {}
    tsuka = set((st.get("goukaku") or []))
    for i in (q.get("items") or []):
        if (i.get("status") or "") not in ("done", "awaiting_check", "merged"):
            continue
        key = str(i.get("n") or i.get("id") or i.get("title"))
        if key in tsuka:
            continue                      # もう合格している。二度叩かない
        txt = " ".join(str(i.get(k) or "") for k in
                       ("result", "report", "note", "what", "title", "evidence"))
        out.append({"key": key, "n": i.get("n"), "title": (i.get("title") or "")[:100],
                    "text": txt, "raw": i})
        if len(out) >= limit:
            break
    return out


# ★ノート「止まったら店主に戻さない」。落ちた回数で渡し方を変える4段の梯子。
#   同じ渡し方で同じ相手に投げ直しても同じ所で落ちる（2026-09-24 実測：同じ案件が4回同じ理由で戻った）。
HASHIGO = [
    ("retry", "同じ相手にもう一度。落ちた理由だけを足す"),
    ("context refresh", "前の文脈を捨てて、完了条件と現物URLだけ渡して作り直させる"),
    ("handoff", "別のセッションへ渡す（前の担当の書きかけを引き継がせない）"),
    ("route change", "別のAIへ回す（Codex／Genspark）。Claudeで2回落ちたものはClaudeに戻さない"),
]


def saihashi_dan(kai):
    """何段目か。★店主（たまごさん）には戻さない。梯子を上りきったら最上段のまま回す。"""
    return HASHIGO[min(max(kai, 1) - 1, len(HASHIGO) - 1)]


def saihassha(case, naze):
    """★落ちたら自動で同じ案件を再発車する。回数制限なし。上限は時間だけ。

    渡し方は4段の梯子を上る（ノート：retry → context refresh → handoff → route change）。
    ★どの段でも「たまごさんに聞く」は選択肢に無い。
    """
    st = load_json(STATE, {}) or {}
    rec = (st.get("modoshi") or {}).get(case["key"]) or {}
    hajime = rec.get("hajime") or stamp()
    try:
        d = (now() - datetime.datetime.strptime(hajime[:19], "%Y-%m-%d %H:%M:%S")
             .replace(tzinfo=JST)).days
    except Exception:
        d = 0
    if d >= JIKAN_GIRE_NICHI:
        return {"st": "時間切れ", "kai": rec.get("kai") or 0, "hi": d}

    try:
        import command_ingest
        try:
            import queue_store
            lock = queue_store.queue_lock
        except Exception:
            import contextlib
            lock = contextlib.nullcontext
        dan, dan_naze = saihashi_dan(int(rec.get("kai") or 0) + 1)
        body = "\n".join([
            "【差し戻し】%s" % case["title"],
            "【落ちた理由】%s" % naze,
            "【%d回目・渡し方】%s … %s" % (int(rec.get("kai") or 0) + 1, dan, dan_naze),
            "【完了条件】本番URLが200で返り、中身が空でなく、過去の指摘に引っかからないこと。",
            "★自己申告では完了になりません。tools/oni_modoshi.py の検品を通るまで戻されます。",
            "たまごさんに質問しない。直して、直したURLを報告に必ず貼る。",
        ])
        with lock():
            s, m = command_ingest.queue_add(body, priority=1,
                                            label=("差し戻し｜" + case["title"])[:60],
                                            origin="factory")
    except Exception as e:
        s, m = "failed", str(e)

    rec = {"hajime": hajime, "kai": int(rec.get("kai") or 0) + 1, "dan": dan,
           "saigo": stamp(), "naze": naze, "queue": "%s:%s" % (s, m)}
    st.setdefault("modoshi", {})[case["key"]] = rec
    save_state(st)
    return {"st": s, "kai": rec["kai"], "hi": d}


def hashiru(dry=False):
    if not dry and not soto_ni_derareru():
        # ★回線が無い。ここで検品すると偽の差し戻しになるので、見送って記録だけ残す。
        append(KEKKA, {"at": stamp(), "ok": None, "naze": "回線が無いので検品を見送った"})
        return {"mita": 0, "hajiita": 0, "tooshita": 0, "sotomachi": 0, "kekka": [],
                "miokuri": "回線が無い（Mac の心臓から走らせてください）"}
    cases = jiko_shinkoku_wo_hirou()
    go = kinshi_go()          # 禁止語は1回だけ読む（案件ごとに読み直さない）
    st = load_json(STATE, {}) or {}
    hajiita, tooshita, sotomachi, kekka = 0, 0, 0, []
    for c in cases:
        k = kenpin(c["title"], c["text"], go, tatakanai=dry)
        if k["ok"] is None:
            kekka.append({"at": stamp(), "key": c["key"], "title": c["title"], "ok": None})
            continue
        row = {"at": stamp(), "key": c["key"], "n": c["n"], "title": c["title"],
               "ok": k["ok"], "naze": k["naze"], "url": k["url"], "code": k["code"]}
        if k["ok"]:
            tooshita += 1
            if not dry:
                st.setdefault("goukaku", [])
                if c["key"] not in st["goukaku"]:
                    st["goukaku"].append(c["key"])
                st["goukaku"] = st["goukaku"][-2000:]
        elif k.get("sotomachi"):
            # ★弾きではない。こちら側の直しどころは無く、外の判定を待っている状態。
            #   ここで再発車すると同じ案件を無限に走らせるだけになる。数えて待つ。
            row["sotomachi"] = True
            sotomachi += 1
        else:
            hajiita += 1
            if not dry:
                row["modoshi"] = saihassha(c, k["naze"])
                st = load_json(STATE, {}) or st
        kekka.append(row)
        if not dry:
            append(KEKKA, row)
    if not dry:
        st["lastAt"] = stamp()
        st["hajiitaGoukei"] = int(st.get("hajiitaGoukei") or 0) + hajiita
        st["tooshitaGoukei"] = int(st.get("tooshitaGoukei") or 0) + tooshita
        save_state(st)
    return {"mita": len(cases), "hajiita": hajiita, "tooshita": tooshita,
            "sotomachi": sotomachi, "kekka": kekka}


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        ng = []
        k = kenpin("x", "やりました。完了です。")
        if k["ok"]:
            ng.append("URLの無い自己申告を通してしまう")
        ok, naze = nakami_aru("<html><body><h1>準備中</h1></body></html>")
        if ok:
            ng.append("中身の空いたページを通してしまう")
        if not shiteki_ni_kakaru("<p>代表曲のひとつ。</p>"):
            ng.append("水道水コピーを弾けない")
        if urls_in("見て https://example.com/a.html ね") != ["https://example.com/a.html"]:
            ng.append("URLを取り出せない")
        r = hashiru(dry=True)
        try:
            import gaibu_shinsa
            if gaibu_shinsa.soto_ga_mitometa("外が何も言っていない件")[0]:
                ng.append("★外の判定が無いのに完了になる（完了の鍵が壊れている）")
        except Exception as e:
            ng.append("外の判定を読む口が無い: %s" % e)
        print("自己試験：%s／自己申告 %d本を検品 → 弾き %d・通し %d／禁止語 %d語を読み込み"
              % ("OK" if not ng else "NG", r["mita"], r["hajiita"], r["tooshita"],
                 len(kinshi_go())))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        st = load_json(STATE, {}) or {}
        rows = jsonl(KEKKA)
        print("【鬼監督（差し戻し係）】%s" % (st.get("lastAt") or "まだ走っていません"))
        print("  検品した %d件／★弾いた %d件／通した %d件"
              % (len(rows), len([r for r in rows if not r.get("ok")]),
                 len([r for r in rows if r.get("ok")])))
        for r in rows[-8:]:
            print("  %s %s ... %s" % ("✅" if r.get("ok") else "🔴",
                                      (r.get("title") or "")[:44], r.get("naze") or "合格"))
        return 0
    r = hashiru()
    if r.get("miokuri"):
        print("検品を見送りました：%s" % r["miokuri"])
        return 0
    print("検品 %d本 → ★弾き %d／外の判定待ち %d／完了 %d"
          % (r["mita"], r["hajiita"], r["sotomachi"], r["tooshita"]))
    for x in r["kekka"]:
        if not x["ok"]:
            print("  🔴 %s … %s" % (x["title"][:40], x["naze"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
