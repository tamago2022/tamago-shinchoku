#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWAの「リモコン」ボタンから来たコマンドを実行する（2026-09-03）。

流れ:
  PWA（スマホ）でボタンをタップ → obsidian://new が Vault に
  `AI出力/_ルール/コマンド_受信/<id>.md`（JSON）を作る → iCloudでMacに届く
  → このスクリプト（30秒おきのlaunchdから呼ばれる）が未処理の受信ファイルを読んで実行
     → status/commands.json に結果を追記してpush（PWAが読んで「実行しました」を表示）

対応アクション:
  resume    : 止まっているセッションを claude -p --resume で再開
  stop      : 指定pidを終了（Claudeプロセスであることを確認してから。SIGTERM）
  handoff   : 詰まっているセッションに簡易引き継ぎメッセージ付きの新セッションを立てる
  close_app : 重いアプリを終了（除外リスト＝Brave・Chromeは絶対に実行しない。未保存書類は失敗扱い）
  queue_ok    : 進捗表「たまごさんの確認待ち」で✅OKを押した番号を status/queue.json で done にする
  queue_redo  : 同じくやり直しを押した番号を waiting に戻し、items配列の先頭へ移動する（次に発車の一番手にする）
  queue_add   : 進捗表の入力欄に書いた1行（+優先度1-5）を status/queue.json の末尾へ waiting として新規追加する
                （2026-09-04追加。スマホから直接発車待ちへ積めるようにした。これまでDispatch経由でしか積めなかった）

  2026-09-04 queue_ok/queue_redo 追加：進捗表の確認ボタンは、これまで押した結果が端末内
  （localStorage）にしか残らず、Mac側の status/queue.json には一切反映されていなかった
  （index.html側コメントに「Obsidian経由でMac側へ渡す」と書かれていたが実装が無かった）。
  優先度（priority_ingest.py）・リモコン（resume/stop/handoff/close_app）と同じ
  「obsidian://new → Vault → このingest → status/queue.json」の道に乗せて実装した。

受信ファイルは消さない（記録として残す）。commands.jsonに書いたidは二重実行しない。
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
INBOX_DIR = os.path.join(VAULT, "AI出力", "_ルール", "コマンド_受信")
OUT = os.path.join(REPO, "status", "commands.json")
QUEUE = os.path.join(REPO, "status", "queue.json")
CLAUDE = os.environ.get("CLAUDE_BIN") or (os.path.expanduser("~/.local/bin/claude")
        if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")

# 2026-09-03 たまごさん指定：絶対に閉じない（Chromeを含めるのは『Happy Place Station | Lovable』の
# ウィンドウを巻き込まないため。プロセス単位のquitではウィンドウ単位の除外ができないので全体を除外する）
EXCLUDED_APPS = {"Brave Browser", "Google Chrome"}



# ---- 認証トークン（2026-09-05）----
# `claude setup-token` はキーチェーンに保存せず画面に出すだけなので、
# こちらで ~/.tamago/claude_token（600・git管理外）に置き、起動時に環境変数で渡す。
def claude_env():
    """CLIに渡す環境。**環境変数のトークンは原則使わない**（2026-09-05に実測）。

    `CLAUDE_CODE_OAUTH_TOKEN` を渡すと、キーチェーンに入っている**正しい鍵より優先される。**
    9/05は `/login` が成功して「Logged in as eggypop2010@gmail.com」と出ているのに、
    ここで古い壊れたトークン（79文字）を被せていたせいで「OAuth session expired」が続いた。
    キーチェーンを正本にする。環境変数を使いたいときだけ ~/.tamago/use_token を置く。
    """
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    if not os.path.exists(os.path.expanduser("~/.tamago/use_token")):
        return env
    p = os.path.expanduser("~/.tamago/claude_token")
    try:
        t = io.open(p, encoding="utf-8").read().strip()
        if t:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = t
    except Exception:
        pass
    return env


def run(cmd, timeout=10, env=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except Exception:
        return None


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def close_app(app):
    if not app:
        return "failed", "対象アプリ名が無い"
    if app in EXCLUDED_APPS:
        return "skipped", "%s は除外対象のため実行しません" % app
    check = run(["pgrep", "-f", app])
    if not check or not check.stdout.strip():
        return "skipped", "%s は起動していません" % app
    r = run(["osascript", "-e", 'tell application "%s" to quit' % app.replace('"', '\\"')], timeout=8)
    if r is None:
        return "failed", "タイムアウト（保存待ちの可能性）"
    time.sleep(2)
    check2 = run(["pgrep", "-f", app])
    if check2 and check2.stdout.strip():
        return "failed", "保存待ちで閉じられませんでした（未保存の書類がある可能性）"
    return "done", "%s を閉じました" % app


def resume(cli):
    if not cli:
        return "failed", "対象セッションIDが無い"
    log = os.path.join(REPO, "status", "cmd-resume-%s.log" % cli[:8])
    cmd = [CLAUDE, "-p", "--resume", cli, "--permission-mode", "auto", "--output-format", "json",
           "【PWAリモコン】たまごさんがスマホから再開を指示。止まっていた続きを最後までやって。"]
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s resume ===\n" % time.strftime("%Y-%m-%d %H:%M:%S")).encode())
            subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdout=f, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True, env=claude_env())
        return "done", "再開コマンドを送りました"
    except Exception as e:
        return "failed", str(e)


def stop(pid):
    try:
        pid = int(pid)
    except Exception:
        return "failed", "pidが不正"
    check = run(["ps", "-p", str(pid), "-o", "command="])
    if not check or not (check.stdout or "").strip():
        return "skipped", "既に終了しています"
    if "claude" not in check.stdout.lower():
        return "failed", "Claudeのプロセスではないため安全のため止めません"
    try:
        os.kill(pid, 15)  # SIGTERM。強制終了(-9)はしない
        return "done", "止めました"
    except Exception as e:
        return "failed", str(e)


def handoff(cli):
    if not cli:
        return "failed", "対象セッションIDが無い"
    new_id = str(uuid.uuid4())
    log = os.path.join(REPO, "status", "cmd-handoff-%s.log" % new_id[:8])
    prompt = ("【PWAリモコン・引き継ぎ】たまごさんがスマホから引き継ぎを指示。前のセッション（%s）が詰まっている。"
              "止まらない工場のホワイトボード（python3 /Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py next）"
              "を見て、担当を引き取り、続きを進めて。tamago-unyou-osスキルの前提に従うこと。" % cli[:8])
    cmd = [CLAUDE, "-p", "--session-id", new_id, "--permission-mode", "auto", "--output-format", "json", prompt]
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s handoff from %s ===\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), cli[:8])).encode())
            subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdout=f, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True, env=claude_env())
        return "done", "新セッション %s を起動しました" % new_id[:8]
    except Exception as e:
        return "failed", str(e)


# ---- 台帳の鍵（2026-09-05）----
# たまごさん「完了に入ったものもあれば、反応しないものもあります」の原因。
# 押したボタンの処理と、心臓（着火・回収）が同時に台帳を読み書きしていたため、
# 片方が古い内容で上書きして押した結果が消えていた（lost update）。
# 読む→書くの間ずっと鍵をかける（auto_launcher.py と同じ鍵ファイル）。
import fcntl
from contextlib import contextmanager

QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")


@contextmanager
def queue_lock(timeout=10.0):
    f = open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def _load_queue():
    return load_json(QUEUE, {"items": []})


def _save_queue(q):
    save_json(QUEUE, q)


def _find_item(items, n):
    for it in items:
        if it.get("n") == n:
            return it
    return None


# ---- 2026-09-06 421番：積む前に重複を照合 ----
# 心臓の多重起動で同じ指示が10個・15個と積み上がる事故が繰り返し起きた（queue_dedupe参照）。
# あれは「増えてしまった後」の掃除。ここでは「積む前」に止める。
DUP_STATUSES = ("waiting", "running", "hold")


def _titles_conflict(a, b):
    """題名の重複判定：完全一致／どちらかがもう片方を含む／先頭30文字が同じ。"""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    if len(a) >= 30 and len(b) >= 30 and a[:30] == b[:30]:
        return True
    return False


