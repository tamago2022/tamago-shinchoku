#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
801番：LINE（Creators Market／スタンプメーカー）への問い合わせ返信の見張り。
626番のcheck_anthropic_reply.pyと全く同じ骨組み（新しい常駐は増やさず既存の心臓に相乗り）。

たまごさんの指示（2026-09-13）：
「1日1回、Gmail(eggypop2010@gmail.com)でLINEからの返信を探す。
 既存の見回り便に相乗りする。新しい常駐を増やさない。」
「2週間は待てない。月曜・火曜で返事が欲しい」

見るのは送り主・件名・日付だけではなく、本文まで読む（626番と違い、
たまごさんの指示で「全文をそのまま確認ページに貼る（要約しない）」ため、
本文を読む必要がある。読むだけでフラグは立てない = readonly接続）。

1回検知したら status/.line_watch_done を作り、以後は何もしない
（新しい問い合わせを見張り直したくなったらこのフラグを消せば再開）。
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
STATE_PATH = os.path.join(ROOT, "status", ".line_watch_state.json")
DONE_FLAG = os.path.join(ROOT, "status", ".line_watch_done")
DATA_JS = os.path.join(ROOT, "data.js")
CRED_PATH = os.path.expanduser("~/.tamago/gmail_app_password")
GMAIL_ADDR = "eggypop2010@gmail.com"
SINCE_DATE = "13-Sep-2026"  # 問い合わせを送った日より前の無関係メールを誤検知しない
JST = timezone(timedelta(hours=9))
CHECK_INTERVAL_HOURS = 20  # 「1日1回」の実装。心臓は15秒おきに呼ぶが、実際にIMAPへ繋ぐのはここで間引く

# LINE公式からの返信を拾うための緩めの条件（差出人ドメイン or 件名・本文キーワード）
FROM_CANDIDATES = ["line.me", "line-cc.com", "linecorp.com"]
SUBJECT_KEYWORDS = ["LINE Creators Market", "LINEスタンプ", "お問い合わせ", "受付番号", "クリエイターズマーケット"]


def log_state(**kv):
    st = {}
    if os.path.exists(STATE_PATH):
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            st = {}
    # ★1026番（2026-09-23）たまごさん「投げるのをやめる（催促も回数も増やさない）」
    #   鍵が無い間、この紙を毎回書き換えていたので、台帳が「78回走った」と数えていた。
    #   実際には1度もGmailに繋ぎに行っていない。**理由が前と同じなら、書き換えない。**
    #   赤は消えない（blocked はそのまま残る）。増えるのをやめるだけ。
    #   ※ st.update(kv) の**前に**見る。後で見ると必ず一致して、永久に書かなくなる。
    if kv.get("blocked") and st.get("blocked") == kv.get("blocked") \
            and os.path.exists(STATE_PATH):
        return
    st.update(kv)
    # 鍵が戻って実際に読めた回は、**前の止め札を必ず消す**。
    # 消さないと、直ったのに赤が残り続ける（それも嘘のログ）。
    if "found" in kv or "hits" in kv:
        st.pop("blocked", None)
        st.pop("credentialMissingNotified", None)
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


def get_body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                try:
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    continue
        return ""
    try:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")
    except Exception:
        return ""


def run_git(args):
    return subprocess.run(["git"] + args, cwd=ROOT, check=True, capture_output=True, text=True)


def already_checked_recently():
    if not os.path.exists(STATE_PATH):
        return False
    try:
        st = json.load(open(STATE_PATH, encoding="utf-8"))
    except Exception:
        return False
    last = st.get("lastCheckedAt")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    return (datetime.now(JST) - last_dt) < timedelta(hours=CHECK_INTERVAL_HOURS)


def main():
    if os.path.exists(DONE_FLAG):
        log_state(skipped="already_notified")
        return 0

    if already_checked_recently():
        return 0
    log_state(lastCheckedAt=datetime.now(JST).isoformat())

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
        or_from = " OR ".join(f'FROM "{d}"' for d in FROM_CANDIDATES)
        # IMAP検索は単純なORの入れ子が面倒なため、ドメインごとに検索してUIDを合算する
        uids = set()
        for dom in FROM_CANDIDATES:
            typ, data = M.search(None, f'(FROM "{dom}" SINCE {SINCE_DATE})')
            if typ == "OK" and data and data[0]:
                uids.update(data[0].split())
        if not uids:
            log_state(found=0)
            M.logout()
            return 0
        latest_uid = sorted(uids, key=lambda x: int(x))[-1]
        typ, hdata = M.fetch(latest_uid, "(BODY.PEEK[])")
        M.logout()
        if typ != "OK" or not hdata or not hdata[0]:
            log_state(error="fetch_failed")
            return 0
        msg = email.message_from_bytes(hdata[0][1])
        subject = decode(msg.get("Subject", ""))
        from_ = decode(msg.get("From", ""))
        date_ = msg.get("Date", "")
        body = get_body_text(msg).strip()
        log_state(found=len(uids), latestSubject=subject, latestFrom=from_, latestDate=date_)
    except Exception as e:
        log_state(error=str(e))
        return 0

    gmail_url = "https://mail.google.com/mail/u/0/#search/from%3Aline.me"
    now_iso = datetime.now(JST).isoformat()
    obj_js = (
        "{\n"
        f"    subject: {json.dumps(subject, ensure_ascii=False)},\n"
        f"    from: {json.dumps(from_, ensure_ascii=False)},\n"
        f"    date: {json.dumps(date_, ensure_ascii=False)},\n"
        f"    body: {json.dumps(body, ensure_ascii=False)},\n"
        f"    gmailUrl: {json.dumps(gmail_url, ensure_ascii=False)},\n"
        f"    detectedAt: {json.dumps(now_iso, ensure_ascii=False)}\n"
        "  }"
    )
    src = open(DATA_JS, encoding="utf-8").read()
    pattern = re.compile(r"lineReply:\s*(?:null|\{[\s\S]*?\})\s*,")
    if not pattern.search(src):
        log_state(error="lineReply_field_not_found_in_data_js")
        return 0
    new_src = pattern.sub(f"lineReply: {obj_js},", src, count=1)
    open(DATA_JS, "w", encoding="utf-8").write(new_src)

    try:
        run_git(["add", "data.js"])
        run_git(["commit", "-m", "801番: LINE問い合わせの返信を検知、進捗表に表示"])
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
    rc = main()
    # 974番（2026-09-20）：ラシコルの審査結果の見張りを、この呼び出しに相乗りさせる。
    #   heartbeat.sh にも1行足してあるが、動いている心臓はループ本体を既に読み込み済みで、
    #   入れ直すまで新しい行を読まない。ここに置けば**心臓を入れ直さなくても今日から効く**。
    #   中で30分に間引き＋錠を持っているので、両方から呼ばれても二重には走らない。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import check_line_shinsa
        check_line_shinsa.main()
    except Exception:
        pass
    sys.exit(rc)
