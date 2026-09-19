#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番【本丸】共有ブリーフ — 「どこに話に行っても話が通じる」の実体。

たまごさんの言葉（2026-09-18・原文）:
  「1番望んでるのは、どこに話に行っても話が通じるってことだね。全部が筒になってるっていう状態。」
  「GrokでLINEスタンプ修正したんだけど『誰か申請まで投げれますか？』って言ったら
    『僕ができます』とか『こういうやり方がありました』とか、個別に聞いてるのがめちゃくちゃ面倒くさいのよ。」

■ これは何か
  外部AI（Grok / ChatGPT / Gemini）に何かを聞く・頼むとき、**必ず先頭に付ける1枚**。
  向こうは記憶を持っていないので、これが無いと毎回ゼロから説明することになる。
  これを付けると「915号の件だけど」で話が通じる。

■ 正本はどこか（手で書かない）
  status/queue.json … 案件の一覧・状態・号番号
  status/genzaichi.md … 今の数字（クレジット・残タスク・止まっているもの）
  status/REPEATED_UNFIXED.md … 何度も直っていないこと（= 制約の実体）
  このスクリプトはそれらを読んで **生成するだけ**。ここを手で書き換えても次回上書きされる。

■ 出力
  status/kyoyu_brief.md  … Claude/機械が読む用
  status/kyoyu_brief.txt … ★たまごさんが他社の画面にそのまま貼る用（.mdは向こうで開けない）

■ 使い方
  python3 tools/kyoyu_brief.py                # 両方を書き出す
  python3 tools/kyoyu_brief.py --print        # 標準出力に出す（他のツールが取り込む用）
  python3 tools/kyoyu_brief.py --n 915        # 915号を「今この話をしている」として先頭に立てる
  python3 tools/kyoyu_brief.py --max-cases 12 # 載せる案件数