def _find_duplicate_title(items, title):
    for it in items:
        if it.get("status") not in DUP_STATUSES:
            continue
        if _titles_conflict(title, str(it.get("title") or "")):
            return it
    return None


# ---- 2026-09-06 423番：大きすぎる仕事を自動で小さく切る ----
# たまごさん「『サイト全体の◯◯を直す』のような仕事が1本で積まれ、3時間で切られて
# 中途半端に終わっている」。発車の直前（＝発車待ちに積む時点）で指示文を見て、
# 『全ページ』『全件』『すべての』『◯◯件』のような言葉があれば大きい仕事だと判定する。
BIG_JOB_KEYWORDS = ("全ページ", "全件", "すべての", "全部の", "全アーティスト", "全曲", "全記事")
BIG_JOB_COUNT_RE = re.compile(r"(\d{2,})\s*件")  # 二桁以上の「N件」（10件〜）


def _is_big_job(text):
    """大きすぎる仕事かどうかの機械判定。誤判定を恐れず広めに拾う
    （広めに拾っても『まず一覧だけ作る』に落ちるだけで実害が小さいため）。"""
    t = text or ""
    for kw in BIG_JOB_KEYWORDS:
        if kw in t:
            return True
    m = BIG_JOB_COUNT_RE.search(t)
    if m:
        try:
            if int(m.group(1)) >= 10:
                return True
        except Exception:
            pass
    return False


def _build_list_phase_what(n, title, text):
    """大きい仕事の1本目＝『対象の一覧を作るだけ』の指示文を組み立てる。"""
    return (
        "この依頼は「全ページ」「全件」「すべての」「◯◯件」のような言葉を含んでいたため、"
        "**大きすぎる仕事**だと機械が判定しました（423番の仕組み）。\n"
        "1本で3時間かけてやろうとすると、途中で切られて成果がゼロになる実害が繰り返し出ているため、"
        "**今回はまだ本体の作業をしないでください。**\n\n"
        "# 元の依頼\n---\n%s\n---\n\n"
        "# 今回やること（これだけ）\n"
        "1. 上の依頼の対象になる項目（ページ・アーティスト・曲など、1件＝あとで1本の小さい仕事に"
        "分割できる単位）を実際に調べて洗い出してください。\n"
        "2. 洗い出した一覧を、次の場所にJSONで**必ず**保存してください"
        "（このファイルが無い・空だと自動分割ができず、この仕事はやり直しになります）：\n"
        "   `status/split/%d-list.json`\n"
        "   形式：`{\"items\": [\"対象1の短い説明\", \"対象2の短い説明\", ...]}`\n"
        "   （例：ページのURLやスラッグ、アーティスト名など、次の担当がそれだけ読めば"
        "何をすればいいか分かる短い一文にすること）\n"
        "3. 確認ページ（`python3 tools/make_check_page.py`）に、見つけた**件数**と一覧の**代表例**"
        "（全部は貼らなくてよい）をまとめて報告してください。\n"
        "4. 一覧ファイルさえ保存できていれば、あとは工場が自動で**10件ずつ**の小分けタスクに割って"
        "発車待ちへ積みます。あなたはこの一覧作成が終わった時点で完了です。\n\n"
        "# 禁止\n"
        "- この回で対象の中身（ページ内容の修正など）まで手を出さない（次の10件ずつの回でやります）\n"
        "- 「多すぎるので無理」と諦めない。調べられる範囲で実際に洗い出す\n"
    ) % (text, n)


def queue_add(text, priority=None, label=None, origin=None):
    """進捗表の「＋発車待ちに追加」→ status/queue.json の末尾（n=最大+1）へ
    waiting状態の新規項目を追加する。2026-09-04：いままでDispatch経由でしか積めなかった
    発車待ちの列に、スマホから直接1行で積めるようにした。

    優先度（1=今すぐ…5=後回し）はitem自身の"priority"フィールドに書く。
    auto_launcher.pyのrank()はこのフィールドを最優先で見る（priority.jsonのQキー方式より単純で確実）。

    2026-09-06(453/455番) たまごさん「工場が自分で作って、自分で終わらせて、確認を求めているものが
    大量にある」→ 各タスクに「たまごさん発／工場発」の印(origin)を持たせ、確認列の表示判定に使う。
    進捗表(スマホ)・Dispatchからの通常追加＝たまごさんの言葉で入るものなので既定は"user"。
    見張り番・棚卸し等がAI自身の判断で積む時だけ、呼び出し側が明示的に origin="factory" を渡す。"""
    text = (text or "").strip()
    if not text:
        return "failed", "本文が空です"
    # ---- 2026-09-06 01:10 **ここに2つの重大なバグがあった。**----
    # ① `text[:400]` で指示文を400文字に切っていた。Dispatchが書いた長い指示（守るべき条件・
    #    禁止事項・出力先・上限額）が**途中で消え、子セッションは不完全な指示で走っていた。**
    #    実測：#404・#412〜418 の8本が全部きっかり400文字で切れていた。
    # ② 題名を `text[:120]`（指示文の先頭120文字）にしていた。だから進捗表に指示文が
    #    そのまま題名として並び、たまごさんに「6番以降が変」と言われた。
    # → 制限を外し、**題名は label（短い名前）を優先**して使う。
    label = (label or "").strip()
    # 2026-09-06 421番：本当に別物のときの逃げ道。label に「重複OK」と書いてあれば
    # 重複照合をスキップして通す（マーカー自体は題名から取り除く）。
    force_dup = "重複OK" in label
    if force_dup:
        label = re.sub(r"重複OK", "", label).strip(" 　・:：,、")
    title = label
    if not title:
        # labelが無いときだけ、本文の1行目から短く作る（記号は落とす）
        first = re.sub(r"[*#`>]", "", text.splitlines()[0] if text.splitlines() else text)
        first = re.sub(r"^【[^】]*】", "", first).strip()
        title = first[:60]
    title = re.sub(r"[*#`]", "", title)[:80]
    try:
        p = int(priority)
    except Exception:
        p = None
    if p is not None and (p < 1 or p > 5):
        p = None
    q = _load_queue()
    items = q.get("items") or []
    # 2026-09-06 421番：積む前に重複を照合する。完全一致／片方がもう片方を含む／
    # 先頭30文字が同じ、のいずれかなら「重複OK」指定が無い限り積まずに返す。
    if not force_dup:
        dup = _find_duplicate_title(items, title)
        if dup is not None:
            return "skipped", "%d番と同じ内容です（積みませんでした。別物なら label に『重複OK』と書いて送ってください）" % dup.get("n")
    next_n = (max([int(it.get("n") or 0) for it in items], default=0)) + 1
    # 2026-09-06 423番：大きすぎる仕事は、本体を積む代わりに「一覧作成だけ」の1本目を積む。
    # 一覧ができたら auto_launcher.py の harvest() が自動で10件ずつの発車待ちへ割る。
    big_job = _is_big_job(text)
    item = {
        "n": next_n,
        "title": ("【一覧作成】%s" % title) if big_job else title,
        "why": "スマホから追加",
        "what": _build_list_phase_what(next_n, title, text) if big_job else text,
        "status": "waiting",
        "limitMin": 180,
        "model": "claude-sonnet-5",
        "origin": origin if origin in ("user", "factory") else "user",
    }
    if big_job:
        item["bigJob"] = True
        item["phase"] = "list"
        item["originalTitle"] = title
        item["originalWhat"] = text
    if p is not None:
        item["priority"] = p
    items.append(item)
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    if big_job:
        return "done", ("%d番：大きい仕事と判定したので、まず一覧作成だけを発車待ちに追加しました"
                         "（P%s）。一覧ができたら自動で10件ずつに割ります" % (next_n, p if p else "-"))
    return "done", "%d番として発車待ちに追加しました（P%s）" % (next_n, p if p else "-")


