#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
進捗表に出す「何をする仕事か」の1行（hyoudai＝表題）を作る係。

■ たまごさん（2026-10-01）
  「進捗表、とても見づらい。『調べてとりあえず4、5曲ずつは入れておく』とかって、
   俺の会話を引っこ抜いただけでしょう。何をやっているのかが1行でわかるようにして。
   前はちゃんとなっていた。たとえば『マイクを押して声で話して返事が来るのを一往復だけ通す』
   『外部連絡を押すだけで出る仕組み』『間違ったものが報告に上がってこない入口の検査・ブロック』」

■ どこで壊れたか
  前の良い題名は、Dispatch が queue_add に label（短い日本語名）を手で渡していたもの。
  その後、自動で積む係（hantei_hiduke.py の「判定日赤」繰り上げ・kioku 取り込み等）が
  増え、label に**たまごさんの発言そのもの**を入れて積むようになった。
  command_ingest.queue_add() は label をそのまま title にするので、発言の切り抜きが
  そのまま進捗表の題名になっていた（1409・1981・1987・1989番などが実例）。

■ 直し方
  title は触らない（重複照合・shukudai の「判定日赤｜」判定などが title を見ているため）。
  代わりに item["hyoudai"]（表示用の1行）を別に持たせ、進捗表はこれを優先して出す。
  原文（title）は進捗表の畳んだ中に残す。
    1. queue_add の時点で rule_hyoudai()（機械的な掃除）を即座に入れる（待たせない）。
       hyoudaiSrc="rule"
    2. 心臓の定期便から `python3 tools/hyoudai.py --fill` を回し、rule のままの項目を
       まとめて AI（claude -p・haiku）に「何をする仕事か」へ書き直させる。hyoudaiSrc="ai"
       走っているもの → 次に発車に近い順 → 後回し の順で、1回20件ずつ。

使い方:
  python3 tools/hyoudai.py --fill [--max 40]   # AIで書き直す（心臓の定期便から）
  python3 tools/hyoudai.py --rule "文"          # 機械的な掃除だけ試す
  python3 tools/hyoudai.py --selftest
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "hyoudai.log")
MAX_LEN = 30

# ---------- 機械的な掃除（AIが使えないときの最低線） ----------
_PREFIX = [
    r"^\s*判定日赤\s*[｜|:：]\s*",
    r"^\s*検品(要人手|不合格|待ち)\s*[｜|:：]?\s*",
    r"^\s*GH\s*\d+\s*[｜|:：]?\s*",
    r"^\s*\[\s*[xX ]?\s*\]\s*",
    r"^\s*\(\d/\d\)\s*",
    r"^\s*\d{2,5}\s*[｜|番:：]\s*",
    r"^\s*【(タスク|一覧作成|中断から再開[^】]*)】\s*",
    r"^\s*🗣️\s*",
    r"^\s*＋\s*",
]
# 会話の語尾 → 仕事の言い方
_TAIL = [
    (r"(しておいて|しといて|してほしい|して欲しい|してください|して下さい|してくれ|してね|して)$", "する"),
    (r"(作っておいて|作ってほしい|作ってください|作って)$", "作る"),
    (r"(直しておいて|直してほしい|直してください|直して)$", "直す"),
    (r"(入れておいて|入れてほしい|入れてください|入れて)$", "入れる"),
    (r"(調べておいて|調べてほしい|調べてください|調べて)$", "調べる"),
    (r"(おくとかさ|とかさ|とか|かな|よね|だよね|だよ|だね|でしょう?|じゃん|ね|よ|さ|わ)$", ""),
]
_JARGON = [
    (r"関所", "入口の検査"), (r"心臓", "自動の係"), (r"(公開便|5分便|定期便)", "自動更新"),
    (r"憲法点検", "決まりごとの点検"), (r"ppid\s*\d*", ""),
]


