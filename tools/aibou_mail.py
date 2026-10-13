#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
34655番：Gmail相棒メール窓口（スマホからいつでも呼べる相棒・Gmail側）

たまごさんが2026-08-07(金) 02:06にスマホで言った依頼：
「Gmailやカレンダーをつないで、スマホからいつでも呼べる相棒に育てます」

カレンダー側は既存の tools/deadline_watch.py が担当済み
（share/calendar.ics を6時間ごとに書き換え、status/public/calendar.ics として公開・
  status/calendar_todo.json に手入力用の候補も出している）。
このファイルは「Gmail」側だけを新規に足す。

やること：
  スマホのGmailアプリから eggypop2010@gmail.com 宛て（＝自分宛て）に、
  件名の先頭を「AI:」または「たまご:」で始めてメールを送ると、
  この見張りが拾って発車待ち（status/queue.json）へ自動で積む。
  新しい台帳は作らない。既存の command_ingest.queue_add()（進捗表の
  「＋発車待ちに追加」と全く同じ入口）をそのまま使う。

鍵（~/.tamago/gmail_app_password）がまだ置かれていない間は、何もせず
静かに待つ（check_line_reply.py / renraku.py と同じ守り方。鍵が無い理由が
前回と同じ間は催促を増やさない＝1026番の教訓）。鍵の有無とお願いの出し方は
tools/kagi_seimei.py（既存の鍵生命チェック）が既に拾っている。ここで
たまごさんへ新しく催促を増やさない。

使い方: python3 tools/aibou_mail.py            （心臓から15秒おきに呼ばれる想定。内部で10分に間引く）
        python3 tools/aibou_mail.py --force    （間引きを無視して今すぐ1回だけ実行。手動確認用）
"""
import email
import imaplib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATE_PATH = os.path.join(ROOT, "status", ".aibou_mail_state.json")
STATUS_PATH = os.path.join(ROOT, "status", "aibou_mail.json")
CRED_PATH = os.path.expanduser("~/.tamago/gmail_app_password")
GMAIL_ADDR = "eggypop2010@gmail.com"
JST = timezone(timedelta(hours=9))
CHECK_INTERVAL_MIN = 10  # 心臓は15秒おきに呼ぶが、実際にIMAPへ繋ぐのはここで10分に間引く
# 件名の先頭が「AI:」「たまご:」（全角コロンも許容）で始まるものだけを相棒メールとして拾う
TRIGGER_RE = re.compile(r"^\s*(?:AI|たまご)\s*[:：]\s*(.+)$", re.IGNORECASE | re.DOTALL)


def decode_hdr(s):
    if not s:
        return ""
    out = ""
    for text, enc in decode_header(s):
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def log_state(**kv):
    st = load_json(STATE_PATH, {})
    # 1026番と同じ守り方：止まっている理由が前回と同じ間は書き換えない（催促を増やさない）。
    if kv.get("blocked") and st.get("blocked") == kv.get("blocked"):
        return
    st.update(kv)
    if "processed" in kv:
        st.pop("blocked", None)
    st["lastRunAt"] = datetime.now(JST).isoformat()
    save_json(STATE_PATH, st)


def already_checked_recently():
    st = load_json(STATE_PATH, {})
    last = st.get("lastCheckedAt")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    return (datetime.now(JST) - last_dt) < timedelta(minutes=CHECK_INTERVAL_MIN)


def update_status(connected, reason=None, recent_append=None):
    st = load_json(STATUS_PATH, {"recent": []})
    st["connected"] = connected
    if reason is not None:
        st["reason"] = reason
    elif connected:
        st.pop("reason", None)
    if recent_append:
        st["recent"] = ([recent_append] + st.get("recent", []))[:20]
    st["checkedAt"] = datetime.now(JST).isoformat()
    save_json(STATUS_PATH, st)


def main():
    force = "--force" in sys.argv
    if not force and already_checked_recently():
        return 0
    log_state(lastCheckedAt=datetime.now(JST).isoformat())

    if not os.path.exists(CRED_PATH):
        log_state(blocked="no_credential")
        update_status(False, reason="Gmailアプリパスワード未登録（~/.tamago/gmail_app_password が無い。"
                                     "初回登録はたまごさん本人のGoogleアカウント操作が必要）")
        return 0
    app_password = open(CRED_PATH, encoding="utf-8").read().strip()
    if not app_password:
        log_state(blocked="empty_credential")
        update_status(False, reason="Gmailアプリパスワードのファイルが空")
        return 0

    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(GMAIL_ADDR, app_password)
        M.select("INBOX")  # 処理後に既読フラグを立てるので読み書き接続
        typ, data = M.search(None, "(UNSEEN)")
        if typ != "OK":
            log_state(error="search_failed")
            update_status(True, reason="IMAP検索に失敗")
            M.logout()
            return 0
        uids = data[0].split() if data and data[0] else []
        queued = []
        for uid in uids:
            typ2, hdata = M.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
            if typ2 != "OK" or not hdata or not hdata[0]:
                continue
            msg = email.message_from_bytes(hdata[0][1])
            subject = decode_hdr(msg.get("Subject", ""))
            from_ = decode_hdr(msg.get("From", ""))
            m = TRIGGER_RE.match(subject or "")
            if not m or GMAIL_ADDR not in (from_ or ""):
                continue  # トリガー件名でない・自分宛て以外は相棒メールとして扱わない
            task_text = m.group(1).strip()
            if task_text:
                import command_ingest
                status, detail = command_ingest.queue_add(
                    task_text, priority=None, label="Gmail相棒経由（34655番）", origin="user")
                queued.append({
                    "subject": subject, "queued": task_text,
                    "status": status, "detail": detail,
                    "at": datetime.now(JST).isoformat(),
                })
            M.store(uid, "+FLAGS", "\\Seen")  # 空文でも二重処理しないよう既読化
        M.logout()
        if queued:
            log_state(processed=len(queued), lastQueued=queued[-1])
            for q in queued:
                update_status(True, recent_append=q)
        else:
            log_state(processed=0)
            update_status(True)
    except Exception as e:
        log_state(error=str(e))
        update_status(False, reason=str(e)[:200])
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
