#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
732番（2026-09-11・2回のやり直し後の恒久対応）：
「完了したら聞かれる前に届く」の本丸。

これまでの実装（README「完了は聞かれる前に届く」節）は進捗表(PWA)側だけで、
Dispatch（たまごさんと会話しているセッション）には一切自動で届いていなかった。
たまごさんの言葉：「進捗表に上がってないから、みたいな。だけどツイッターみたいに
来てくれる方が楽だな」＝届け先は会話そのもの。

ここでは status/dispatch_outbox.jsonl（完了の生ログ）と status/dispatch_reported.json
（Dispatchが会話の中で"もう伝えた"と確定した番号の台帳）を突き合わせ、
「まだ会話で伝えていない完了」だけを取り出す。

呼び出し元は `~/.claude/hooks/tamago_ledger.py`（UserPromptSubmitフック＝たまごさんが
何か発言するたび毎回発火する）。build_notice() が None 以外を返したら、それをそのまま
additionalContext としてAIに渡す。AI側はその内容を次の返信の冒頭で必ず先に伝える。

dispatch_reported.json が消えている／壊れている場合も落ちない設計にする
（2026-09-11実測：一度も作られておらず「未報告か既報告か」自体が判定不能になっていた）。
無ければ空として扱い、二重に伝える方向に倒す（報告漏れの方がはるかに悪いため）。
書き込み時は直前の内容を1世代だけ .bak として残す。
"""
import io
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
REPORTED = os.path.join(REPO, "status", "dispatch_reported.json")
REPORTED_BAK = REPORTED + ".bak"

# 1回の通知でURL付きを何件まで本文で見せるか（それ以上は件数だけにする＝情報過多を避ける）
MAX_SHOW = 6


def load_reported():
    """壊れていても消えていても、必ず {"ns": [...]} の形で返す。例外を外へ出さない。"""
    try:
        with io.open(REPORTED, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("ns"), list):
            return data
    except Exception:
        pass
    # 壊れている／存在しない時は、直前の世代バックアップから拾えるなら拾う
    try:
        with io.open(REPORTED_BAK, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("ns"), list):
            return data
    except Exception:
        pass
    return {"ns": []}


def save_reported(data):
    """世代バックアップを1つ残してから保存する。失敗しても呼び出し側は握りつぶす前提。"""
    try:
        if os.path.exists(REPORTED):
            try:
                with io.open(REPORTED, encoding="utf-8") as f:
                    prev = f.read()
                with io.open(REPORTED_BAK, "w", encoding="utf-8") as f:
                    f.write(prev)
            except Exception:
                pass
        tmp = REPORTED + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, REPORTED)
    except Exception:
        pass


def read_outbox_rows():
    rows = []
    try:
        with io.open(OUTBOX, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return rows


def pending_rows(rows, reported_ns):
    """通常の完了報告（n が数値）だけを対象にする。ok=false（失敗した完了）も含める
    ——ここで漏らすと tools/kenpou_check.py の11番目「未報告の完了」が失敗分だけ
    永遠に赤のまま残ってしまう（2026-09-11実測：ok=falseが19件、reportedに登録
    されないまま放置されていた）。
    cost_confirm/owner_redo_escalation（n が "<番号>-cost" 等の文字列）は
    進捗表の💴ボタン・failures.md記録という既存の別ルートで扱われるためここでは除外する。
    同じ番号が複数回完了報告されている（連番タスクの1/9等）場合は最新の1件だけ残す。
    """
    reported_set = set(reported_ns or [])
    latest = {}
    for row in rows:
        n = row.get("n")
        if not isinstance(n, int):
            continue
        if n in reported_set:
            continue
        latest[n] = row  # 同じnは後勝ち＝最新の完了行
    return [latest[n] for n in sorted(latest.keys())]


def _clip(text, limit=26):
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit - 1] + "…"
    return text


def format_line(row):
    urls = row.get("urls") or []
    title = _clip(row.get("title"))
    n = row.get("n")
    if not row.get("ok"):
        return "⚠️ %s番 うまくいかず：%s" % (n, title)
    if urls:
        return "🎉 %s番 上がりました：%s\n%s" % (n, title, urls[0])
    return "🔧 %s番 完了：%s" % (n, title)


def build_notice(max_show=MAX_SHOW):
    """未報告の完了があれば通知テキストを返す。無ければ None。

    【750番・2026-09-12修正】旧実装は「6件を超えた分」を件数だけ見せて
    "確認ページで"と案内しつつ、実際にはそのページを作らないまま
    pend全件（=overflow分も含めて）をその場でdispatch_reported.jsonへ
    既読登録していた。Dispatchとの会話が長く空くとbacklogが6件を大きく
    超え、超過分の内容（title/url）は誰にも見せられないまま永久に
    「報告済み」扱いになって消えていた（715番の日次点検が実際に
    「132件たまっている」を検知した根本原因）。
    → 今回から、既読登録の対象は「実際に本文へ出した分」だけに限定する。
      表示しきれなかった分（failed/with_urlのoverflow）は既読にせず、
      次回build_notice()が呼ばれた時にまた候補として残す。
      二重報告にはなるが、内容が消えるより遥かにマシ（既存方針と同じ）。
      without_url（urlも無い裏方完了）は元々中身が薄いため、件数表示のみで
      引き続き即時に既読化する（これは元の設計のまま維持）。
    """
    reported = load_reported()
    rows = read_outbox_rows()
    pend = pending_rows(rows, reported.get("ns"))
    if not pend:
        return None

    failed = [r for r in pend if not r.get("ok")]
    with_url = [r for r in pend if r.get("ok") and r.get("urls")]
    without_url = [r for r in pend if r.get("ok") and not r.get("urls")]

    lines = []
    # 失敗は握りつぶさない。件数が多くても直近だけは必ず本文に出す。
    shown_failed = failed[-max_show:]
    for row in shown_failed:
        lines.append(format_line(row))
    shown_url = with_url[-max_show:]
    rest_url_count = len(with_url) - len(shown_url)
    for row in shown_url:
        lines.append(format_line(row))

    tail = []
    rest_failed_count = len(failed) - len(shown_failed)
    if rest_failed_count > 0:
        tail.append("（ほか %d件、うまくいかなかった分・次回以降に古い順で伝えます）" % rest_failed_count)
    if rest_url_count > 0:
        tail.append("（ほか %d件、URLあり・次回以降に古い順で伝えます）" % rest_url_count)
    if without_url:
        tail.append("（裏方の完了 %d件・省略）" % len(without_url))

    header = "【🔔 完了しました・まだ伝えていない分】"
    body = "\n\n".join(lines)
    footer = "\n".join(tail)
    notice = header + "\n\n" + body if body else header
    if footer:
        notice += "\n" + footer
    notice += "\n\n↑これを次の返信の冒頭で必ず先に伝えてください（1件＝1行＋URL）。"

    # 既読にするのは「実際に本文へ出した分」＋「without_url（中身が薄い裏方完了）」だけ。
    # overflow（表示しきれなかったfailed/with_url）は既読にせず次回へ持ち越す＝内容ロスト防止。
    shown_ns = (
        [r.get("n") for r in shown_failed]
        + [r.get("n") for r in shown_url]
        + [r.get("n") for r in without_url]
    )
    new_ns = sorted(set((reported.get("ns") or []) + shown_ns))
    save_reported({"ns": new_ns, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00")})

    return notice


if __name__ == "__main__":
    # 単体テスト用：実際には保存まで進めず、今どれだけ未報告があるかだけ見たい時に使う。
    r = load_reported()
    rows = read_outbox_rows()
    p = pending_rows(rows, r.get("ns"))
    print("reported ns件数:", len(r.get("ns") or []))
    print("未報告(pending)件数:", len(p))
    for row in p[-10:]:
        print(" -", row.get("n"), row.get("title"), row.get("urls"))
