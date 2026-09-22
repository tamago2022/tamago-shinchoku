#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
974番：LINE Creators Market「珍獣ラシコル」の【審査結果】の見張り。

たまごさんの指示（2026-09-20）：
「ようやくラシコル、リクエストできたから。申請通ったらすぐ教えて。見張ってちょうだいね」
「既にLINEからのメールを拾って見張る仕組みが過去に作られている。生きていれば乗せる。
 新しい常駐を増やさない」
「通ったら1行。落ちた場合も1行（理由はメールの原文から。こちらの解釈を足さない）」

設計（801番 check_line_reply.py と同じ骨組み・同じ心臓に相乗り）：
  - 新しいlaunchd常駐は作らない。tools/heartbeat.sh の既存tickから呼ばれるだけ。
  - 15秒ごとに呼ばれても、実際にIMAPへ繋ぐのは CHECK_INTERVAL_MINUTES に間引く。
  - 801番との違いは3点だけ：
      ① 見るのは「問い合わせの返信」ではなく「審査結果」（状態ファイルを分けてある。
         801番のDONEフラグに巻き込まれて審査結果を取りこぼす事故を避けるため）
      ② 間引きが1日1回ではなく30分（たまごさんが「すぐ」と言っているため）
      ③ 通知先が data.js ではなく status/dispatch_outbox.jsonl（1行で届く道）
  - 状態が変わったときだけ1回通知する。同じことを何度も言わない（冪等）。
  - 鍵（Gmailアプリパスワード）が無くて目が塞がっている間も、1回だけそれを通知する
    ＝「見張りが黙って死んでいる」状態を作らない。

