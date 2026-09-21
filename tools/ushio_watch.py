#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1019番：牛尾剛さんの発信を毎日ひとりでに拾って「うちもこうやる」まで書く常設の係。

たまごさんの言葉（そのまま）：
「牛尾さんって言ってるのは、自分の知る限り世界のトップエンジニアが周辺にいる人、その真ん中に
 いる人だから。常にアップデートされてるだろうからキャッチアップして。そういうリサーチャーみたい
 なのが必要。言ったら勝手にリサーチが走ってて、何時間後に『今こうやってますから、うちもこう
 やります』と報告が来る位にしたい。」

設計の縛り（たまごさん指定・koushiki_update_watch.py と同じ形に揃えてある）：
  - **定期タスク（scheduled task）は作らない。新しいlaunchd便も作らない。**
    心臓（tools/heartbeat.sh）に相乗りし、実際に外へ出るのは1日1回だけに間引く。
  - **拾って終わりにしない。**1件ごとに「だからうちはこうする」を必ず1つ付ける。
    付けられないものは **載せない**。代わりに status/queue.json の発車待ちへ
    「打ち手を書く」仕事として自分で積む（＝人が押さなくても次が回る）。
  - **走った回数と拾えた件数の両方を数える。**走行>0 なのに 拾えた=0 は赤。
    （mac_souji.py と同じ考え方。「動いているのに何も取れていない」が一番たちの悪い壊れ方）
  - **出典リンク必須。裏が取れないものは書かない。**本文を長く引き写さない（題名＋URLまで）。
  - **英語を出すときは日本語も併記。**

拾う先（許可リストで機械的に縛る。ここに無いホストは絶対に見に行かない）：
  1. note（note.com/simplearchitect）… 本人の一次発信。新刊の告知もここに出る
  2. 本人の記事の中から外に張られたリンク … ＝「本人が紹介している世界トップの実践」
  3. X（@sandayuu）… 認証なしで読める公開タイムラインだけ。取れなければ sourceErrors に残す
  ※文藝春秋BOOKSは2026-09-22に外した。著者ページから本の一覧が機械で読めず0件のままで、
    **永久に赤を出し続ける取得元を置いておくのは害**だと判断した。新刊はnoteの告知で取れている。

出す先：status/public/ushio_watch.json（進捗表とcheckページが読む）
  {"updatedAt","runs","pickedTotal","pickedThisRun","heldTotal","red",
   "items":[{"date","source","title","url","uchi","where"}],
   "held":[{...}], "sourceErrors":[...], "perSource":{取得元:{読めた,打ち手つき}}}

手で今すぐ動かしたいとき：
  python3 tools/ushio_watch.py --now       # 間引きを無視して即取得
  python3 tools/ushio_watch.py --dry-run   # 取るだけで書き込まない
  python3 tools/ushio_watch.py --selftest  # 外に出ずに配線だけ確かめる
