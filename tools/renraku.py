#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
896番：外部連絡いっぱつ（renraku.py）

たまごさんの指示（2026-09-16 23:20）：
「LINEだとか外部にメールを送信するんだったら、もう100%、下書きと、英語と日本語と、
 LINEは日本だから日本語でいいけれども、もうそれがぱっと出る仕組み。
 俺は押すだけでいいっていう仕組み。もうこれも何回も言わせちゃだめだよ。」

使い方:
  python3 tools/renraku.py send <相手キー> --subject "<件名(日本語)>" --body-ja "<本文(日本語)>" \
      [--subject-en "<件名(英語)>" --body-en "<本文(英語)>"] [--body-file <path>] [--dry-run]
  python3 tools/renraku.py list        窓口台帳を表示
  python3 tools/renraku.py check       登録済みの送信について、Gmailで返信が来ていないか探す（1日1回想定）

設計方針（896番で確定した制約に基づく）:
  - 相手・窓口は status/renraku_madoguchi.json に事前登録しておく（無ければ先に調べて登録する。
    このスクリプト自身は自然言語で窓口を検索しない。renraku.pyを使うAI/人間が事前に
    madoguchi.jsonへ1件追記してから呼ぶ。二度と同じ調べ物をしないための貯蔵庫）。
  - 文面（件名・本文）の作文はこのスクリプトの外（呼び出し元のAIエージェント）が担当する。
    機械翻訳APIキーはこの環境に無いため、renraku.py自身は英訳しない。
    海外窓口(country=overseas)は --subject-en / --body-en が無いとエラーで止める
    （英日セット必須というたまごさんの指示を、ここで機械的に強制する）。
  - webform: 専用のNode.jsヘルパー(tools/_renraku_cdp.mjs)でChromeの実タブを開き、
    スクショを撮る。送信ボタンは押さない（自動で押す実装を一切書かない＝物理的に押せない）。
  - email: 2つの経路を両方試す。
      (a) IMAP APPENDでGmailの下書きフォルダへ直接下書きを保存する（ブラウザ不要・最も確実）。
          ~/.tamago/gmail_app_password が無い場合はスキップし、その旨を結果へ記録する。
      (b) Gmail作成画面のURL(https://mail.google.com/mail/u/0/?view=cm&...)を
          Chromeで開いてスクショを撮る（(a)の裏取り・目視確認用）。
          ログイン済みプロファイルが無いとログイン画面が開くだけになるが、それも証拠として残す。
  - 送信は絶対に押さない。記録は status/renraku.json に追記する。
  - 返信の見張りは `check` サブコマンドで行う。1日1回想定（heartbeatに相乗りする運用は
    既存の check_line_reply.py / check_anthropic_reply.py と同じ形）。2週間来なければ
    その旨を1回だけ報告する（is_stale判定）。
"""
import argparse
import base64
import email as email_lib
import imaplib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header

ROOT = "/Users/mac/Desktop/tamago-shinchoku"
MADOGUCHI_PATH = os.path.join(ROOT, "status", "renraku_madoguchi.json")
RECORD_PATH = os.path.join(ROOT, "status", "renraku.json")
SHOT_DIR = os.path.join(ROOT, "share", "check", "renraku")
CDP_HELPER = os.path.join(ROOT, "tools", "_renraku_cdp.mjs")
GMAIL_ADDR = "eggypop2010@gmail.com"
GMAIL_CRED_PATH = os.path.expanduser("~/.tamago/gmail_app_password")
JST = timezone(timedelta(hours=9))
STALE_DAYS = 14
# 891番：毎日メールの見張り（朝・夜の2回想定）。heartbeatは15秒おきに呼ぶが、
# 実際にIMAPへ繋ぐのはここで間引く（check_anthropic_reply.py/check_line_reply.pyと同じ設計）。
CHECK_STATE_PATH = os.path.join(ROOT, "status", ".renraku_check_state.json")
CHECK_INTERVAL_HOURS = 10
DISPATCH_OUTBOX = os.path.join(ROOT, "status", "dispatch_outbox.jsonl")
# 相手ごとにどのプロファイル(CDPポート)で開くか。今のところ全窓口を chrome-line(9224) に集約
# （新規プロファインは初回ログインの人手が要るため増やさない。896番の判断）。
DEFAULT_CDP_PORT = 9224


def now_iso():
    return datetime.now(JST).isoformat()


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


def load_madoguchi():
    return load_json(MADOGUCHI_PATH, {})


def find_target(key_or_name):
    madoguchi = load_madoguchi()
    key_or_name = key_or_name.strip()
    if key_or_name in madoguchi:
        return key_or_name, madoguchi[key_or_name]
    low = key_or_name.lower()
    for key, info in madoguchi.items():
        if key.lower() == low:
            return key, info
        for alias in info.get("aliases", []):
            if alias.lower() == low or low in alias.lower():
                return key, info
    return None, None


def run_node(args):
    """tools/_renraku_cdp.mjs を呼び、標準出力のJSON1行をパースして返す。"""
    try:
        r = subprocess.run(
            ["node", CDP_HELPER] + args, cwd=ROOT, capture_output=True, text=True, timeout=40
        )
        line = (r.stdout or "").strip().splitlines()[-1] if r.stdout else "{}"
        return json.loads(line)
    except Exception as e:
        return {"ok": False, "error": f"node呼び出し失敗: {e}"}


def open_and_shot(url, shot_name, cdp_port=DEFAULT_CDP_PORT):
    os.makedirs(SHOT_DIR, exist_ok=True)
    shot_path = os.path.join(SHOT_DIR, shot_name)
    result = run_node(["open", str(cdp_port), url, shot_path])
    return result


def imap_connect():
    if not os.path.exists(GMAIL_CRED_PATH):
        return None, "no_credential"
    pw = open(GMAIL_CRED_PATH, encoding="utf-8").read().strip()
    if not pw:
        return None, "empty_credential"
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(GMAIL_ADDR, pw)
        return M, None
    except Exception as e:
        return None, f"login_failed:{e}"


def build_rfc822(to_addr, subject, body):
    msg = email_lib.message.EmailMessage()
    msg["From"] = GMAIL_ADDR
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


def save_gmail_draft(to_addr, subject, body):
    """IMAP APPENDでGmailの下書きフォルダへ直接保存する。ブラウザ・ログイン状態に依存しない
    最も確実な経路。認証情報が無ければ (False, 理由) を返すだけで例外を投げない。"""
    M, err = imap_connect()
    if err:
        return False, err
    try:
        raw = build_rfc822(to_addr, subject, body)
        # Gmailの下書きフォルダはロケール非依存のXLISTだと [Gmail]/Drafts が一般的
        typ, _ = M.append('"[Gmail]/Drafts"', r"(\Draft)", imaplib.Time2Internaldate(datetime.now().timestamp()), raw)
        M.logout()
        if typ == "OK":
            return True, None
        return False, f"append_failed:{typ}"
    except Exception as e:
        try:
            M.logout()
        except Exception:
            pass
        return False, str(e)


def gmail_compose_url(to_addr, subject, body):
    from urllib.parse import quote

    return (
        "https://mail.google.com/mail/u/0/?view=cm&fs=1&tf=cm"
        f"&to={quote(to_addr)}&su={quote(subject)}&body={quote(body)}"
    )


def build_message(target_key, info, subject_ja, body_ja, subject_en, body_en):
    country = info.get("country", "domestic")
    if country == "overseas":
        if not subject_en or not body_en:
            print(
                f"エラー: {target_key} は海外窓口(country=overseas)です。"
                " --subject-en と --body-en の両方が必須です（英日セットが憲法）。",
                file=sys.stderr,
            )
            sys.exit(2)
        subject = f"{subject_en} / {subject_ja}"
        body = f"{body_en}\n\n----------\n\n{body_ja}"
    else:
        subject = subject_ja
        body = body_ja
    return subject, body


def cmd_send(args):
    target_key, info = find_target(args.target)
    if not info:
        print(
            f"窓口不明: 「{args.target}」は status/renraku_madoguchi.json に登録がありません。"
            " 先に窓口を調べて1件追記してから呼んでください（二度と同じ調べ物をしないため、"
            " 調べたら必ずここへ貯める）。",
            file=sys.stderr,
        )
        sys.exit(1)

    body_ja = args.body_ja
    if args.body_file:
        body_ja = open(args.body_file, encoding="utf-8").read()

    subject, body = build_message(
        target_key, info, args.subject, body_ja, args.subject_en, args.body_en
    )

    ts = datetime.now(JST).strftime("%Y%m%d-%H%M%S")
    record = {
        "id": f"{target_key}-{ts}",
        "to": target_key,
        "to_label": info.get("aliases", [target_key])[0],
        "type": info.get("type"),
        "subject": subject,
        "body": body,
        "sent_at": now_iso(),
        "reply_received": False,
        "reply_text": None,
        "reply_checked_at": None,
        "screenshots": [],
        "notes": [],
    }

    if args.dry_run:
        record["notes"].append("dry-run: 実際には何も開いていない")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    if info.get("type") == "email":
        to_addr = info["email"]
        ok, err = save_gmail_draft(to_addr, subject, body)
        if ok:
            record["notes"].append("Gmail下書きフォルダへ直接保存成功（IMAP APPEND）")
        else:
            record["notes"].append(f"Gmail下書き直接保存はスキップ/失敗: {err}")
        url = gmail_compose_url(to_addr, subject, body)
        # 「押すだけ」の本体はこのURL自体。たまごさん本人のログイン済みブラウザでこのリンクを
        # 開けば to/subject/body が自動で入った下書き作成画面になる（Gmail公式のURL仕様）。
        # 自動化用Chrome(~/.tamago/chrome-line)は896番2回目時点でGoogle未ログインのため、
        # そちらで開いたスクショは「実際にどう見えるか」の証拠にならない（未ログイン広告ページになる）。
        # そのため compose_url を記録に残し、確認ページ側でクリック可能なリンクとして提示する方式へ変更。
        record["compose_url"] = url
        shot_name = f"{record['id']}-gmail.png"
        cdp_port = info.get("cdp_port", DEFAULT_CDP_PORT)
        res = open_and_shot(url, shot_name, cdp_port)
        if res.get("ok"):
            record["screenshots"].append(f"share/check/renraku/{shot_name}")
            record["notes"].append("参考: 自動化用Chrome(未ログイン)でも開けることは確認したが、ログイン未済のため広告/ログイン画面が写るだけで文面反映の証拠にはならない。本番の「押すだけ」はcompose_urlをたまごさん本人のログイン済みブラウザで開く経路")
        else:
            record["notes"].append(f"ブラウザでの表示確認は失敗: {res.get('error')}")

    elif info.get("type") == "webform":
        url = info["url"]
        shot_name = f"{record['id']}-form.png"
        cdp_port = info.get("cdp_port", DEFAULT_CDP_PORT)
        res = open_and_shot(url, shot_name, cdp_port)
        if res.get("ok"):
            tab_id = res.get("tabId")
            record["_tab_id"] = tab_id
            record["_cdp_port"] = cdp_port
            # ログイン画面等をスキップするボタンがmadoguchiに登録されていればクリックする
            post_click = info.get("post_open_click")
            if post_click and tab_id:
                click_res = run_node(["click", str(cdp_port), tab_id, post_click])
                if click_res.get("ok") and click_res.get("clicked"):
                    record["notes"].append(f"「{post_click}」をクリックしてフォーム本体へ到達")
                else:
                    record["notes"].append(f"「{post_click}」のクリックに失敗: {click_res}")

            # 返信用メールアドレス欄・自由記述本文欄がmadoguchiに登録されていれば自動入力する
            # （896番2回目：これが無いとフォームを開いただけで本文欄が空欄のまま止まっていた）
            email_selector = info.get("email_selector")
            if email_selector and tab_id:
                email_b64 = base64.b64encode(GMAIL_ADDR.encode("utf-8")).decode("ascii")
                fill_res = run_node(["fill", str(cdp_port), tab_id, email_selector, email_b64])
                if fill_res.get("ok") and fill_res.get("filled"):
                    record["notes"].append("返信用メールアドレス欄を自動入力済み")
                else:
                    record["notes"].append(f"メールアドレス欄の自動入力に失敗: {fill_res}")

            body_selector = info.get("body_selector")
            if body_selector and tab_id:
                body_b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
                fill_res = run_node(["fill", str(cdp_port), tab_id, body_selector, body_b64])
                if fill_res.get("ok") and fill_res.get("filled"):
                    record["notes"].append("自由記述の本文欄を自動入力済み（「カテゴリ」「詳細」の選択だけ手動で残る。選択後に本文欄が画面に現れる）")
                else:
                    record["notes"].append(f"本文欄の自動入力に失敗: {fill_res}")

            if tab_id:
                shot_name2 = f"{record['id']}-form-filled.png"
                shot_path2 = os.path.join(SHOT_DIR, shot_name2)
                run_node(["shot", str(cdp_port), tab_id, shot_path2])
                record["screenshots"].append(f"share/check/renraku/{shot_name2}")
            else:
                record["screenshots"].append(f"share/check/renraku/{shot_name}")
            record["notes"].append("フォームを開いてスクショ済み。カテゴリ等のカスタムselectはサービス固有のUIのため選択だけ手動で残る")
        else:
            record["notes"].append(f"フォームを開けなかった: {res.get('error')}")
    else:
        record["notes"].append(f"未対応のtype: {info.get('type')}")

    data = load_json(RECORD_PATH, {"sent": []})
    data.setdefault("sent", []).append(record)
    save_json(RECORD_PATH, data)
    print(json.dumps(record, ensure_ascii=False, indent=2))


def cmd_list(args):
    madoguchi = load_madoguchi()
    for key, info in madoguchi.items():
        if key.startswith("_"):
            continue
        print(f"{key}: type={info.get('type')} country={info.get('country')} "
              f"target={info.get('email') or info.get('url')}")


def decode_hdr(s):
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


def append_dispatch(n, title, message, extra=None):
    """891番：見張りの結果をDispatchへ届ける唯一の口。要約せず全文をそのまま入れること。"""
    row = {
        "ts": now_iso(),
        "n": n,
        "type": "renraku_check",
        "title": title,
        "message": message,
    }
    if extra:
        row.update(extra)
    try:
        with open(DISPATCH_OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _check_state():
    return load_json(CHECK_STATE_PATH, {})


def _save_check_state(st):
    save_json(CHECK_STATE_PATH, st)


def cmd_check(args):
    """既に送った(reply_received=false)相手について、Gmailで新着を探す。
    926番check_line_reply.py / check_anthropic_reply.pyと同じ骨組みを汎用化。

    891番：毎日（朝・夜の2回想定）の見張り。heartbeatから15秒おきに呼ばれても、
    実際にIMAPへ繋ぐのはCHECK_INTERVAL_HOURSで間引く（--forceで手動テスト時は無視）。
    新着・2週間未着・認証情報なしは、それぞれ1回だけdispatch_outboxへ全文で通知する
    （要約しない。都合よく解釈しない、原文のまま渡す、というたまごさんの指示のため）。"""
    st = _check_state()
    force = getattr(args, "force", False)
    if not force:
        last = st.get("lastCheckedAt")
        if last:
            try:
                if datetime.now(JST) - datetime.fromisoformat(last) < timedelta(hours=CHECK_INTERVAL_HOURS):
                    return
            except Exception:
                pass
    st["lastCheckedAt"] = now_iso()
    _save_check_state(st)

    data = load_json(RECORD_PATH, {"sent": []})
    madoguchi = load_madoguchi()
    pending = [r for r in data.get("sent", []) if not r.get("reply_received")]
    if not pending:
        print("チェック対象なし（全件返信済み、または送信記録が無い）")
        return

    M, err = imap_connect()
    if err:
        print(f"Gmail接続不可: {err}（~/.tamago/gmail_app_password 未設置。設置され次第このコマンドが自動で動く）")
        if not st.get("credentialMissingNotified"):
            append_dispatch(
                891,
                "【毎日】メールの見張り（LINEの返事待ち）",
                (
                    "見張りの仕組みは実装済みですが、Gmail接続用のアプリパスワードが未設置のため動けません。\n"
                    f"設置先: {GMAIL_CRED_PATH}（1行だけ、パスワード文字列そのものを書く）\n"
                    "設置され次第、次の見回り（最大10時間以内）で自動的に動き出します。"
                ),
                extra={"blocked": "no_credential", "credPathExpected": GMAIL_CRED_PATH},
            )
            st["credentialMissingNotified"] = True
            _save_check_state(st)
        return
    else:
        if st.get("credentialMissingNotified"):
            st["credentialMissingNotified"] = False
            _save_check_state(st)

    changed = False
    for rec in pending:
        info = madoguchi.get(rec["to"], {})
        domains = info.get("reply_from_domains") or (
            [info["email"].split("@")[-1]] if info.get("type") == "email" else []
        )
        if not domains:
            continue
        try:
            M.select("INBOX", readonly=True)
            uids = set()
            sent_date = datetime.fromisoformat(rec["sent_at"]).strftime("%d-%b-%Y")
            for dom in domains:
                typ, d = M.search(None, f'(FROM "{dom}" SINCE {sent_date})')
                if typ == "OK" and d and d[0]:
                    uids.update(d[0].split())
            if not uids:
                continue
            latest = sorted(uids, key=lambda x: int(x))[-1]
            typ, hdata = M.fetch(latest, "(BODY.PEEK[])")
            if typ != "OK" or not hdata or not hdata[0]:
                continue
            msg = email_lib.message_from_bytes(hdata[0][1])
            rec["reply_received"] = True
            rec["reply_text"] = get_body_text(msg).strip()
            rec["reply_subject"] = decode_hdr(msg.get("Subject", ""))
            rec["reply_from"] = decode_hdr(msg.get("From", ""))
            rec["reply_checked_at"] = now_iso()
            changed = True
            print(f"新着あり: {rec['to']} ← {rec['reply_from']}")
            is_en = all(ord(c) < 128 for c in rec["reply_text"][:200]) if rec["reply_text"] else False
            note = "（英文の可能性があります。日本語訳を添えて伝えてください）\n\n" if is_en else ""
            append_dispatch(
                891,
                f"【返信あり】{info.get('aliases', [rec['to']])[0] if info.get('aliases') else rec['to']} から返信が来ました",
                (
                    f"差出人: {rec['reply_from']}\n"
                    f"件名: {rec.get('reply_subject','')}\n"
                    f"日時: {rec['reply_checked_at']}\n"
                    f"{note}"
                    "---本文（原文そのまま。要約なし）---\n"
                    f"{rec['reply_text']}"
                ),
                extra={"to": rec["to"], "toLabel": rec.get("to_label", rec["to"])},
            )
        except Exception as e:
            print(f"{rec['to']} のチェックでエラー: {e}")
        finally:
            rec["reply_checked_at"] = now_iso()
            changed = True

    try:
        M.logout()
    except Exception:
        pass

    if changed:
        save_json(RECORD_PATH, data)

    # 2週間未着の分は1回だけ報告する（is_stale_reportedフラグで多重報告を防ぐ）
    for rec in pending:
        if rec.get("reply_received") or rec.get("stale_reported"):
            continue
        sent_dt = datetime.fromisoformat(rec["sent_at"])
        if datetime.now(JST) - sent_dt > timedelta(days=STALE_DAYS):
            print(f"未着報告(1回のみ): {rec['to']} は{STALE_DAYS}日経っても返信が来ていません")
            append_dispatch(
                891,
                f"【未着・{STALE_DAYS}日経過】{rec.get('to_label', rec['to'])} から返信が来ていません",
                (
                    f"送信日時: {rec['sent_at']}\n"
                    f"件名: {rec.get('subject','')}\n"
                    f"{STALE_DAYS}日経っても返信が来ていません（この通知は1回のみ）。"
                ),
                extra={"to": rec["to"], "toLabel": rec.get("to_label", rec["to"])},
            )
            rec["stale_reported"] = True
            save_json(RECORD_PATH, data)


def main():
    p = argparse.ArgumentParser(description="896番: 外部連絡いっぱつ")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("send", help="窓口台帳の相手へ、文面を作って送信ボタン手前まで開く")
    sp.add_argument("target", help="窓口台帳のキーまたはエイリアス")
    sp.add_argument("--subject", required=True, help="件名(日本語)")
    sp.add_argument("--body-ja", default="", help="本文(日本語)")
    sp.add_argument("--body-file", default=None, help="本文(日本語)をファイルから読む場合のパス")
    sp.add_argument("--subject-en", default=None, help="件名(英語)。海外窓口は必須")
    sp.add_argument("--body-en", default=None, help="本文(英語)。海外窓口は必須")
    sp.add_argument("--dry-run", action="store_true", help="ブラウザを開かず記録もしない（確認用）")
    sp.set_defaults(func=cmd_send)

    lp = sub.add_parser("list", help="窓口台帳を表示")
    lp.set_defaults(func=cmd_list)

    cp = sub.add_parser("check", help="返信が来ていないか確認する（heartbeatから頻繁に呼ばれても内部で1日2回程度に間引く）")
    cp.add_argument("--force", action="store_true", help="間引きを無視して今すぐ確認する（動作確認用）")
    cp.set_defaults(func=cmd_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