注意：LINEのページ側は一切触らない。メールを読むだけ（IMAPはreadonlyで開く）。
"""
import email
import imaplib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header

ROOT = "/Users/mac/Desktop/tamago-shinchoku"
STATE_PATH = os.path.join(ROOT, "status", ".line_shinsa_state.json")
DONE_FLAG = os.path.join(ROOT, "status", ".line_shinsa_done")
NOKEY_FLAG = os.path.join(ROOT, "status", ".line_shinsa_nokey_notified")
OUTBOX = os.path.join(ROOT, "status", "dispatch_outbox.jsonl")
CRED_PATH = os.path.expanduser("~/.tamago/gmail_app_password")
GMAIL_ADDR = "eggypop2010@gmail.com"
SINCE_DATE = "19-Sep-2026"   # 審査リクエストを出した日より前のLINEメールを誤検知しない
JST = timezone(timedelta(hours=9))
CHECK_INTERVAL_MINUTES = 30
STICKER_NAME = "珍獣ラシコル"

FROM_CANDIDATES = ["line.me", "line-cc.com", "linecorp.com"]

# 「審査結果のメールかどうか」の門番。ここを通らないメールには一切触らない。
SHINSA_HINTS = [
    "審査", "リクエスト", "承認", "リジェクト", "却下", "差し戻",
    "Creators Market", "クリエイターズマーケット", "スタンプ", "sticker",
    "review", "approved", "rejected", "declined", "submission",
]

# 判定語。どちらか片方だけ当たったときだけ断定する。
# 「承認」「approved」の単体は入れない。「承認されませんでした」に食い込んで
# 差し戻しを通過と読み違えるため（2026-09-20の机上テストで実際に起きた）。
APPROVE_WORDS = [
    "承認されました", "承認いたしました", "承認となりました", "審査を通過",
    "リリースされました", "販売が開始", "販売開始",
    "has been approved", "was approved", "is now available", "is now on sale",
]
REJECT_WORDS = [
    "リジェクト", "却下", "差し戻", "非承認", "承認されませんでした", "修正が必要",
    "has been rejected", "was rejected", "declined", "rejected", "not approved",
]

URL_RE = re.compile(
    r"https?://(?:store\.line\.me/stickershop/product/\d+[^\s\)\]\">']*"
    r"|line\.me/S/sticker/\d+[^\s\)\]\">']*)"
)


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


def notify(title, message, n):
    """Dispatchの受信箱へ1行だけ積む（たまごさんに1行で届く既存の道）。"""
    rec = {
        "ts": datetime.now(JST).isoformat(),
        "n": n,
        "type": "line_shinsa",
        "title": title,
        "message": message,
    }
    os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def decode_any(s):
    if not s:
        return ""
    out = ""
    for text, enc in decode_header(s):
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def get_body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition", "")
            ):
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


def looks_like_shinsa(subject, body):
    hay = (subject + "\n" + body).lower()
    return any(h.lower() in hay for h in SHINSA_HINTS)


def classify(subject, body):
    """承認 / 差し戻し / 不明 を返す。両方当たった・どちらも当たらない＝不明。

    解釈を足さないための規則：不明のときは何も断定せず、件名をそのまま渡す。
    """
    hay = (subject + "\n" + body).lower()
    hit_ok = any(w.lower() in hay for w in APPROVE_WORDS)
    hit_ng = any(w.lower() in hay for w in REJECT_WORDS)
    if hit_ok and not hit_ng:
        return "approved"
    if hit_ng and not hit_ok:
        return "rejected"
    return "unknown"


def extract_url(body):
    m = URL_RE.search(body or "")
    return m.group(0) if m else ""


def extract_reason(body, limit=400):
    """差し戻し理由をメールの原文から抜く。要約も言い換えもしない。

    理由が書かれている行の周辺をそのまま切り出すだけ。見つからなければ本文の頭。
    """
    text = (body or "").replace("\r\n", "\n").strip()
    if not text:
        return ""
    lines = [ln.strip() for ln in text.split("\n")]
    keys = ["理由", "reason", "修正", "該当", "詳細", "ガイドライン", "guideline"]
    for i, ln in enumerate(lines):
        low = ln.lower()
        if any(k.lower() in low for k in keys) and len(ln) > 3:
            chunk = " / ".join([x for x in lines[i:i + 4] if x])
            return chunk[:limit]
    head = " / ".join([x for x in lines if x][:4])
    return head[:limit]


def build_message(verdict, subject, url, reason):
    if verdict == "approved":
        tail = url if url else "（販売ページURLはメール本文に無し。creator.line.meで確認が要ります）"
        return f"【{STICKER_NAME}】審査通りました　{tail}"
    if verdict == "rejected":
        return f"【{STICKER_NAME}】差し戻し。理由：{reason}"
    return f"【{STICKER_NAME}】LINEからメールが来ました（通過／差し戻しの判定つかず）。件名：{subject}"


def already_checked_recently():
    if not os.path.exists(STATE_PATH):
        return False
    try:
        st = json.load(open(STATE_PATH, encoding="utf-8"))
        last = st.get("lastCheckedAt")
        if not last:
            return False
        return (datetime.now(JST) - datetime.fromisoformat(last)) < timedelta(
            minutes=CHECK_INTERVAL_MINUTES
        )
    except Exception:
        return False


def main():
    if os.path.exists(DONE_FLAG):
        return 0
    if already_checked_recently():
        return 0

    # 二重に走らせない。心臓からの呼び出しと801番からの相乗りが同じ瞬間に重なっても、
    # 先に錠を取った1本だけが進む（同じメールで2回騒ぐ事故を止める）。
    lock = os.path.join(ROOT, "status", ".line_shinsa.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        try:  # 5分以上古い錠は、落ちた走行の置き土産とみなして外す
            if datetime.now().timestamp() - os.path.getmtime(lock) > 300:
                os.remove(lock)
        except Exception:
            pass
        return 0
    try:
        return _run()
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass


def _run():
    log_state(lastCheckedAt=datetime.now(JST).isoformat())

    # 鍵が無い＝目が塞がっている。黙って死なない。1回だけ知らせる。
    if not os.path.exists(CRED_PATH) or not open(CRED_PATH, encoding="utf-8").read().strip():
        log_state(blocked="no_credential", credPathExpected=CRED_PATH)
        if not os.path.exists(NOKEY_FLAG):
            notify(
                "審査結果の見張りが目を塞がれています",
                f"🛑【{STICKER_NAME}】審査結果を見張る仕組みは動いていますが、"
                f"Gmailを読む鍵（アプリパスワード）が {CRED_PATH} に無いのでメールが読めません。"
                "たまごさんが置いてくれれば、次の30分以内に自動で見張りが始まります。",
                "line-shinsa-nokey",
            )
            open(NOKEY_FLAG, "w", encoding="utf-8").write(datetime.now(JST).isoformat())
        return 0

    app_password = open(CRED_PATH, encoding="utf-8").read().strip()

    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(GMAIL_ADDR, app_password)
        M.select("INBOX", readonly=True)
        uids = set()
        for dom in FROM_CANDIDATES:
            typ, data = M.search(None, f'(FROM "{dom}" SINCE {SINCE_DATE})')
            if typ == "OK" and data and data[0]:
                uids.update(data[0].split())
        if not uids:
            log_state(found=0)
            M.logout()
            return 0

        hit = None
        for uid in sorted(uids, key=lambda x: int(x), reverse=True):
            typ, hdata = M.fetch(uid, "(BODY.PEEK[])")
            if typ != "OK" or not hdata or not hdata[0]:
                continue
            msg = email.message_from_bytes(hdata[0][1])
            subject = decode_any(msg.get("Subject", ""))
            body = get_body_text(msg).strip()
            if looks_like_shinsa(subject, body):
                hit = {
                    "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "subject": subject,
                    "from": decode_any(msg.get("From", "")),
                    "date": msg.get("Date", ""),
                    "messageId": msg.get("Message-ID", ""),
                    "body": body,
                }
                break
        M.logout()
    except Exception as e:
        log_state(error=str(e))
        return 0

    if not hit:
        log_state(found=len(uids), shinsaHit=0)
        return 0

    # 同じメールで二度騒がない（判定が「不明」でDONEを書かない間も、静かに見張り続ける）。
    st = {}
    if os.path.exists(STATE_PATH):
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            st = {}
    seen = st.get("notifiedMessageIds", [])
    key = hit["messageId"] or (hit["subject"] + "|" + hit["date"])
    if key in seen:
        log_state(found=len(uids), shinsaHit=1, skipped="already_notified")
        return 0

    verdict = classify(hit["subject"], hit["body"])
    url = extract_url(hit["body"])
    reason = extract_reason(hit["body"]) if verdict != "approved" else ""
    message = build_message(verdict, hit["subject"], url, reason)

    log_state(
        notifiedMessageIds=(seen + [key])[-20:],
        found=len(uids),
        shinsaHit=1,
        verdict=verdict,
        latestSubject=hit["subject"],
        latestFrom=hit["from"],
        latestDate=hit["date"],
        storeUrl=url,
    )
    notify(f"【{STICKER_NAME}】LINEの審査結果", message, f"line-shinsa-{verdict}")

    # 判定がついたときだけ見張りを終える。不明のままなら見張り続ける。
    if verdict in ("approved", "rejected"):
        json.dump(
            {
                "verdict": verdict,
                "subject": hit["subject"],
                "date": hit["date"],
                "messageId": hit["messageId"],
                "storeUrl": url,
                "notifiedAt": datetime.now(JST).isoformat(),
            },
            open(DONE_FLAG, "w", encoding="utf-8"),
            ensure_ascii=False,
            indent=2,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