"""
import argparse
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

QUEUE = os.path.join(REPO, "status", "queue.json")
GENZAICHI = os.path.join(REPO, "status", "genzaichi.md")
REPEATED = os.path.join(REPO, "status", "REPEATED_UNFIXED.md")
OUT_MD = os.path.join(REPO, "status", "kyoyu_brief.md")
OUT_TXT = os.path.join(REPO, "status", "kyoyu_brief.txt")

# ---------------------------------------------------------------------------
# 決まっている制約。
# ここだけは「実行のたびに変わらないもの」なので定数で持つ。
# 出典はたまごさんの発言および status/REPEATED_UNFIXED.md / CLAUDE.md。
# 増やすときは「外部AIが知らないと事故るもの」だけにする（長くすると読まれない）。
# ---------------------------------------------------------------------------
SEIYAKU = [
    "本番アプリ(ごきげん補給所)はLovableで作られている。**Lovableのチャット欄にプロンプトを打たせる案は出さない。**"
    "コードはローカルのクローン(/Users/mac/Desktop/joy-relief-station)を直接編集してgit pushする。",
    "**Braveブラウザのタブは絶対に触らない・閉じない。**たまごさんの作業中タブが消えるため。",
    "報告は**1行＋URL**。長い説明は要らない。作ったものは必ず「見に行けるURL」を添える。",
    "**お金を使う前に必ず見積もりを出して止まる。**実費は必ず「円」で報告する。新規のサブスク契約はしない。",
    "たまごさんは**非エンジニア**。専門用語で説明しない。手順は1つずつ。",
    "**アカウント作成・パスワード入力はAI側でやらない。**既にログイン済みのものだけ使う。",
    "「できました」で終わらせない。**実測値（URL・スクショ・秒数・円）を出して初めて完了**。",
    "作ったものは**たまごさんに見せる前に外部AIの検品ゲート(tools/kenpin_gate.py)を通す。**",
]

# 外部AIが混乱しやすい固有名詞。1行ずつ。
YOUGO = [
    "ごきげん補給所 / 卵商店街 … たまごさんが運営する音楽・映像のWebアプリ（本番はLovable上）",
    "名カバー案内所 … ごきげん補給所の中の、カバー曲を紹介する棚",
    "Eden Loop … たまごさんの思想プロジェクト。管理型社会から自律調和型社会への移行",
    "カガリビト … 2035年のAIと子どもを描く映像作品",
    "号番号 … 案件の通し番号。status/queue.json の n がそのまま正本。『915号』のように呼ぶ",
    "工場 … たまごさんのMac上で5分おきに回っている自動処理群（tools/machine_status_push.sh）",
    "Dispatch … スマホとデスクトップをまたいで同じ話を続ける仕組み",
    "鬼監督 … 出す前に自分で落とすための自己検品の役",
]


def _read(path, limit=None):
    try:
        s = io.open(path, encoding="utf-8", errors="ignore").read()
        return s[:limit] if limit else s
    except Exception:
        return ""


def _load_queue():
    try:
        q = json.load(io.open(QUEUE, encoding="utf-8"))
    except Exception:
        return []
    return q.get("items") or [] if isinstance(q, dict) else (q or [])


def _clean(s, limit=160):
    """依頼本文は絵文字の警告ブロックや長い経緯で膨らんでいる。外部AIに渡す1行に落とす。"""
    s = (s or "").replace("\r", "")
    # 🚨で囲まれた警告ブロック・見出し記号を落とす
    s = re.sub(r"🚨[^\n]*\n", "", s)
    s = re.sub(r"^#+\s*", "", s, flags=re.M)
    s = re.sub(r"\*\*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _state_ja(it):
    st = it.get("state")
    stat = it.get("status")
    if st == "passed":
        return "検品PASS"
    if st == "fix_required":
        return "検品が直せと言っている"
    if st == "submitted":
        return "検品に出した"
    if stat == "running":
        return "走行中"
    if stat == "done":
        return "完了"
    if stat == "awaiting":
        return "たまごさんの確認待ち"
    if stat == "hold":
        return "保留"
    return "発車待ち"


def _num(v, default):
    """★2026-09-20 修理：台帳の priority / n が文字列("2" や "高" や "")で入っていることがあり、
    そのまま数と比べると TypeError で共有ブリーフごと落ちる（＝kiku も tanomu も丸ごと死ぬ）。
    数にできるものは数に、できないものは default に倒す。ここで絶対に例外を出さない。"""
    if v is None or v is True or v is False:
        return default
    if isinstance(v, (int, float)):
        return v
    try:
        return int(str(v).strip())
    except Exception:
        pass
    try:
        return float(str(v).strip())
    except Exception:
        return default


def _pick_cases(items, max_cases, focus_n=None):
    """いま話題になりうる案件だけを選ぶ。全部載せると読まれない。"""
    def rank(it):
        stat = it.get("status")
        st = it.get("state")
        score = 0
        if stat == "running":
            score -= 100
        if st in ("fix_required", "submitted"):
            score -= 50
        if stat == "awaiting":
            score -= 40
        if it.get("urgent"):
            score -= 30
        if _num(it.get("priority"), 9) <= 2:
            score -= 10
        if stat == "done":
            score += 200
        return (score, -_num(it.get("n"), 0))

    pool = [it for it in items if it.get("status") != "done"]
    pool.sort(key=rank)
    picked = pool[:max_cases]
    if focus_n:
        hit = [it for it in items if it.get("n") == focus_n]
        if hit and hit[0] not in picked:
            picked = hit + picked[: max_cases - 1]
        elif hit:
            picked = hit + [x for x in picked if x is not hit[0]]
    return picked


def _numbers_block():
    """genzaichi.md から数字の節だけを抜く（全文は長すぎる）。"""
    g = _read(GENZAICHI)
    if not g:
        return "（数字は取得できませんでした）"
    out = []
    grab = False
    for line in g.splitlines():
        if line.startswith("## 数字"):
            grab = True
            continue
        if grab:
            if line.startswith("## "):
                break
            if line.strip():
                out.append(line.strip())
    return "\n".join(out) if out else "（数字は取得できませんでした）"


def _stuck_block():
    g = _read(GENZAICHI)
    out = []
    for line in g.splitlines():
        if line.strip().startswith("- 🔴") or line.strip().startswith("- ⚠️"):
            out.append(line.strip())
    return "\n".join(out[:4])


def build(max_cases=12, focus_n=None, for_txt=False):
    items = _load_queue()
    cases = _pick_cases(items, max_cases, focus_n)
    now = time.strftime("%Y-%m-%d %H:%M")

    L = []
    A = L.append
    A("===== たまご工場・共有ブリーフ（%s 自動生成）=====" % now)
    A("")
    A("これは、たまご（宗形宏平／ひとりで映像・Webを作っている人）の作業場の現在地です。")
    A("あなたは今からこの人の仕事を手伝います。以下を前提として読んでから答えてください。")
    A("**知らないことを知っているふりで埋めないでください。**分からなければ『分からない』と言ってください。")
    A("")

    if focus_n:
        hit = [it for it in items if it.get("n") == focus_n]
        if hit:
            it = hit[0]
            A("■ 今この話をしています → **%s号：%s**" % (focus_n, it.get("title") or ""))
            A("　状態：%s" % _state_ja(it))
            w = _clean(it.get("what"), 400)
            if w:
                A("　中身：%s" % w)
            A("")

    A("■ いま動いている案件（号番号で呼びます）")
    if not cases:
        A("　（なし）")
    for it in cases:
        n = it.get("n")
        line = "　%s号 [%s] %s" % (n, _state_ja(it), (it.get("title") or "").strip())
        A(line[:200])
        w = _clean(it.get("what"), 110)
        if w:
            A("　　　→ %s" % w)
    A("")

    A("■ 今日の数字")
    A(_numbers_block())
    A("")

    st = _stuck_block()
    if st:
        A("■ 詰まっているところ")
        A(st)
        A("")

    A("■ 決まっている制約（これを破る案は出さないでください）")
    for i, s in enumerate(SEIYAKU, 1):
        A("　%d. %s" % (i, s))
    A("")

    A("■ 固有名詞")
    for s in YOUGO:
        A("　・%s" % s)
    A("")

    A("■ 答え方")
    A("　・結論を先に1行。理由はその後。")
    A("　・日本語で。専門用語を使うときは必ずカッコで言い換えを添える。")
    A("　・URLを出すときは公式のものだけ。見つからなければ『無い』と書く。")
    A("　・推測で書いた箇所には必ず『推測』と明記する。")
    A("===== ここまでが前提。以下が今回の用件 =====")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--max-cases", type=int, default=12)
    ap.add_argument("--print", dest="do_print", action="store_true")
    a = ap.parse_args()

    body = build(max_cases=a.max_cases, focus_n=a.n)
    if a.do_print:
        sys.stdout.write(body)
        return 0

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("<!-- tools/kyoyu_brief.py が自動生成。手で書き換えない。 -->\n\n```\n")
        f.write(body)
        f.write("\n```\n")
    with io.open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(body)
        f.write("\n")
    print("書きました:")
    print("  " + OUT_MD)
    print("  " + OUT_TXT + "  ←★これを他社の画面に貼る")
    print("  %d文字 / 案件%d件" % (len(body), min(a.max_cases, len(_load_queue()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