def _split_targets(target):
    """"12" でも "12,15,18" でも受ける共通の分解処理。
    2026-09-06(459番) 「まとめてOK」でチェックした複数件を1回の通信で流すために追加。
    重複・空要素・数字でないものは無視する。"""
    nums = []
    for part in str(target).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = int(part)
        except Exception:
            continue
        if v not in nums:
            nums.append(v)
    return nums


def queue_ok(target):
    """進捗表「✅OK・完了にする」→ status/queue.json の該当番号を done にする。
    2026-09-06(459番) 「まとめてOK」対応：target は "12" 単体でも "12,15,18" のカンマ区切りでもよい。
    1件ずつ82回通信させない、が今回の趣旨（1回の呼び出しでqueue.jsonを1回だけ保存する）。"""
    ns = _split_targets(target)
    if not ns:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    done, skipped, missing = [], [], []
    for n in ns:
        it = _find_item(items, n)
        if it is None:
            missing.append(n)
            continue
        if it.get("status") == "done":
            skipped.append(n)
            continue
        it["status"] = "done"
        it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        done.append(n)
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    if len(ns) == 1:
        if done:
            return "done", "%d番を完了にしました" % done[0]
        if skipped:
            return "skipped", "%d番はすでに完了です" % skipped[0]
        return "failed", "%d番がqueue.jsonに見つかりません" % ns[0]
    msg = "%d件をまとめて完了にしました（%s）" % (len(done), ",".join(str(x) for x in done)) if done else "完了できたものはありません"
    if skipped:
        msg += "・すでに完了%d件" % len(skipped)
    if missing:
        msg += "・見つからず%d件（%s）" % (len(missing), ",".join(str(x) for x in missing))
    return ("done" if done else "failed"), msg


def queue_undo_ok(target):
    """「まとめてOK」直後の取り消し（10秒以内）。done→awaiting_checkへ戻す。
    2026-09-06(459番) 「押した瞬間に画面から消す→直後に『取り消す』を10秒だけ出す」の受け皿。
    checkedAtを外すだけで、result/urls等の中身は消さない（元の確認待ちにそのまま戻る）。"""
    ns = _split_targets(target)
    if not ns:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    restored = []
    for n in ns:
        it = _find_item(items, n)
        if it is None or it.get("status") != "done":
            continue
        it["status"] = "awaiting_check"
        it.pop("checkedAt", None)
        restored.append(n)
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    if not restored:
        return "skipped", "取り消せる項目がありませんでした（%r）" % target
    return "done", "%d件を確認待ちに戻しました（%s）" % (len(restored), ",".join(str(x) for x in restored))


def queue_redo(target):
    """進捗表「↩︎やり直し」→ status/queue.json の該当番号を waiting に戻し、
    items配列の先頭へ移す（＝次に発車の一番手。auto_launcher.pyが次サイクルで拾う）。
    走行の残骸（sessionId/pid/startedAt/finishedAt/result/urls）は消し、新規のwaiting項目と同じ形に戻す。"""
    # 2026-09-04 たまごさん「やり直しも、今すぐやり直せないのか、急ぎのやつもある。
    #   順番待ちの後に並んでいいよ、っていうのもある」
    #   → target は "12"（今まで通り＝先頭）か "12:5"（優先度つき）で受ける。
    #     優先度が付いていれば、先頭へ割り込ませず item.priority に書いて列の順番に任せる。
    prio = None
    if ":" in str(target):
        target, _p = str(target).split(":", 1)
        try:
            prio = int(_p)
        except Exception:
            prio = None
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    idx = None
    for i, it in enumerate(items):
        if it.get("n") == n:
            idx = i
            break
    if idx is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    it = items.pop(idx)
    it["status"] = "waiting"
    it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for k in ("finishedAt", "result", "urls", "sessionId", "pid", "startedAt"):
        it.pop(k, None)
    if prio:
        it["priority"] = prio
        items.append(it)          # 順番待ちの後ろへ。優先度で拾われる
        where = "P%d で列に戻しました（急がない）" % prio
    else:
        it.pop("priority", None)
        it["priority"] = 1
        items.insert(0, it)       # 今すぐ＝先頭へ割り込ませる
        where = "列の先頭（次に発車）へ戻しました"
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を%s" % (n, where)


