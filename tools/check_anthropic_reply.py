#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
626番：Anthropicサポート返信の見張り。

たまごさんが2026-09-07にsupport@anthropic.comへ問い合わせを送った。
1日1回（launchd）起動し、Gmail(eggypop2010@gmail.com)のINBOXをIMAPで見て、
anthropic.com からの新着があれば data.js の anthropicReply を書き換えてpushする。

見るのは送り主・件名・日付だけ（本文は一切読まない＝
BODY.PEEK[HEADER.FIELDS(...)] でヘッダーだけ取得し、既読フラグも立てない）。

1回知らせたら status/.anthropic_watch_done を作り、以後launchdが毎日呼んでも
即座に何もせず終わる（「見張りは止める」の実装）。新しい問い合わせを見張り
直したくなったら、このフラグファイルを消せば再開する。
"""
import email
import imaplib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header

ROOT = "/Users/mac/Desktop/tamago-shinchoku"
STATE_PATH = os.path.join(ROOT, "status", ".anthropic_watch_state.json")
DONE_FLAG = os.path.join(ROOT, "status", ".anthropic_watch_done")
DATA_JS = os.path.join(ROOT, "data.js")
CRED_PATH = os.path.expanduser("~/.tamago/gmail_app_password")
GMAIL_ADDR = "eggypop2010@gmail.com"
SINCE_DATE = "07-Sep-2026"  # 問い合わせを送った日より前のものは見ない（古い無関係メールの誤検知防止）
JST = timezone(timedelta(hours=9))


def log_state(**kv):
    st = {}
    if os.path.exists(STATE_PATH):
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            st = {}
    st.update(kv)
    st["lastRunAt"] = datetime.now(JST).isoformat()
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(st, open(STATE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def decode(s):
    if not s:
        return ""
    out = ""
    for text, enc in decode_header(s):
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def run_git(args):
    return subprocess.run(["git"] + args, cwd=ROOT, check=True, capture_output=True, text=True)


def main():
    if os.path.exists(DONE_FLAG):
        log_state(skipped="already_notified")
        return 0

    if not os.path.exists(CRED_PATH):
        log_state(blocked="no_credential", credPathExpected=CRED_PATH)
        return 0

    app_password = open(CRED_PATH, encoding="utf-8").read().strip()
    if not app_password:
        log_state(blocked="empty_credential", credPathExpected=CRED_PATH)
        return 0

    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(GMAIL_ADDR, app_password)
        M.select("INBOX", readonly=True)
        typ, data = M.search(None, f'(FROM "anthropic.com" SINCE {SINCE_DATE})')
        if typ != "OK":
            log_state(error=f"search_failed:{typ}")
            M.logout()
            return 0
        uids = data[0].split()
        if not uids:
            log_state(found=0)
            M.logout()
            return 0
        # 何件来ていても、一番新しい1件が分かれば「来ています」の役目は足りる
        latest_uid = uids[-1]
        typ, hdata = M.fetch(latest_uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        M.logout()
        if typ != "OK" or not hdata or not hdata[0]:
            log_state(error="fetch_failed")
            return 0
        msg = email.message_from_bytes(hdata[0][1])
        subject = decode(msg.get("Subject", ""))
        from_ = decode(msg.get("From", ""))
        date_ = msg.get("Date", "")
        log_state(found=len(uids), latestSubject=subject, latestFrom=from_, latestDate=date_)
    except Exception as e:
        log_state(error=str(e))
        return 0

    gmail_url = "https://mail.google.com/mail/u/0/#search/from%3Aanthropic.com"
    now_iso = datetime.now(JST).isoformat()
    obj_js = (
        "{\n"
        f"    subject: {json.dumps(subject, ensure_ascii=False)},\n"
        f"    from: {json.dumps(from_, ensure_ascii=False)},\n"
        f"    date: {json.dumps(date_, ensure_ascii=False)},\n"
        f"    gmailUrl: {json.dumps(gmail_url, ensure_ascii=False)},\n"
        f"    detectedAt: {json.dumps(now_iso, ensure_ascii=False)}\n"
        "  }"
    )
    src = open(DATA_JS, encoding="utf-8").read()
    pattern = re.compile(r"anthropicReply:\s*(?:null|\{[\s\S]*?\})\s*,")
    if not pattern.search(src):
        log_state(error="anthropicReply_field_not_found_in_data_js")
        return 0
    new_src = pattern.sub(f"anthropicReply: {obj_js},", src, count=1)
    open(DATA_JS, "w", encoding="utf-8").write(new_src)

    try:
        run_git(["add", "data.js"])
        run_git(["commit", "-m", "626番: Anthropicサポート返信を検知、進捗表に表示"])
        # 他の常設セッションが同時にpushしていることがあるため、先にrebaseで取り込んでから送る
        try:
            run_git(["pull", "--rebase", "origin", "main"])
        except subprocess.CalledProcessError as e:
            log_state(error=f"git_pull_rebase_failed:{e.stderr[:300] if e.stderr else ''}")
            return 0
        run_git(["push", "origin", "main"])
        log_state(pushed=True)
    except subprocess.CalledProcessError as e:
        log_state(error=f"git_failed:{e.stderr[:300] if e.stderr else ''}")
        return 0

    open(DONE_FLAG, "w", encoding="utf-8").write(now_iso)
    return 0


if __name__ == "__main__":
    sys.exit(main())