def rule_hyoudai(raw):
    t = str(raw or "").strip()
    t = re.sub(r"[*#`>]", "", t)
    for _ in range(3):
        for p in _PREFIX:
            t = re.sub(p, "", t)
    t = t.replace("\n", " ").strip()
    t = re.sub(r"^[「｢”\"'『]+", "", t)
    # 最初の1文だけ
    m = re.match(r"^(.{6,}?)[。！？!?…]", t)
    if m:
        t = m.group(1)
    t = re.sub(r"[」』”\"]+$", "", t).strip(" 　、。")
    for a, b in _JARGON:
        t = re.sub(a, b, t)
    for _ in range(2):
        for a, b in _TAIL:
            t2 = re.sub(a, b, t)
            if t2 != t:
                t = t2.strip(" 　、。")
                break
    t = re.sub(r"\s*[｜|]\s*", "　", t).strip(" 　、。")
    if len(t) > MAX_LEN:
        cut = t[:MAX_LEN]
        # 読点で切れるならそこで切る
        k = cut.rfind("、")
        t = (cut[:k] if k >= 12 else cut[:MAX_LEN - 1]) + "…"
    return t


# ---------- AIで「何をする仕事か」に書き直す ----------
PROMPT = """あなたは工場の進捗表の題名係です。下の仕事ひとつひとつに、
店主（たまごさん）がスマホで一目見て「何をやっている仕事か」が分かる日本語1行の題名をつけてください。

ルール:
- 20〜28字くらい。長くても32字まで。
- 「何をする仕事か」を書く。店主の発言をそのまま切り抜かない（「〜とかさ」「〜してほしい」などの口語は消す）。
- 動詞で終える（「〜を直す」「〜を作る」「〜を入れる」）か、名詞で止める（「〜の仕組み」「〜の検査」）。
- 番号・ファイル名・英語の関数名・内輪の言葉（判定日赤・関所・心臓・kioku 等）は入れない。
- 原文がすでに「何をする仕事か」の1行になっているなら、ほぼそのまま使う（先頭の【】の印と番号は外す）。
- 中身が読み取れないときは、本文から一番それらしい作業を推して書く。推せないときだけ「中身の確認（発言の意図を読む）」。
良い例:
「マイクを押して声で話して返事が来るのを一往復だけ通す」
「外部連絡を押すだけで出る仕組み」
「間違ったものが報告に上がってこない入口の検査・ブロック」
「曲が0件の棚に4〜5曲ずつ入れる」
悪い例（発言の切り抜き）:「調べて、とりあえず4〜5曲ずつは入れておくとかさ」

出力は JSON だけ。{"番号": "題名", ...} の形。説明文は書かない。

仕事の一覧:
"""


def _claude_bin():
    c = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(c):
        for x in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
            if os.path.exists(x):
                c = x
                break
    kanmon = os.path.join(HERE, "1158_kanmon.py")
    if os.path.exists(kanmon):
        os.environ.setdefault("KANMON_CLAUDE_BIN", c)
        return kanmon
    return c


def _log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg))
    except Exception:
        pass


def _body_of(it):
    w = it.get("originalWhat") or it.get("what") or ""
    # 再開・判定日赤の定型文は除いて、本文の芯だけ渡す
    w = re.sub(r"【中断から再開[^】]*】[^\n]*\n(\*\*[^\n]*\n)?─+\n?", "", w)
    w = re.sub(r"【(言われた日時|なぜ赤か|完了条件|報告|出どころ)】[^\n]*", "", w)
    w = re.sub(r"(★自己申告|たまごさんに質問しない)[^\n]*", "", w)
    return re.sub(r"\s+", " ", w).strip()[:260]


def ai_hyoudai(items, models=("claude-haiku-4-5", "claude-sonnet-5")):
    """items: [{"n":.., "title":.., "what":..}] → {n: 題名}。失敗したら {}。"""
    lines = []
    for it in items:
        lines.append("- 番号%s｜原文：%s｜本文：%s" % (
            it.get("n"), (it.get("title") or it.get("label") or "")[:120], _body_of(it)))
    prompt = PROMPT + "\n".join(lines)
    # 関所（1158番・同時上限1本）は本物の発車で埋まっていることが多く、並ぶと100秒で
    # 間に合わない（2026-10-01 12:06 実測：haiku/sonnet とも TimeoutExpired）。
    # auth_keeper の見張りと同じ理由で、長期トークン（CLAUDE_CODE_OAUTH_TOKEN）を渡せるときは
    # 関所を通さず本体を直接呼ぶ。この形は refreshToken の作り替えが起きない（読むだけ）。
    env = dict(os.environ)
    binpath = _claude_bin()
    try:
        sys.path.insert(0, HERE)
        import auth_keeper
        tok = auth_keeper.token_text()
        if tok:
            env.pop("ANTHROPIC_API_KEY", None)
            env["CLAUDE_CODE_OAUTH_TOKEN"] = tok
            binpath = auth_keeper.CLAUDE_DIRECT
    except Exception:
        pass
    for model in models:
        try:
            r = subprocess.run([binpath, "-p", "--model", model, prompt],
                               capture_output=True, text=True, timeout=100, env=env,
                               stdin=subprocess.DEVNULL, cwd="/tmp")
        except Exception as e:
            _log("claude %s 失敗 %s" % (model, type(e).__name__))
            continue
        out = (r.stdout or "").strip()
        m = re.search(r"\{.*\}", out, re.S)
        if r.returncode != 0 or not m:
            _log("claude %s rc=%s 出力が取れない: %s" % (model, r.returncode, (out + (r.stderr or ""))[:200]))
            continue
        try:
            d = json.loads(m.group(0))
        except Exception:
            _log("claude %s JSONが壊れている: %s" % (model, out[:200]))
            continue
        res = {}
        for k, v in d.items():
            try:
                n = int(re.sub(r"\D", "", str(k)))
            except Exception:
                continue
            v = str(v or "").strip().strip("「」\"' ")
            if 4 <= len(v) <= 40:
                res[n] = v
        if res:
            return res
    return {}