def queue_later(target):
    """「🟡 とりあえずOK（あとで直す）」を押したとき。

    2026-09-04 たまごさんの言葉：「70点だけど、今急ぎじゃないからいいや、っていうのもあるわけよ。
    完全には治ってないけど、まあここまでだったらとりあえずいいや、という状態がある。
    完全にオッケーじゃないんだけどね。とりあえずオッケー、だけど時間あるとき直そうね、っていうこと。
    結構俺の中では優先順位中ぐらいなのに、70点を85点に持っていくのに時間はかけたくない。」

    → **いったん完了として片づける**（確認待ちの列から外す）。
      そのうえで「あとで直す」1件を **P5（後回し）** で発車待ちの末尾に積む。
      列が空いてきたときに勝手に拾われるので、たまごさんは何もしなくてよい。
    """
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    src = None
    for it in items:
        if it.get("n") == n:
            src = it
            break
    if src is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    # 2026-09-04 たまごさん「とりあえず後回しでOKを押すと、後回しボックスに入れて欲しいのに、
    #   **押してるのに次から次へと出てくる。1回だから後回しでOKって言ったんだ。そこから消えて欲しい。**」
    #   → 「あとで直す」を新しい依頼として積み直すのをやめた（それが増え続ける原因だった）。
    #     status を later（後回しボックス）にするだけ。確認待ちからは即座に消え、発車もしない。
    #     時間ができたら「後回しを回して」の一言で waiting に戻す。
    src["status"] = "later"
    src["laterAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    src["checkedAt"] = src["laterAt"]
    src["checkNote"] = "たまごさん判定：とりあえずOK（70点。時間があるとき直す）"
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を後回しボックスへ入れました（確認待ちからは消えます）" % n


def queue_prio(target):
    """進捗表「🚏次に発車」の行のPボタン → その番号の優先度を queue.json に書き込む。

    2026-09-04 たまごさん「そこにも俺、優先順位つけるよ」。
    これまでPボタンは端末の中（localStorage）にしか残らず、**Mac側の発車順には
    一切効いていなかった**。押した意味が無い状態だったので、他のボタンと同じ
    obsidian経由の指示に乗せ、queue.json の item.priority を直接書き換える。
    target は "37:1"（番号:優先度）。優先度0は「Pを外す」。
    """
    try:
        s = str(target)
        n_s, p_s = s.split(":", 1)
        n, p = int(n_s), int(p_s)
    except Exception:
        return "failed", "指定が不正: %r（番号:優先度 の形で渡す）" % target
    q = _load_queue()
    for it in q.get("items") or []:
        if it.get("n") == n:
            if p:
                it["priority"] = p
            else:
                it.pop("priority", None)
            q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
            _save_queue(q)
            return "done", "%d番の優先度を%sにしました" % (n, ("P%d" % p) if p else "なし")
    return "failed", "%d番がqueue.jsonに見つかりません" % n


def _repo_status(name):
    return os.path.join(REPO, "status", name)


def launch_switch(on):
    """発車のもと栓。2026-09-04 たまごさん「ガソリンが切れる。家にたどり着かなきゃいけないのに寄り道してる」

    止めているあいだも、終わったものの回収・判定・繰り上げの順番は動く。燃料だけ使わない。
    """
    flag = _repo_status("no_launch.flag")
    if on:
        try:
            os.remove(flag)
        except Exception:
            pass
        return "done", "発車を再開しました"
    with io.open(flag, "w", encoding="utf-8") as f:
        f.write("たまごさんが進捗表から止めました %s\n" % time.strftime("%Y-%m-%d %H:%M"))
    return "done", "発車を止めました（走っているものはそのまま）"


def launch_cap(target):
    """同時に走らせる本数の上限。少ないクレジットを何本に配るかをたまごさんが決める。"""
    try:
        n = int(target)
    except Exception:
        return "failed", "本数が不正: %r" % target
    n = max(0, min(6, n))
    with io.open(_repo_status("launch_cap.json"), "w", encoding="utf-8") as f:
        json.dump({"cap": n, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, f, ensure_ascii=False, indent=1)
    return "done", "同時に走る本数を%d本にしました" % n


def process(cmd):
    action = cmd.get("action")
    if action in ("queue_ok", "queue_undo_ok", "queue_redo", "queue_add", "queue_prio", "queue_later",
                  "queue_pause", "queue_delete", "queue_order", "queue_dedupe"):
        with queue_lock():
            return _process_queue(action, cmd)

    target = cmd.get("target")
    if action == "close_app":
        return close_app(target)
    if action == "resume":
        return resume(target)
    if action == "stop":
        return stop(target)
    if action == "handoff":
        return handoff(target)
    return _process_other(action, cmd)


def _process_queue(action, cmd):
    target = cmd.get("target")
    if action == "queue_ok":
        return queue_ok(target)
    if action == "queue_undo_ok":
        return queue_undo_ok(target)
    if action == "queue_redo":
        return queue_redo(target)
    if action == "queue_add":
        return queue_add(target, cmd.get("priority"), cmd.get("label"), cmd.get("origin"))
    if action == "queue_prio":
        return queue_prio(target)
    if action == "queue_later":
        return queue_later(target)
    if action == "queue_pause":
        return queue_pause(target)
    if action == "queue_order":
        return queue_order(target)
    if action == "queue_dedupe":
        return queue_dedupe(target)
    if action == "queue_delete":
        return queue_delete(target)
    return "failed", "不明なアクション: %s" % action


def git_unlock(_target=None):
    """置き去りのgitロックを消す（このリポジトリの .git 直下のみ）。

    2026-09-05：Cowork側のサンドボックスから `git add` を叩くと、マウント越しでは
    `.git/index.lock` を消せず（Operation not permitted）残ってしまい、
    以後ホスト側の commit/push が全部止まる＝**進捗表が更新されなくなる**。
    ホスト側で動くこのプロセスなら消せるので、専用の指示を用意した。
    消すのは「このリポジトリの .git 直下の *.lock と objects の一時ファイル」だけ。
    """
    import glob as _glob
    removed = []
    for pat in (os.path.join(REPO, ".git", "*.lock"),
                os.path.join(REPO, ".git", "refs", "**", "*.lock"),
                os.path.join(REPO, ".git", "objects", "*", "tmp_obj_*")):
        for f in _glob.glob(pat, recursive=True):
            try:
                os.remove(f)
                removed.append(os.path.relpath(f, REPO))
            except Exception:
                pass
    return "done", ("消しました: %s" % ", ".join(removed[:6])) if removed else ("skipped", "ロックはありませんでした")[1] if False else ("消しました: %s" % ", ".join(removed[:6]) if removed else "ロックはありませんでした")


def push_unlock(_target=None):
    """5分おきの巡回が止まったときに、置き去りのロックを外す。

    2026-09-05：巡回(machine_status_push.sh)は二重起動を防ぐためロックを置くが、
    途中で死ぬとロックが残り、以後の巡回が全部 exit 0 で素通りして
    **計測もpushも止まる**（実測：02:42で止まり、進捗表が更新されなくなった）。
    中のpidが生きていなければ外す。生きているなら触らない。
    """
    lock = os.path.join(REPO, "status", ".machine_status_push.lock")
    if not os.path.exists(lock):
        return "skipped", "ロックはありません"
    try:
        pid = int(open(lock).read().strip())
    except Exception:
        pid = None
    if pid:
        try:
            os.kill(pid, 0)
            return "skipped", "巡回はまだ動いています（pid %d）" % pid
        except Exception:
            pass
    try:
        os.remove(lock)
        return "done", "止まった巡回のロックを外しました（pid %s は生きていません）" % pid
    except Exception as e:
        return "failed", str(e)


def queue_dedupe(_target=None):
    """同じ題名の仕事が何個も並んでいたら、1つだけ残して片づける（2026-09-05）。

    たまごさん「同じものが2つ同時に作業してるよね。これも変だよね」
    原因は心臓が何本も走っていたこと（受信箱が何度も読まれ、同じ指示が何回も実行された）。
    心臓は1本に直したが、**既に増えてしまった分**をここで掃除する。
    走行中のものを最優先で残し、次に番号が小さいものを残す。残りは deleted.json へ控えて消す。
    """
    q = _load_queue()
    items = q.get("items") or []
    box = os.path.join(REPO, "status", "deleted.json")
    d = load_json(box, {"items": []})
    groups = {}
    for it in items:
        if it.get("status") not in ("waiting", "running", "hold"):
            continue
        key = (str(it.get("title") or "")[:60], it.get("status") == "hold")
        groups.setdefault(key[0], []).append(it)
    drop = []
    for key, xs in groups.items():
        if len(xs) < 2:
            continue
        xs.sort(key=lambda x: (x.get("status") != "running", int(x.get("n") or 0)))
        for it in xs[1:]:
            it["deletedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            it["deletedWhy"] = "重複（心臓が多重起動していた時に増えたもの）"
            d.setdefault("items", []).append(it)
            drop.append(it.get("n"))
    if not drop:
        return "done", "重複はありませんでした"
    d["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    save_json(box, d)
    q["items"] = [x for x in items if x.get("n") not in drop]
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "重複%d件を片づけました（deleted.jsonに控えてあります）" % len(drop)


def queue_order(target):
    """手で並べ替えた順番を台帳に焼き込む（2026-09-05）。

    たまごさんの言葉：
      「**ドラッグアンドドロップで、順番入れ替えられるようにしたい、上下。
        今さ、押したら1個下に下がる、みたいなやつでしょ。すごいやりづらいです。**」

    target は "37,113,313,314" のように**並べ替えた後の番号を先頭から並べた文字列**。
    その順に order を 1,2,3… と振る。発車係(auto_launcher.rank)は
    優先度 → order → 番号 の順で見るので、同じ箱の中の並びがそのまま発車順になる。
    画面に出ていない番号には触らない（部分的な並べ替えでも壊れない）。
    """
    try:
        ns = [int(x) for x in str(target).replace(" ", "").split(",") if x != ""]
    except Exception:
        return "failed", "並び順が読めません: %r" % target
    if not ns:
        return "failed", "並び順が空です"
    q = _load_queue()
    items = q.get("items") or []
    hit = 0
    for i, n in enumerate(ns, start=1):
        it = _find_item(items, n)
        if it is not None:
            it["order"] = i
            hit += 1
    if not hit:
        return "failed", "その番号は台帳にありません"
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d件の並び順を保存しました（この順に発車します）" % hit


def queue_pause(target):
    """走行中の仕事を安全に引っ込めて、続きから再開できる形で列に戻す。

    2026-09-05 たまごさん：
      「**今あなたこれ1回引っ込めて**、みたいな。作業の途中で引っ込めるとどういうエラーが出ちゃうのか
       分かんないけど、**それも安全に止められるように、続きから再開できるように。**
       途中で止めても。**割り込みもあり。緊急で入るから。**」

    やること：SIGTERM（強制終了ではない）で止める → status を waiting に戻す →
    `resumeFrom` にセッションIDを残す。次に発車するとき auto_launcher が
    `claude -p --resume <id>` で**前回の続きから**起こす。最初からやり直しにはならない。
    """
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    it = _find_item(q.get("items") or [], n)
    if it is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    if it.get("status") != "running":
        return "skipped", "%d番は走っていません（今は%s）" % (n, it.get("status"))
    pid = it.get("pid")
    killed = False
    if pid:
        try:
            os.kill(int(pid), 15)      # SIGTERM。-9は使わない（途中成果を書き切らせる）
            killed = True
        except Exception:
            pass
    it["status"] = "waiting"
    it["pausedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if it.get("sessionId"):
        it["resumeFrom"] = it["sessionId"]     # 続きから再開するための目印
    it.pop("pid", None)
    it["priority"] = it.get("priority") or 3
    # 2026-09-05 たまごさん「引っ込めたやつはちょっと列の後ろに行って。最後尾に」
    #   引っ込めた直後にまた先頭へ戻ってくると、割り込ませたくて引っ込めた意味が無い。
    #   同じ優先度の中で一番後ろになるよう order を大きく振る。
    orders = [int(x.get("order")) for x in (q.get("items") or [])
              if isinstance(x.get("order"), int)]
    it["order"] = (max(orders) if orders else 0) + 1000
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を引っ込めて列の最後尾へ回しました（%s。次に発車するとき続きから再開します）" % (
        n, "止めました" if killed else "すでに終わっていました")


def queue_delete(target):
    """タスクそのものを台帳から消す。

    2026-09-05 たまごさん：
      「**タスク自体削除っていう削除にして、その4つにして。**完了と、とりあえずOK（あとで直す）と、
       やり直しますと、あとタスク削除。この4つにして。」

    完了（成果として積む）とは別物。**もう要らない依頼を列から消す**ためのもの。
    消す前に status/deleted.json へ丸ごと退避する（憲法：消さずに倉庫へ。取り消せるようにしておく）。
    """
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    it = _find_item(items, n)
    if it is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    if it.get("status") == "running" and it.get("pid"):
        try:
            os.kill(int(it["pid"]), 15)
        except Exception:
            pass
    box = os.path.join(REPO, "status", "deleted.json")
    d = load_json(box, {"items": []})
    it["deletedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    d.setdefault("items", []).append(it)
    d["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    save_json(box, d)
    q["items"] = [x for x in items if x.get("n") != n]
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を消しました（取り消せるよう status/deleted.json に控えてあります）" % n


def disk_report(_target=None):
    """容量が戻らない理由を実測で洗い出す（2026-09-05）。

    たまごさん「**一昨日60GB（120GB）空けたばかりでしょ。なんでそんなに早く埋まる？
    原因解明して。**」「**120GB他へ移動したはずでしょ。**」

    実測で分かっていること：本体(466GB)は残り20GB・96%。外付けiMac HDD(1.9TB)は893GB空き。
    **移動したのに本体が減っていない。**その理由をここで機械的に確かめる。
    いちばんありがちな犯人はTime Machineのローカルスナップショット
    （消しても移しても、スナップショットが古い状態を抱えていて容量が返ってこない）。
    """
    out = []

    def add(title, cmd, timeout=60):
        r = run(cmd, timeout=timeout)
        txt = ((r.stdout or "") + (r.stderr or "")).strip() if r else "(取得できず)"
        out.append("【%s】%s" % (title, txt[:600].replace("\n", " / ")))

    # 2026-09-05 23:12 **`df -h /` だけ見てはいけない。**
    #   macOS(APFS)は起動ディスクを「システム」と「データ」の2つのボリュームに分けている。
    #   `/` はシステム側（読み取り専用・約21GB）なので、**たまごさんのファイルの実態は
    #   `/System/Volumes/Data` の方**にある。ここを見ないと「空きがある/ない」を間違える。
    add("本体（システム側）", ["df", "-h", "/"])
    add("★本体（データ側＝実態）", ["df", "-h", "/System/Volumes/Data"])
    add("パージ可能（消せば戻る分）", ["bash", "-lc",
        "diskutil info / | grep -iE 'Free Space|Available|Container Free' | head -4"], timeout=30)
    # ① Time Machineのローカルスナップショット（消しても容量が返らない最大の理由）
    add("ローカルスナップショット", ["tmutil", "listlocalsnapshots", "/"])
    # ② パージ可能領域（Finderの「空き容量」と実際のズレ）
    add("パージ可能を含む詳細", ["diskutil", "info", "/"], timeout=40)
    # 2026-09-05 23:10 **`du` をここから外した。**
    #   ホーム全体を舐める `du -sx ~/* ~/Library` を入れたせいで、受信箱の処理が何分も止まり、
    #   後ろに並んでいた指示（心臓の入れ直しなど）が12分間1つも実行されなかった。
    #   **工場の中で重いコマンドを走らせない**（07:03に工場を止めたのと同じ失敗）。
    #   容量の内訳は `du` を使わずに済む方法（下の tmutil / diskutil）で足りる。
    #   どうしても内訳が要るときは、Dispatch自身のbashから範囲を絞って測る。
    add("ゴミ箱の中身の数", ["bash", "-lc", "ls -1 ~/.Trash 2>/dev/null | wc -l"], timeout=20)
    msg = " ／ ".join(out)
    try:
        io.open(os.path.join(REPO, "status", "disk_report.txt"), "w", encoding="utf-8").write(
            time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + "\n\n".join(out))
    except Exception:
        pass
    return "done", msg[:1800]


def disk_breakdown(_target=None):
    """何に何GB使っているかを、投げっぱなしで実測する（2026-09-06）。

    たまごさん「**何に何ギガ使ってるかも分からないんでね。移動して問題ないものがあるなら
    どんどん移動していきたい。**」

    `du` は重い。**工場の中で待つと心臓ごと詰まる**（9/05に実測。12分止めた）。
    だから**投げっぱなしにして、結果はファイルに書かせる。**こちらは何も待たない。
    出来上がりは status/disk_breakdown.txt。
    """
    out = os.path.join(REPO, "status", "disk_breakdown.txt")
    script = r'''
{
  echo "=== 測った時刻: $(date '+%F %T') ==="
  echo
  echo "=== 本体の空き（データ側＝実態）==="
  df -h /System/Volumes/Data | tail -1
  echo
  echo "=== ホーム直下（GB・大きい順）==="
  du -sx -m ~/* ~/Library 2>/dev/null | sort -rn | head -25 \
    | awk '{ printf "%8.1f GB  %s\n", $1/1024, substr($0, index($0,$2)) }'
  echo
  echo "=== 書類の中（GB・大きい順）==="
  du -sx -m ~/Documents/* 2>/dev/null | sort -rn | head -15 \
    | awk '{ printf "%8.1f GB  %s\n", $1/1024, substr($0, index($0,$2)) }'
  echo
  echo "=== デスクトップの中（GB・大きい順）==="
  du -sx -m ~/Desktop/* 2>/dev/null | sort -rn | head -15 \
    | awk '{ printf "%8.1f GB  %s\n", $1/1024, substr($0, index($0,$2)) }'
  echo
  echo "=== ライブラリの中（GB・大きい順）==="
  du -sx -m ~/Library/* 2>/dev/null | sort -rn | head -15 \
    | awk '{ printf "%8.1f GB  %s\n", $1/1024, substr($0, index($0,$2)) }'
  echo
  echo "=== 終わり ==="
} > "__OUT__" 2>&1
'''.replace("__OUT__", out)
    # ↑ ここは絶対に % 書式を使わないこと。
    #   スクリプトの中に awk の `%8.1f` が入っているので、`% out` と書くと
    #   Pythonがそれを書式指定子と誤解して TypeError で落ちる。
    #   2026-09-06 03:28、これで command_ingest が15分間まるごと止まり、
    #   たまごさんが押したボタンも新しい指示も1件も処理されなくなった。
    try:
        io.open(out, "w", encoding="utf-8").write(
            "測定中です（数分かかります）。始めた時刻: %s\n" % time.strftime("%F %T"))
        subprocess.Popen(["bash", "-lc", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        return "done", "容量の内訳を測り始めました（投げっぱなし・数分後に status/disk_breakdown.txt に出ます）"
    except Exception as e:
        return "failed", str(e)


def relay_fix(_target=None):
    """中継所（進捗表→Mac）を強制的に立て直し、**結果を実測で返す**（2026-09-05）。

    たまごさんの「今すぐ押しても入らない」「今何も動いてませんてなる」の正体は、
    cloudflared のクイックトンネルが**プロセスを残したまま無言で死ぬ**こと。
    見回りが pgrep で生死を見ていたので、毎回「生きている」と誤判定して素通りしていた。
    ここでは古いものを必ず殺してから立て直し、外から叩いて200が返るかまで確かめる。
    """
    import shutil as _sh
    steps = []
    rjson = os.path.join(REPO, "status", "relay.json")
    tunlog = os.path.join(REPO, "status", "relay_tunnel.log")

    # ① 掃除。古い受け口とトンネルを確実に落とす（ポート占有 Address already in use の元）
    run(["pkill", "-f", "cloudflared"], timeout=10)
    run(["pkill", "-f", "relay_server.py"], timeout=10)
    # localtunnel も必ず落とす。残しておくと二重に張って、どちらのURLが生きているか分からなくなる
    run(["pkill", "-f", "localtunnel"], timeout=10)
    run(["pkill", "-f", "lt --port"], timeout=10)
    time.sleep(2)
    lsof = run(["lsof", "-ti", "tcp:8788"], timeout=10)
    stuck = [x for x in ((lsof.stdout or "") if lsof else "").split() if x.strip()]
    for pid in stuck:
        run(["kill", "-9", pid], timeout=5)
    if stuck:
        steps.append("ポート8788を掴んでいた%d本を落とした" % len(stuck))
        time.sleep(1)

    # ② 受け口だけ先に立てる
    subprocess.Popen([sys.executable, os.path.join(REPO, "tools", "relay_server.py")],
                     stdout=open(os.path.join(REPO, "status", "relay.log"), "a"),
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)
    time.sleep(2)
    h = run(["curl", "-s", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}",
             "http://127.0.0.1:8788/health"], timeout=10)
    local_ok = h is not None and (h.stdout or "").strip() == "200"
    steps.append("受け口(ローカル)=%s" % ("OK" if local_ok else "NG"))
    if not local_ok:
        return "failed", "受け口が立ちません。" + " ／ ".join(steps)

    # ②' 家のWi-Fiの中で直接届く道（トンネル不要・切れない・URLが変わらない）
    lan = ""
    ip = run(["ipconfig", "getifaddr", "en0"], timeout=5)
    addr = (ip.stdout or "").strip() if ip is not None else ""
    if not addr:
        ip = run(["ipconfig", "getifaddr", "en1"], timeout=5)
        addr = (ip.stdout or "").strip() if ip is not None else ""
    if addr:
        lan = "http://%s:8788" % addr
        steps.append("家の中の道=%s" % lan)

    # ③ 道を2本用意する。cloudflared が張れなければ localtunnel へ落ちる。
    #    2026-09-05：たまごさんの回線は 7844 が塞がれていて cloudflared が hard_fail する。
    #    **道が1本しかないのが今日の詰まりの原因**なので、必ず代わりを持たせる。
    def _wait_url(pat, sec=45):
        for _ in range(sec):
            try:
                txt = io.open(tunlog, encoding="utf-8", errors="ignore").read()
            except Exception:
                txt = ""
            m = re.findall(pat, txt)
            if m:
                return m[-1]
            time.sleep(1)
        return ""

    def _outside_ok(u):
        c = run(["curl", "-s", "-m", "15", "-o", "/dev/null", "-w", "%{http_code}",
                 "-H", "bypass-tunnel-reminder: 1", u.rstrip("/") + "/health"], timeout=25)
        return c is not None and (c.stdout or "").strip() == "200"

    # **localtunnel を先に試す。**（2026-09-05）
    # たまごさんの回線は 7844番が塞がれていて cloudflared が張れない日がある。
    # 先に cloudflared を試すと、失敗が分かるまで毎回45秒を捨てることになる。
    # 繋がる方を先頭に置く。cloudflared が使えるようになったらここを戻せばよい。
    url = ""
    npx = _sh.which("npx")
    if npx:
        io.open(tunlog, "w").write("--- localtunnel ---\n")
        # **名前を固定する。**（2026-09-05）
        # 立て直すたびにURLが変わると、進捗表が読む status/relay.json の公開（5分おき）が
        # 追いつかず、たまごさんの画面はいつまでも「何も動いてない」ままになる。
        # 固定名なら、立て直しても進捗表は同じ場所を見続けられる。
        subprocess.Popen([npx, "-y", "localtunnel", "--port", "8788",
                          "--subdomain", "tamago-shinchoku"],
                         stdout=open(tunlog, "a"), stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        url = _wait_url(r"https://[a-z0-9-]+\.loca\.lt", 60)
        steps.append("localtunnel=%s" % (url or "URLが出ない"))
        # 名前が取られていたら、名前なしでもう一度（繋がることを優先する）
        if url and url != "https://tamago-shinchoku.loca.lt":
            steps.append("固定名は取られていたので別名で張った")
        if url and not _outside_ok(url):
            steps.append("localtunnelのURLは外から繋がらず→別の道へ")
            run(["pkill", "-f", "localtunnel"], timeout=10)
            url = ""
    else:
        steps.append("npxが無いのでlocaltunnelは使えない")

    if not url:
        cf = _sh.which("cloudflared") or os.path.expanduser("~/.tamago/bin/cloudflared")
        if os.path.exists(cf):
            io.open(tunlog, "a").write("\n--- cloudflared ---\n")
            subprocess.Popen([cf, "tunnel", "--url", "http://localhost:8788",
                              "--protocol", "http2", "--no-autoupdate"],
                             stdout=open(tunlog, "a"), stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
            url = _wait_url(r"https://[a-z0-9-]+\.trycloudflare\.com", 45)
            steps.append("cloudflared=%s" % (url or "URLが出ない"))
            if url and not _outside_ok(url):
                steps.append("cloudflaredのURLも外から繋がらず")
                run(["pkill", "-f", "cloudflared"], timeout=10)
                url = ""

    if not url:
        # トンネルが全部だめでも、家の中の道が生きていれば進捗表は動く。失敗扱いにしない。
        if lan:
            json.dump({"url": "", "lanUrl": lan, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                      io.open(rjson, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return "done", "外への道は張れませんでしたが、家の中の道は通っています（%s）／ %s" % (lan, " ／ ".join(steps))
        return "failed", "どの道も張れませんでした。" + " ／ ".join(steps)

    c = run(["curl", "-s", "-m", "20", "-o", "/dev/null", "-w", "%{http_code}", url + "/health"], timeout=30)
    code = (c.stdout or "").strip() if c is not None else ""
    json.dump({"url": url, "lanUrl": lan, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              io.open(rjson, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if code == "200":
        return "done", "中継所が復活しました（%s・実測200）／ %s" % (url, " ／ ".join(steps))
    return "failed", "URLは出ましたが外から繋がりません（%s → HTTP %s）／ %s" % (url, code or "不明", " ／ ".join(steps))


def auth_probe(_target=None):
    """claude CLI が本当に認証できるかを、いちばん軽い実行で確かめる（2026-09-05）。

    たまごさんは「ログインしている」と言っている。アプリのログインとCLIの認証は
    別々に持っているので、**推測せずに実際に叩いて確かめる。**
    """
    r = run([CLAUDE, "-p", "--model", "claude-sonnet-5", "--output-format", "json", "1+1は？"], timeout=60, env=claude_env())
    if r is None:
        return "failed", "claude が応答しませんでした（タイムアウト）"
    out = (r.stdout or "") + (r.stderr or "")
    if "Failed to authenticate" in out or "OAuth session expired" in out:
        return "failed", "まだ認証が切れています（OAuth session expired）"
    if '"result"' in out:
        try:
            import json as _j
            d = _j.loads(out.strip().splitlines()[-1])
            return "done", "認証OK。返事=%s" % str(d.get("result"))[:40]
        except Exception:
            return "done", "認証OK（応答あり）"
    return "failed", ("見慣れない応答: " + out[-200:]).replace("\n", " ")


def auth_where(_target=None):
    """認証がどこに入っているか・どのclaudeを使っているかを調べる（中身は読まない・場所と日時だけ）。"""
    import glob as _g
    lines = []
    for c in ("~/.local/bin/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude",
              "/Applications/Claude.app/Contents/Resources/claude",
              "~/.claude/local/claude"):
        pth = os.path.expanduser(c)
        if os.path.exists(pth):
            v = run([pth, "--version"], timeout=20)
            lines.append("%s : %s" % (c, ((v.stdout or v.stderr or "").strip()[:40] if v else "応答なし")))
    for c in ("~/.claude/.credentials.json", "~/Library/Application Support/Claude/.credentials.json"):
        pth = os.path.expanduser(c)
        lines.append("%s : %s" % (c, time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(pth)))
                                  if os.path.exists(pth) else "無し"))
    k = run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"], timeout=15)
    lines.append("キーチェーン(Claude Code-credentials): %s" % ("あり" if (k and k.returncode == 0) else "無し/読めない"))
    return "done", " ｜ ".join(lines)[:900]


def restart_heartbeat(_target=None):
    """心臓を入れ直す（2026-09-05）。

    bash の while ループは起動時にまとめて読み込まれるので、`heartbeat.sh` を書き換えても
    **走っている心臓には反映されない**（実測：auth_watch.py を足したのに1時間以上呼ばれていなかった）。
    ここで一度落とす。5分おきの巡回が新しい中身で立て直す。
    """
    # 2026-09-05 **確実に全部落としてから1本だけ立てる。**
    #   これまでは pkill 1回で満足していたので、落としきれなかった心臓が生き残り、
    #   立て直すたびに増えていった（16:25の2分間で12本）。心臓が増える＝受信箱が
    #   何回も読まれる＝**同じ指示が何回も実行されて、台帳に同じ仕事が何個も増える。**
    pidf = os.path.join(REPO, "status", "heartbeat.pid")
    for _ in range(3):
        run(["pkill", "-f", "tools/heartbeat.sh"], timeout=10)
        time.sleep(1)
        chk = run(["pgrep", "-f", "tools/heartbeat.sh"], timeout=10)
        if not (chk and (chk.stdout or "").strip()):
            break
    chk = run(["pgrep", "-f", "tools/heartbeat.sh"], timeout=10)
    left = [x for x in ((chk.stdout or "") if chk else "").split() if x.strip()]
    for pid in left:
        run(["kill", "-9", pid], timeout=5)
    try:
        os.remove(pidf)
    except Exception:
        pass
    time.sleep(0.5)
    try:
        subprocess.Popen(["bash", os.path.join(REPO, "tools", "heartbeat.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        return "failed", "落としたが立て直せませんでした: %s" % e
    time.sleep(2)
    chk2 = run(["pgrep", "-f", "tools/heartbeat.sh"], timeout=10)
    now_n = len([x for x in ((chk2.stdout or "") if chk2 else "").split() if x.strip()])
    return "done", "心臓を入れ直しました（いま%d本%s）" % (
        now_n, "" if now_n == 1 else "・★1本になっていません")


def auth_login_url(_target=None):
    """ログイン用のURLだけを取り出す（2026-09-05・安全版）。

    最初の版は `p.stdout.readline()` で待っていたため、`claude setup-token` が
    入力待ちで黙り込むと**心臓ごと固まった**（07:03〜、たまごさんにPCを再起動させた）。
    **ぶら下がる読み取りは絶対に使わない。必ず時間で切って、残骸も落とす。**
    """
    r = run([CLAUDE, "setup-token"], timeout=20)
    out = ((r.stdout or "") + (r.stderr or "")) if r else ""
    run(["pkill", "-f", "setup-token"], timeout=5)
    import re as _re
    m = _re.search(r"https://\S+", out)
    if m:
        return "done", "ログインURL: %s" % m.group(0)
    return "failed", ("URLが出ませんでした: " + out[-250:]).replace("\n", " ")


def auth_login_start(_target=None):
    """ログイン手続きを**投げっぱなしで**始める（2026-09-05）。

    分かったこと（実測）：
      `claude setup-token` はブラウザを開いてログインさせ、**たまごさんが完了するまで待つ。**
      前回はこちらが20秒で打ち切ったため、たまごさんがブラウザでログインしても
      トークンが保存されなかった（＝認証は切れたまま）。
    だから**待つのをやめる。**起動だけして、すぐ帰る。出力はファイルへ流す。
    こちらは何も待たないので、心臓は絶対に固まらない。
    後片付けは auth_watch.py が10分後に落とす。
    """
    # 2026-09-05 17:10 封印。たまごさん「Claude Codeさんが接続を希望していますって、
    #   もうこれやめてくんないかなって話だよ」。この手のアクションは動くたびにブラウザの
    #   ログイン画面を開く。既定で何もしない。~/.tamago/allow_login_helper を置いたときだけ動く。
    if not os.path.exists(os.path.expanduser("~/.tamago/allow_login_helper")):
        return "skipped", "ログイン手続きは封印中です（ブラウザのログイン画面を出さないため）"
    log = os.path.join(REPO, "status", "auth_login.log")
    run(["pkill", "-f", "setup-token"], timeout=5)   # 前の残骸があれば先に落とす
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s ログイン開始 ===\n" % time.strftime("%Y-%m-%d %H:%M:%S")).encode())
            p = subprocess.Popen([CLAUDE, "setup-token"], stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        io.open(os.path.join(REPO, "status", "auth_login.pid"), "w").write(str(p.pid))
        return "done", "ログイン手続きを始めました（ブラウザが開きます。完了までこちらは待ちません）"
    except Exception as e:
        return "failed", str(e)



def auth_ps(_target=None):
    """ログイン手続きのプロセスが生きているか、何を出しているかを見る（読むだけ・待たない）。"""
    r = run(["pgrep", "-fl", "setup-token"], timeout=10)
    alive = (r.stdout or "").strip() if r else ""
    log = os.path.join(REPO, "status", "auth_login.log")
    tail = ""
    try:
        with open(log, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 800))
            tail = f.read().decode("utf-8", "ignore")
    except Exception:
        pass
    return "done", ("生きているプロセス: %s ／ ログ末尾: %s" % (alive or "なし", tail.replace("\n", " ")))[:900]



def auth_login_pty(_target=None):
    """ログイン手続きを"にせの端末"付きで始めて、URLだけ拾う（2026-09-05）。

    分かったこと（実測）：
      `claude setup-token` は**端末（TTY）が無いと何も出さずに即死する。**
      だから「投げっぱなし」でも「時間で切る」でも、URLは一度も出なかった。
    → Pythonのptyで**にせの端末**を作って渡す。これで本来の表示（ログインURL）が出る。
      読み取りは select で25秒だけ。**プロセスは殺さない**（たまごさんがブラウザで
      ログインを終えるまで生かす）。後片付けは auth_watch.py が10分後にやる。
    """
    # 2026-09-05 17:10 封印。たまごさん「Claude Codeさんが接続を希望していますって、
    #   もうこれやめてくんないかなって話だよ」。この手のアクションは動くたびにブラウザの
    #   ログイン画面を開く。既定で何もしない。~/.tamago/allow_login_helper を置いたときだけ動く。
    if not os.path.exists(os.path.expanduser("~/.tamago/allow_login_helper")):
        return "skipped", "ログイン手続きは封印中です（ブラウザのログイン画面を出さないため）"
    import pty as _pty
    import select as _select
    log = os.path.join(REPO, "status", "auth_login.log")
    run(["pkill", "-f", "setup-token"], timeout=5)
    master, slave = _pty.openpty()
    try:
        p = subprocess.Popen([CLAUDE, "setup-token"], stdin=slave, stdout=slave, stderr=slave,
                             start_new_session=True, close_fds=True)
    except Exception as e:
        return "failed", "起動できませんでした: %s" % e
    os.close(slave)
    io.open(os.path.join(REPO, "status", "auth_login.pid"), "w").write(str(p.pid))
    out, t0 = "", time.time()
    while time.time() - t0 < 25:
        r, _, _ = _select.select([master], [], [], 1.0)
        if not r:
            continue
        try:
            chunk = os.read(master, 4096)
        except Exception:
            break
        if not chunk:
            break
        out += chunk.decode("utf-8", "ignore")
        if "http" in out:
            break
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s pty版 ===\n" % time.strftime("%Y-%m-%d %H:%M:%S")).encode())
            f.write(out.encode("utf-8", "ignore"))
    except Exception:
        pass
    import re as _re
    m = _re.search(r"https://\S+", out)
    if m:
        return "done", "ログインURL: %s" % m.group(0).rstrip("\x1b[0m")
    clean = _re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out)
    return "failed", ("URLが出ませんでした: " + clean[-300:]).replace("\n", " ")



def auth_login_helper(_target=None):
    """ログイン係（tools/auth_login_helper.py）を切り離して起動する。こちらは待たない。"""
    # 2026-09-05 17:10 封印。たまごさん「Claude Codeさんが接続を希望していますって、
    #   もうこれやめてくんないかなって話だよ」。この手のアクションは動くたびにブラウザの
    #   ログイン画面を開く。既定で何もしない。~/.tamago/allow_login_helper を置いたときだけ動く。
    if not os.path.exists(os.path.expanduser("~/.tamago/allow_login_helper")):
        return "skipped", "ログイン手続きは封印中です（ブラウザのログイン画面を出さないため）"
    try:
        subprocess.Popen(["python3", os.path.join(REPO, "tools", "auth_login_helper.py"), (_target or "login")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        return "failed", str(e)
    return "done", "ログイン係を起動しました（URLは status/auth_login_url.txt に出ます）"


def auth_login_code(target):
    """たまごさんがブラウザで受け取ったコードを、待っているログイン係へ渡す。"""
    code = (target or "").strip()
    if not code:
        return "failed", "コードが空です"
    io.open(os.path.join(REPO, "status", "auth_code.txt"), "w", encoding="utf-8").write(code)
    return "done", "コードを渡しました（数秒で保存されます）"



def auth_install_token(_target=None):
    """作られた長期トークンを、工場だけが読める場所へ移す（2026-09-05）。

    `claude setup-token` は**キーチェーンには保存せず、画面に出して終わる**。
    そのままではCLIは認証されないので、こちらで拾って
    `~/.tamago/claude_token`（権限600・git管理外）へ入れ、
    工場がclaudeを起動するときに `CLAUDE_CODE_OAUTH_TOKEN` として渡す。

    **中身はどこにも表示しない。**（このリポジトリはGitHub Pagesで公開されているため、
    status/ 配下には置かない。ログからも消す）
    """
    import re as _re
    log = os.path.join(REPO, "status", "auth_login.log")
    try:
        raw = io.open(log, encoding="utf-8", errors="ignore").read()
    except Exception:
        return "failed", "ログが読めません"
    m = _re.search(r"(sk-ant-oat01-[A-Za-z0-9_\-]+)", raw.replace(" ", ""))
    if not m:
        return "failed", "トークンが見つかりません"
    token = m.group(1)
    d = os.path.expanduser("~/.tamago")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "claude_token")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(token)
    os.chmod(p, 0o600)
    # 痕跡を消す（公開リポジトリの中に秘密を置かない）
    try:
        cleaned = _re.sub(r"sk-ant-oat01-[A-Za-z0-9_\- ]+", "（トークンは ~/.tamago/claude_token へ移しました）", raw)
        io.open(log, "w", encoding="utf-8").write(cleaned)
    except Exception:
        pass
    for junk in ("auth_login_url.txt", "auth_code.txt", "auth_login.pid", "auth_login_done.txt"):
        try:
            os.remove(os.path.join(REPO, "status", junk))
        except Exception:
            pass
    return "done", "トークンを ~/.tamago/claude_token へ入れました（権限600・ログからは消去）"



def auth_token_check(_target=None):
    """トークンが正しく置けているか、中身を出さずに確かめる。"""
    p = os.path.expanduser("~/.tamago/claude_token")
    if not os.path.exists(p):
        return "failed", "トークンのファイルがありません"
    t = io.open(p, encoding="utf-8").read().strip()
    env = claude_env()
    has = "CLAUDE_CODE_OAUTH_TOKEN" in env
    r = run([CLAUDE, "-p", "--model", "claude-sonnet-5", "--output-format", "json", "ping"],
            timeout=60, env=env)
    out = ((r.stdout or "") + (r.stderr or "")) if r else "（応答なし）"
    return "done", ("長さ%d文字・先頭%s／環境変数に入った:%s／結果: %s"
                    % (len(t), t[:12], has, out[-220:].replace("\n", " ")))


def _process_other(action, cmd):
    target = cmd.get("target")
    if action == "close_app":
        return close_app(target)
    if action == "resume":
        return resume(target)
    if action == "stop":
        return stop(target)
    if action == "handoff":
        return handoff(target)
    if action == "push_unlock":
        return push_unlock(target)
    if action == "restart_heartbeat":
        return restart_heartbeat(target)
    if action == "auth_where":
        return auth_where(target)
    if action == "auth_token_check":
        return auth_token_check(target)
    if action == "auth_install_token":
        return auth_install_token(target)
    if action == "auth_login_helper":
        return auth_login_helper(target)
    if action == "auth_login_code":
        return auth_login_code(target)
    if action == "auth_login_pty":
        return auth_login_pty(target)
    if action == "auth_ps":
        return auth_ps(target)
    if action == "auth_login_start":
        return auth_login_start(target)
    if action == "auth_login_url":
        return auth_login_url(target)
    if action == "auth_probe":
        return auth_probe(target)
    if action == "relay_fix":
        return relay_fix(target)
    if action == "disk_report":
        return disk_report(target)
    if action == "disk_breakdown":
        return disk_breakdown(target)
    if action == "git_unlock":
        return git_unlock(target)
    if action == "launch_pause":
        return launch_switch(False)
    if action == "launch_resume":
        return launch_switch(True)
    if action == "launch_cap":
        return launch_cap(target)
    return "failed", "不明なアクション: %s" % action


def main():
    os.makedirs(INBOX_DIR, exist_ok=True)
    out = load_json(OUT, {"results": []})
    # ---- 2026-09-05 18:50 **重複が無限に増えた真因。**----
    # 「処理済みかどうか」を commands.json の results だけで見ていた。
    # ところが results は最後に `[-200:]` で切り詰めている（肥やさないため）。
    # 200件を超えると**古いidが消える → その受信箱ファイルが「未処理」に戻り、また実行される。**
    # 受信箱のファイルは記録として消さない設計なので、**同じ指示が何度でも蘇る。**
    # 今日これで「バッジをakikoに戻す」が10個、「棚編集」が15個、台帳に積み上がった。
    # → 処理済みのidは**切り詰めない別ファイル**に全部貯める。表示用のresultsだけ200件に絞る。
    SEEN = os.path.join(REPO, "status", "processed_ids.json")
    seen = load_json(SEEN, {"ids": []})
    done_ids = set(seen.get("ids") or []) | {r.get("id") for r in out.get("results", [])}
    # 2026-09-04 受信箱を2つにした。
    #   Vault側(iCloud)は同期に数分かかることがあり、Dispatchからの指示が届くのが遅れた（実測4分以上）。
    #   リポジトリ内の status/inbox/ は同じディスクなので**すぐ届く**。Dispatchはこちらを使う。
    local_inbox = os.path.join(REPO, "status", "inbox")
    os.makedirs(local_inbox, exist_ok=True)
    files = sorted(glob.glob(os.path.join(INBOX_DIR, "*.md")) + glob.glob(os.path.join(local_inbox, "*.md")))
    changed = False
    for fp in files:
        try:
            txt = open(fp, encoding="utf-8").read()
        except Exception:
            continue
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            continue
        try:
            cmd = json.loads(m.group(0))
        except Exception:
            continue
        cid = cmd.get("id")
        if not cid or cid in done_ids:
            continue
        status, message = process(cmd)
        out.setdefault("results", []).append({
            "id": cid, "action": cmd.get("action"), "target": cmd.get("target"), "label": cmd.get("label"),
            "status": status, "message": message, "doneAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        done_ids.add(cid)
        changed = True
        print("%s: %s / %s -> %s (%s)" % (cid, cmd.get("action"), cmd.get("target"), status, message))
    if changed:
        # 処理済みidは切り詰めずに全部残す（切り詰めると同じ指示が蘇って重複が増える）
        try:
            ids = list(dict.fromkeys(list(seen.get("ids") or []) + list(done_ids)))
            save_json(SEEN, {"ids": ids[-20000:], "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        except Exception:
            pass
        out["results"] = out["results"][-200:]  # 表示用だけ絞る
        out["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save_json(OUT, out)


if __name__ == "__main__":
    main()