"""
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 公開先は status/public/ 配下でなければならない（.gitignore が status/* を除外し、
# status/public/ だけを明示的に例外化している＝890番・896番の巻き戻り対策）。
OUT = os.path.join(ROOT, "status", "public", "ushio_watch.json")
MARKER = os.path.join(ROOT, "status", ".ushio_watch_last")
QUEUE = os.path.join(ROOT, "status", "queue.json")
JST = timezone(timedelta(hours=9))
KEEP = 60
TIMEOUT = 25
UA = "tamago-shinchoku/1.0 (ushio_watch)"

ALLOWED_HOSTS = (
    "note.com",
    "syndication.twitter.com",
    "books.bunshun.jp",
    "bunshun.jp",
)

NOTE_USER = "simplearchitect"
X_HANDLE = "sandayuu"

# ── 「だからうちはこうする」の対応表 ──
# 拾った題名・本文にこの語が当たったら、その打ち手をそのまま付ける。
# ★ここに当たらないものは載せない（推測で打ち手を作らない）。発車待ちへ積んで人ではなくAIが書く。
# 「うちのどのファイルを変えるか」まで書いておく＝読んだ人がすぐ手を動かせる。
UCHI_RULES = [
    (("レビュー", "プルリク", "pull request", "ボトルネック", "負担", "スローダウン"),
     "うちの1号を小さく割る。号のまま検品に出すのをやめ、"
     "「1号＝たまごさんが1画面で可否を返せる大きさ」を超えたら自動で分割する。",
     "tools/kenpin_gate.py ／ status/queue.json の1件あたりの大きさ判定"),
    (("小さく", "分割", "スタック", "stack", "小さいPR"),
     "確認ページを1枚に詰め込むのをやめる。1枚＝判断1つ。"
     "束ねたいときは親ページからリンクで積む（＝スタックPRと同じ形）。",
     "share/check/ の作り方 ／ tools/make_check_page.py"),
    (("コンテキスト", "context", "トークン", "token", "端的", "余分な情報", "ローカル参照"),
     "Dispatchの指示文に前提を長文で貼るのをやめ、参照はローカルのファイルに置いて指し示す。"
     "遠くのURLを読ませるより手元のコピーの方が正確に扱われる。",
     "tools/session_preamble.md ／ skills/tamago-unyou-os（§9の指示文テンプレート）"),
    (("チュートリアル", "理解", "解像度", "メンタルモデル", "ディープリーディング", "アーキテクチャ"),
     "新しいセッションが工場に入る前に、工場の構造を「簡素化したチュートリアル」として"
     "自分で書かせる。読ませるのではなく手で動かさせる。",
     "tools/session_preamble.md に『工場の歩き方』を1枚追加"),
    (("ハーネス", "harness", "ルールファイル", "制約", "やってはいけない", "ガードレール"),
     "禁止と最低ルールを増やす方向で効かせる。できることを足すより、"
     "やってはいけないことを機械で塞ぐ（関所を増やす）。",
     "tools/sekisho.py ／ tools/kagi_gate.py ／ skills の関所スキル"),
    # ★2026-09-22 実測：ここを「履歴/思考/なぜ/理由」のような普通の日本語にしていたため、
    #   ギターの記事と対談の記事にまでこの打ち手が付いた。**熟語だけに絞る。**
    (("思考の履歴", "思考履歴", "ヒストリ", "history", "エージェントの動きをレビュー", "trace"),
     "エージェントの思考の履歴を毎日1本だけ読み返す係を置く。"
     "「なぜそう動かなかったか」を本人に聞いて、その答えを関所に足す。",
     "status/作業ログ_自動記録.md を読む係（tools/ushio_watch.py に相乗り）"),
    (("失敗", "テスト駆動", "tdd", "レッド", "グリーン", "自動化"),
     "失敗を先に自動化する。直す前にまず「同じ壊れ方を検知する1行」を足してから直す。",
     "tools/test_*.py ／ status/failures.jsonl（tools/failures_ledger.py）"),
    (("スキル", "skill", "パッケージ", "繰り返し"),
     "2回以上同じ指示を書いたら、その場でスキルに固める（＝たまごさんに2回言わせない）。",
     "skills/ 直下に新規スキル ／ mcp__cowork__save_skill"),
    (("介入", "人間の介入", "どこまで任せ", "自動マージ", "承認"),
     "任せる範囲と止める範囲を線で書き出す。ノールックで✅を付けない"
     "（自己申告は🟡止まり・別AIが本番で見て初めて✅）。",
     "skills/tamago-unyou-os §7 ／ tools/kenpin_gate.py"),
    (("楽観ロック", "リスク", "許容", "be lazy", "無駄"),
     "迷ったら先に出す。戻せる作業は確認を取らずに進めて、戻せない4つだけ溜めて1日1回出す。",
     "skills/tamago-unyou-os §11 ／ tools/gate_meyasubako.py"),
    (("アクティブリコール", "記憶", "学習", "思い出"),
     "1日の終わりに、その日やったことを何も見ずに1行で書かせる。"
     "作業ログの機械記録とは別に、思い出して書いた方を残す。",
     "tools/nikki_generator.py"),
    (("新刊", "出版", "書籍", "本を出", "持たざる者"),
     "新刊が出たら、出た日に「うちに効く型」を抜き出す仕事を発車待ちへ積む。買うかはたまごさん。",
     "status/queue.json（この係が自動で積む）"),
    (("想像力", "センス", "こだわり", "テンプレート", "既知"),
     "AIが作ったままの型文を棚に出さない。人の手が入っていない文は落とす。",
     "skills/bonjovi-ojisan-kobun ／ tools/gaibu_kenpin.py"),
]


def log(msg):
    sys.stderr.write("[ushio] %s\n" % msg)


def host_allowed(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return bool(m) and m.group(1).lower() in ALLOWED_HOSTS


def fetch(url):
    if not host_allowed(url):
        raise ValueError("許可リストに無いURLなので見に行きません: %s" % url)
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html, */*"})
    raw = urlopen(req, timeout=TIMEOUT).read()
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&[a-z]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def cut(s, n=160):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


# ★門：この語が1つも無い記事には、どの打ち手も付けない。
#   2026-09-22 実測：ギターの記事・対談の記事に打ち手が付いた。普通の日本語の単語で
#   引っかかるのが原因なので、まず「うちの仕事の話かどうか」で丸ごと落とす。
DOMAIN_WORDS = (
    "エージェント", "agent", "ai", "llm", "コード", "code", "リポジトリ", "repo",
    "プルリク", "pull request", "エンジニア", "開発", "実装", "テスト", "デプロイ",
    "レビュー", "ソフトウェア", "プログラ", "アーキテクチャ", "スキル", "新刊", "出版",
)


def in_domain(text):
    t = (text or "").lower()
    return sum(1 for w in DOMAIN_WORDS if w.lower() in t) >= 2


def uchi_for(text, title=""):
    """「だからうちはこうする」を1つ返す。当たらなければ (None, None)。

    ★点数で決める。1語かすっただけで打ち手を付けない。
      2026-09-22 実測の失敗：素朴に「1語でも当たれば採用」にしたら、ギターの記事にも
      勝間和代さんとの対談にも「1号を小さく割る」が付いた（本文にたまたま「負担」や
      「レビュー」が混ざっていたため）。**打ち手が嘘になる＝拾わない方がまだよい。**
      → 題名に当たれば3点、本文に当たれば1点。合計2点未満は打ち手を付けずに held へ回す。
    """
    if not in_domain(text):
        return None, None
    t = (text or "").lower()
    ti = (title or "").lower()
    best = (0, None, None)
    for keys, uchi, where in UCHI_RULES:
        score = 0
        for k in keys:
            kl = k.lower()
            if kl in ti:
                score += 3
            elif kl in t:
                score += 1
        if score > best[0]:
            best = (score, uchi, where)
    # 3点＝題名に当たった（3点）か、本文に3語当たった。2点だと誤爆が残ることを実測した。
    if best[0] < 3:
        return None, None
    return best[1], best[2]


# ── 取得元 ──

def outbound_links(html):
    """本人が記事の中で外に張ったリンク＝「本人が紹介している実践」。題名は取らずURLだけ残す。"""
    hosts, out = set(), []
    for m in re.finditer(r'href="(https?://[^"]+)"', html or ""):
        u = m.group(1)
        h = re.sub(r"^https?://", "", u).split("/")[0].lower()
        if h.endswith("note.com") or "amazon" in h or "amzn" in h or h in hosts:
            continue
        hosts.add(h)
        out.append(u)
        if len(out) >= 4:
            break
    return out


def src_note_with_links():
    """noteの記事を取りつつ、本文HTMLから外部リンクも一緒に拾う（fetchを2回に留める）。"""
    out = []
    j = json.loads(fetch("https://note.com/api/v2/creators/%s/contents?kind=note&page=1" % NOTE_USER))
    for c in (j.get("data", {}).get("contents") or [])[:10]:
        key = c.get("key") or ""
        page = "https://note.com/%s/n/%s" % (NOTE_USER, key)
        title = strip_tags(c.get("name"))
        date = (c.get("publishAt") or "")[:10]
        raw = ""
        try:
            raw = json.loads(fetch("https://note.com/api/v3/notes/%s" % key)).get("data", {}).get("body") or ""
        except Exception:
            raw = ""
        body = strip_tags(raw)[:6000]
        uchi, where = uchi_for(title + " " + body, title)
        item = {"date": date, "source": "牛尾剛 note", "title": cut(title), "url": page,
                "uchi": uchi, "where": where}
        links = outbound_links(raw)
        if links:
            item["shoukai"] = links
        out.append(item)
    return out


def src_x():
    """認証なしで読める公開タイムラインだけ。取れなければ例外を上げて sourceErrors に残す
    （黙って0件にしない＝『動いているのに何も取れていない』を隠さない）。"""
    url = "https://syndication.twitter.com/srv/timeline-profile/screen-name/%s" % X_HANDLE
    html = fetch(url)
    out, seen = [], set()
    for m in re.finditer(r'"full_text":"(.*?)","', html):
        t = m.group(1).encode().decode("unicode_escape", "replace")
        t = strip_tags(t)
        if len(t) < 30 or t in seen:
            continue
        seen.add(t)
        uchi, where = uchi_for(t, t)
        if not uchi:
            continue
        out.append({"date": "", "source": "牛尾剛 X（@%s）" % X_HANDLE, "title": cut(t),
                    "url": "https://x.com/%s" % X_HANDLE, "uchi": uchi, "where": where})
        if len(out) >= 5:
            break
    if not out and '"full_text"' not in html:
        raise ValueError("公開タイムラインが読めませんでした（認証が要る形に変わった可能性）")
    return out


def src_books():
    """新刊・重版。著者ページの本の題名だけを拾う（本文は取らない）。"""
    # ★2026-09-22 実測：/search?author=... は本が1冊も取れなかった（実在しないURLだった）。
    #   本人の著者ページ（実在を確認済み）に差し替える。
    html = fetch("https://bunshun.jp/list/author/652fa155a53aef36a3000000")
    out, seen = [], set()
    for m in re.finditer(r'href="(https?://books\.bunshun\.jp/ud/book/num/(\d+))"[^>]*>(.*?)</a>', html, re.S):
        title = strip_tags(m.group(3))
        if len(title) < 4 or title in seen:
            continue
        seen.add(title)
        uchi, where = uchi_for(title + " 新刊", title + " 新刊")
        out.append({"date": "", "source": "文藝春秋BOOKS", "title": cut(title),
                    "url": m.group(1),
                    "uchi": uchi, "where": where})
        if len(out) >= 5:
            break
    if not out:
        raise ValueError("著者ページ(bunshun.jp/list/author/...)から本が1冊も取れませんでした"
                         "（ページの作りが変わった可能性）")
    return out


# ★文藝春秋BOOKSは外した（2026-09-22）。理由：著者ページの作りからは本の一覧が機械で読めず、
#   直しても0件のままだった。**永久に赤を出し続ける取得元を置いておくのは害**なので外す。
#   新刊は note の告知で実際に取れている（『持たざる者の戦略』を実測で拾えた）。
SOURCES = [("note", src_note_with_links), ("X", src_x)]


def collect():
    items, errors, per = [], [], {}
    for name, fn in SOURCES:
        try:
            got = fn() or []
            items.extend(got)
            # ★取得元ごとに「読めた件数」「打ち手が付いた件数」を残す。
            #   取得は出来たが1件も残らなかった取得元を、黙って0件にしないため。
            per[name] = {"読めた": len(got), "打ち手つき": len([g for g in got if g.get("uchi")])}
        except Exception as e:
            per[name] = {"読めた": 0, "打ち手つき": 0}
            errors.append({"source": name, "error": "%s: %s" % (type(e).__name__, e)})
    uniq, seen = [], set()
    for it in items:
        k = (it.get("title") or "")[:50]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return uniq, errors, per


def push_to_queue(held):
    """打ち手が付かなかったものを『打ち手を書く』仕事として発車待ちへ積む。
    人が押さなくても次が回る（github_watch.py と同じ形）。積めなくても他を止めない。"""
    if not held:
        return 0
    try:
        q = json.load(io.open(QUEUE, encoding="utf-8"))
        arr = q.get("items") or []
        exist = set((i.get("title") or "") for i in arr)
        n = max([i.get("n") for i in arr if isinstance(i.get("n"), int)] or [1000])
        added = 0
        # ★新しいものだけ積む（14日以内）。古い・関係の薄いものまで積むと発車待ちが荒れる。
        #   積まなかったものは消えるのではなく payload["held"] に残って進捗表から見える。
        limit = (datetime.now(JST) - timedelta(days=14)).strftime("%Y-%m-%d")
        fresh = [h for h in held if (h.get("date") or "") >= limit]
        for h in fresh[:2]:
            title = "牛尾さんの新しい発信に『うちはこうする』を書く：%s" % cut(h.get("title"), 40)
            if title in exist:
                continue
            n += 1
            arr.append({
                "n": n, "title": title,
                "why": "拾えたが打ち手が付いていない。拾って終わりにしない（1019番の約束）",
                "what": "出典：%s\nこの発信を読んで、うちのどのファイル／どの手順をどう変えるかを1つだけ書く。"
                        "書けたら status/public/ushio_watch.json の items に移す。" % h.get("url"),
                "status": "🔴", "origin": "factory",
                "addedAt": datetime.now(JST).isoformat(),
            })
            added += 1
        if added:
            q["items"] = arr
            io.open(QUEUE, "w", encoding="utf-8").write(
                json.dumps(q, ensure_ascii=False, indent=1) + "\n")
        return added
    except Exception as e:
        log("発車待ちへ積めませんでした（他は止めません）: %s" % e)
        return 0


def load_out():
    try:
        return json.load(io.open(OUT, encoding="utf-8")) or {}
    except Exception:
        return {}


def already_ran_today(today):
    try:
        return io.open(MARKER, encoding="utf-8").read().strip() == today
    except Exception:
        return False


def selftest():
    """外に出ずに配線だけ確かめる。打ち手の対応表が本当に効くかを見る。

    ★本物と同じ形（題名・本文の2つ）で試す。実際に出た事故をそのまま検体にしてある：
      ギターの記事・対談の記事は、本文にたまたま「負担」等が混ざっているだけなので
      打ち手を付けてはいけない（＝拾わない方がまだよい）。
    """
    ok = True
    cases = [
        # (題名, 本文, 打ち手が付くべきか)
        ("最近の人間ボトルネック問題解決の工夫",
         "レビューする人間の負担がクリティカルパスになる。プルリクエストを小さくする。", True),
        ("ハーネスエンジニアリングのノウハウ",
         "制約をつける方がエージェントはうまく動く。やってはいけないことを決める。", True),
        ("コンテキスト・マネジメントの真髄",
         "エージェントへの指示は端的に。余分な情報を与えない。"
         "コードを書かせるときもローカル参照の方が正確に扱われる。", True),
        ("新刊『持たざる者の戦略』を出します", "朝日新聞出版から出版していただけることになった。", True),
        ("ギターを自由に弾ける方法",
         "練習の負担を減らして、気分に合わせてJAMする。", False),
        ("人生の運を半分使って対談できた話", "とても楽しい時間だった。", False),
        ("今日は天気がよかった", "散歩に行った。", False),
        # ★2026-09-22 実測でここに打ち手が付いてしまった2件。二度と付かないことを毎回試す。
        ("あの人は全然練習してないのに何であんなに上手いんだろうの謎が解けた話",
         "ギター演奏の思考回路は180度変わった。なぜ上手くなったのか、その理由を分析する。", False),
        ("人生の運を半分使って、勝間和代さんと対談できた話",
         "なぜこうなったのか、思考の履歴を思い出すと不思議な縁だった。", False),
    ]
    for title, body, want in cases:
        got = uchi_for(title + " " + body, title)[0] is not None
        mark = "OK" if got == want else "NG"
        if got != want:
            ok = False
        print("%s: 「%s」→ 打ち手%s" % (mark, title[:30], "あり" if got else "なし"))
    print("対応表 %d本 ／ 許可ホスト %d件" % (len(UCHI_RULES), len(ALLOWED_HOSTS)))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    force = "--now" in argv
    dry = "--dry-run" in argv

    if not force and not dry and already_ran_today(today):
        return 0

    items, errors, per = collect()
    picked = [i for i in items if i.get("uchi")]
    held = [i for i in items if not i.get("uchi")]

    if dry:
        print(json.dumps({"picked": picked, "held": held, "sourceErrors": errors},
                         ensure_ascii=False, indent=2))
        return 0

    prev = load_out()
    runs = int(prev.get("runs") or 0) + 1
    old = prev.get("items") or []
    seen = set((x.get("title") or "")[:50] for x in picked)
    merged = picked + [x for x in old if (x.get("title") or "")[:50] not in seen]

    queued = push_to_queue(held)

    payload = {
        "updatedAt": now.isoformat(),
        "note": "牛尾剛さんの発信を1日1回拾って「だからうちはこうする」を付けた一覧"
                "（tools/ushio_watch.py・心臓に相乗り・定期タスクは使っていない）",
        "runs": runs,
        "pickedThisRun": len(picked),
        "pickedTotal": len(merged),
        "heldThisRun": len(held),
        "queuedThisRun": queued,
        # ★走った>0 なのに 拾えた=0 は赤。動いているのに何も取れていない状態を隠さない。
        "red": bool(runs > 0 and len(merged) == 0),
        "items": merged[:KEEP],
        "held": held[:10],
        "sourceErrors": errors,
        "perSource": per,
    }
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        io.open(OUT, "w", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        io.open(MARKER, "w", encoding="utf-8").write(today)
    except Exception as e:
        log("書き込み失敗: %s" % e)
        return 1
    log("走行%d回目 ／ 拾えた%d件（今回%d件・打ち手待ち%d件・発車待ちへ%d件・取得失敗%d件）%s"
        % (runs, len(merged), len(picked), len(held), queued, len(errors),
           "  ★赤（拾えた0件）" if payload["red"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
