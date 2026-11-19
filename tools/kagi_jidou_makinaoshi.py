#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鍵を切れる前に自分で巻き直す係（1161番の続き）2026-09-27

■ なぜ要るか（実測）
  2026-09-26（1161番）に1年もつ鍵を取り直した。しかし取り直しは**毎回人の手**で、
  しかも 2026-09-27 07:52〜14:35 の見張り10回は全部「混んでいて測れなかった」＝
  **7時間、生死を誰も測っていなかった。**
  ＝「切れたら気づく」も「切れる前に取り直す」も、実際には誰もやっていなかった。

■ この係がやること（穴に段ボールを貼らない。口を1つ作る）
  ① 残り日数を測って status/public/kagi_kigen.json に出す（進捗表の小さい1行の元）
  ② 残り30日を切ったら、**言われる前に** 1161番の取り直しを裏で起動する
     （URLが status/1161_url.txt に出た状態にしておく＝あとは承認を1回押すだけ）
  ③ 起こしたことと「いま押すだけの状態か」を dispatch_outbox.jsonl に1行だけ出す
  ④ 鍵が無い／形が違うときも同じ道で起こす（切れてからでも同じ1本で戻る）

■ 触らないもの
  ・鍵の中身は読まない（長さと先頭の形だけ見る）。ログにも出さない。
  ・use_token は立てない・外さない。それは「実際に1本通った」を見た係の仕事
    （1161_kagi_toru.py / auth_keeper.py）。この係は起こすだけ。
  ・新しい常駐は増やさない。5分便（machine_status_push.sh）に相乗りし、中で1時間ゲートする。
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT = os.path.join(PUBLIC, "kagi_kigen.json")
STATE = os.path.join(STATUS, "kagi_jidou_makinaoshi.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
LOG = os.path.join(STATUS, "auth_keeper.log")   # ログは増やさない。同じ紙に書く
URLF = os.path.join(STATUS, "1161_url.txt")
TORU = os.path.join(HERE, "1161_kagi_toru.py")
TORU_LOCK = os.path.join(STATUS, "1161_toru.lock")

TAMAGO = os.path.expanduser("~/.tamago")
TOKEN = os.path.join(TAMAGO, "claude_token")
MINTED = os.path.join(TAMAGO, "claude_token.minted")
USE = os.path.join(TAMAGO, "use_token")

LIFETIME_DAYS = 365      # setup-token の公称寿命
RENEW_DAYS = 30          # ここを切ったら自分で巻き直しにかかる
GATE_SEC = 3600          # 測るのは1時間に1回
START_COOLDOWN = 6 * 3600   # 取り直しの起動は6時間に1回まで（連打しない）


def log(m):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [巻き直し] %s\n" % (time.strftime("%F %T"), m))
    except Exception:
        pass


def jload(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(
            json.dumps(o, ensure_ascii=False, indent=1))
        os.replace(tmp, p)
    except Exception:
        pass


def minted_at():
    """鍵を作った時刻。分からなければ None（推測で埋めない）。"""
    try:
        s = io.open(MINTED, encoding="utf-8").read().strip()
        try:
            return float(s)
        except ValueError:
            return time.mktime(time.strptime(s[:19], "%Y-%m-%d %H:%M:%S"))
    except Exception:
        try:
            return os.path.getmtime(TOKEN)
        except Exception:
            return None


def token_katachi():
    """鍵の形だけ見る（中身は返さない）。"""
    try:
        t = io.open(TOKEN, encoding="utf-8").read().strip()
    except Exception:
        return "ない", 0
    if not t.startswith("sk-ant-"):
        return "形が違う", len(t)
    if len(t) < 90:
        # 2026-09-26 の実測事故：端末の80桁折り返しで79文字に尻切れした鍵は
        # 保存できるのに叩くと 401 になる。形で先に見つける。
        return "短い（端末の折り返しで尻切れの疑い）", len(t)
    return "ある", len(t)


def hakaru():
    katachi, ln = token_katachi()
    m = minted_at()
    days = None
    expires = None
    if m:
        expires = m + LIFETIME_DAYS * 86400
        days = int((expires - time.time()) // 86400)
    ak = jload(os.path.join(STATUS, "auth_keeper.json"), {}) or {}
    return {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "katachi": katachi,
        "len": ln,
        "useToken": os.path.exists(USE),
        "mintedAt": (time.strftime("%F %T", time.localtime(m)) if m else None),
        "expiresAt": (time.strftime("%F", time.localtime(expires)) if expires else None),
        "daysLeft": days,
        "renewDays": RENEW_DAYS,
        "keeperState": ak.get("state"),
        "keeperLastOkAt": ak.get("lastOkAt"),
    }


def iru(k):
    """巻き直しが必要か。必要なら理由、要らなければ ""。"""
    if k["katachi"] != "ある":
        return "鍵が%s" % k["katachi"]
    if k["daysLeft"] is None:
        return "いつ作った鍵か分からない（期限が読めない）"
    if k["daysLeft"] <= RENEW_DAYS:
        return "残り%d日（%d日を切った）" % (k["daysLeft"], RENEW_DAYS)
    if k["keeperState"] == "expired":
        return "見張りが『通らない』と実測している"
    return ""


def toru_ugoiteiru():
    try:
        return time.time() - os.path.getmtime(TORU_LOCK) < 1800
    except Exception:
        return False


def okosu(why, st):
    """1161番を裏で起こす。承認コードの待ち受けまで向こうが自分でやる。"""
    if toru_ugoiteiru():
        log("取り直しは既に動いている（%s）" % why)
        return False
    if time.time() - float(st.get("lastStartAt") or 0) < START_COOLDOWN:
        return False
    if not os.path.exists(TORU):
        log("取り直しの係が居ない: %s" % TORU)
        return False
    try:
        subprocess.Popen([sys.executable, TORU],
                         cwd=REPO, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        log("起こせなかった（%s）" % type(e).__name__)
        return False
    st["lastStartAt"] = time.time()
    st["lastWhy"] = why
    log("取り直しを起こした（%s）" % why)
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "kagi-jidou-makinaoshi",
                "type": "auth_keeper",
                "title": "Claudeのログイン（自動で巻き直しを始めました）",
                "message": ("🔑 %s ので、鍵の取り直しを自動で始めました。"
                            "1〜5分で status/1161_url.txt にURLが出ます。"
                            "Chromeでそれを開いて「承認」を1回押すだけで終わります"
                            "（押したあとは工場が自分で戻ります）。" % why),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return True


def main():
    st = jload(STATE, {}) or {}
    if time.time() - float(st.get("lastRunAt") or 0) < GATE_SEC and "--force" not in sys.argv:
        return 0
    st["lastRunAt"] = time.time()

    k = hakaru()
    why = iru(k)
    k["renewNeeded"] = bool(why)
    k["renewWhy"] = why or None
    # 「あとは押すだけ」の状態かどうかも進捗表から見えるようにする
    k["machiUrl"] = bool(toru_ugoiteiru() and os.path.exists(URLF))
    jsave(OUT, k)

    if why:
        okosu(why, st)
    jsave(STATE, st)
    print(json.dumps(k, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