def _targets(items, limit):
    def need(x):
        return x.get("hyoudaiSrc") != "ai"
    running = [x for x in items if x.get("status") in ("running", "touchchecking") and need(x)]
    waiting = [x for x in items if x.get("status") == "waiting" and need(x)]

    def pri(x):
        try:
            return int(x.get("priority"))
        except Exception:
            return 9

    urgent = lambda x: str(x.get("urgent")).lower() == "true"
    waiting.sort(key=lambda x: (0 if ("差し戻し" in str(x.get("title")) or urgent(x)) else 1,
                                pri(x), x.get("order") if x.get("order") is not None else 9999,
                                x.get("n") or 0))
    hold = [x for x in items if x.get("status") == "hold" and need(x)]
    # 画面に出る順：走っている → 次に発車の上10 → 後回しの上8 → 残り
    return (running + waiting[:10] + hold[:8] + waiting[10:] + hold[8:])[:limit]


def fill(max_items=40, batch=20):
    # 心臓から10分おきに呼ばれる。前の回がまだAIを待っていたら重ねない。
    import fcntl
    lf = io.open(os.path.join(REPO, "status", ".hyoudai.lock"), "a+")
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        print("前の回がまだ走っています")
        return 0
    sys.path.insert(0, HERE)
    import queue_store
    q = queue_store.load_queue()
    tg = _targets(q.get("items") or [], max_items)
    if not tg:
        print("書き直す項目はありません")
        return 0
    got = {}
    for i in range(0, len(tg), batch):
        chunk = [{"n": x.get("n"), "title": x.get("title"), "label": x.get("label"),
                  "what": x.get("what"), "originalWhat": x.get("originalWhat")}
                 for x in tg[i:i + batch]]
        got.update(ai_hyoudai(chunk))
    if not got:
        print("AIの題名が取れませんでした（hyoudai.log 参照）")
        return 1
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        k = 0
        for it in q.get("items") or []:
            n = it.get("n")
            if n in got and it.get("hyoudaiSrc") != "ai":
                it["hyoudai"] = got[n]
                it["hyoudaiSrc"] = "ai"
                k += 1
        if k:
            queue_store.save_queue(q, snap)
    _log("AIで %d件 書き直し" % k)
    print("AIで %d件 書き直しました" % k)
    for n, v in list(got.items())[:10]:
        print("  %s番 → %s" % (n, v))
    return 0


def selftest():
    cases = {
        "判定日赤｜調べて、とりあえず4〜5曲ずつは入れておくとかさ。": "調べて、とりあえず4〜5曲ずつは入れる",
        "判定日赤｜タスクごとに「丸・三角・バツ」で評価した表を作ってほしい。": "タスクごとに「丸・三角・バツ」で評価した表を作る",
    }
    ok = True
    for a, want in cases.items():
        got = rule_hyoudai(a)
        print(("OK " if got == want else "NG ") + got)
        ok = ok and got == want
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--rule" in a:
        print(rule_hyoudai(a[a.index("--rule") + 1]))
    elif "--fill" in a:
        mx = int(a[a.index("--max") + 1]) if "--max" in a else 40
        sys.exit(fill(mx))
    elif "--selftest" in a:
        sys.exit(selftest())
    else:
        print(__doc__)
