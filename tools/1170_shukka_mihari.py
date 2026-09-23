#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1170番【出荷便の見張り】(2026-09-27)

たまごさん:
  「便が二度と黙って止まらないようにする。止まったら自動で起き直す／
    止まったことが進捗表に出る、のどちらかを入れる。
    『直しました』でなく『もう止まりません』にする。」

■ 何が起きていたか（2026-09-27 実測・証拠つき）
  出荷便 scripts/patrol/push-queue.mjs は launchd の
  com.tamago.joy-relief-station.role-sweep（StartInterval 1800）から
  scripts/roles/sweep-cron.sh 経由で呼ばれている。
  ところが 17:07 / 17:39 / 18:11（JST）の3周が連続で落ちていた：
    fatal: pathspec 'src/lib/trails.ts' did not match any files
    （消すファイルまで git add に渡していたバグ。18:45の周で直って通った）
  ＝ 1時間半のあいだ、荷物は棚に載ったまま1件も本番へ出ていない。
  **その事実がどこにも出ていなかった。** ログは ~/Library/Logs/TamagoRoleSweep/ に
  あり、Cowork（サンドボックス）からは読めない。進捗表にも1行も出なかった。
  だから「止まっている」ことに気づいたのは、たまごさんが本番を見たときだった。

■ 直し方（穴を塞ぐのではなく、信号を1本足す）
  この係は**押し出さない**。押し出す係は既にある（二重実装しない）。
  見るのは2つだけ、どちらもファイルの実測：
    ① 棚に receipt.json の無い依頼が STUCK_SEC 以上ある
    ② _last-run.json（出荷便が走るたび必ず先頭で書く）が SILENT_SEC 以上古い
  どちらかに当たったら、
    A) 進捗表に出す  … status/dispatch_outbox.jsonl へ1行（同じ件で1日1回だけ）
    B) 自動で起き直す … launchctl kickstart で role-sweep を蹴る
                        （新しい常駐・新しいlaunchd便は1本も作らない）
  蹴るのは KICK_MAX 回まで。それ以上は蹴らずに赤だけ出し続ける
  （起きないものを永遠に叩き続けた 09-24 の事故を繰り返さない）。
  青（詰まっていない）ときは1バイトも書かない＝黙っているのが正常の合図。

呼び出し: tools/heartbeat.sh（tick_every 20 ＝ 約5分おき）
出力:     status/1170_shukka.json（進捗表が読む実測）
          status/dispatch_outbox.jsonl（赤のときだけ1行）
"""
import io
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")

JOY = "/Users/mac/Desktop/joy-relief-station"
QUEUE_ROOTS = [
    os.path.join(JOY, ".claude", "push-queue"),
    os.path.join(JOY, "scripts", "patrol", "push-queue-requests"),
]
TRACE = os.path.join(JOY, "scripts", "patrol", "push-queue-requests", "_last-run.json")

OUT = os.path.join(ST, "1170_shukka.json")
PUBLIC = os.path.join(ST, "public", "1170_shukka.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
STATE = os.path.join(ST, "1170_shukka_state.json")

STUCK_SEC = 45 * 60      # 依頼が45分 receipt 無しで棚に残っていたら赤（便は30分おき＝1周ぶんの猶予）
SILENT_SEC = 75 * 60     # 便が75分1度も走っていなければ赤（2周ぶん空振り）
KICK_MAX = 3             # 同じ赤で蹴り直すのは3回まで
SERVICE = "com.tamago.joy-relief-station.role-sweep"


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, obj):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _matteru():
    """receipt.json がまだ無い依頼を、古い順に返す。"""
    out = []
    now = time.time()
    for root in QUEUE_ROOTS:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                continue
            req = os.path.join(d, "request.json")
            if not os.path.exists(req):
                continue
            if os.path.exists(os.path.join(d, "receipt.json")):
                continue
            try:
                age = int(now - os.path.getmtime(req))
            except Exception:
                age = 0
            out.append({"id": name, "machi_sec": age})
    return sorted(out, key=lambda x: -x["machi_sec"])


def _bin_age():
    try:
        t = _load(TRACE, {}).get("started_at")
        if not t:
            return None
        # 例: 2026-09-27T10:19:01.133Z
        ep = time.mktime(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        return int(time.time() - ep)
    except Exception:
        return None


def _keru():
    try:
        uid = os.getuid()
        subprocess.run(["launchctl", "kickstart", "-k", "gui/%d/%s" % (uid, SERVICE)],
                       capture_output=True, timeout=30)
        return True
    except Exception:
        return False


def main():
    machi = _matteru()
    age = _bin_age()
    riyuu = []
    if machi and machi[0]["machi_sec"] >= STUCK_SEC:
        riyuu.append("棚に %s が %d分 残ったままです" %
                     (machi[0]["id"], machi[0]["machi_sec"] // 60))
    if age is not None and age >= SILENT_SEC:
        riyuu.append("出荷便が %d分 1度も走っていません" % (age // 60))
    if age is None:
        riyuu.append("出荷便が走った記録(_last-run.json)がありません")

    akai = bool(riyuu)
    ima = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "akai": akai,
        "machi": machi[:5],
        "bin_age_sec": age,
        "riyuu": riyuu,
    }
    _save(OUT, ima)
    _save(PUBLIC, ima)

    st = _load(STATE, {})
    key = "|".join(riyuu)
    if not akai:
        # 青に戻ったら数え直す（次に詰まったときはまた3回蹴れる）
        if st.get("key"):
            _save(STATE, {})
        return

    if st.get("key") != key:
        st = {"key": key, "kick": 0, "shirase": ""}

    # A) 自動で起き直す
    if st["kick"] < KICK_MAX:
        st["kick"] += 1
        st["kicked_at"] = time.strftime("%F %T")
        _keru()

    # B) 進捗表に出す（同じ件は1日1回だけ）
    kyou = time.strftime("%F")
    if st.get("shirase") != kyou:
        st["shirase"] = kyou
        try:
            os.makedirs(ST, exist_ok=True)
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                    "n": "1170-shukka-mihari",
                    "type": "shukka_tomatta",
                    "title": "出荷便（push-queue）が止まっています",
                    "message": "／".join(riyuu) +
                               "｜role-sweep を蹴り直しました（%d/%d回目）。"
                               "それでも動かない場合はログ "
                               "~/Library/Logs/TamagoRoleSweep/push-queue.log を見ること。"
                               % (st["kick"], KICK_MAX),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
    _save(STATE, st)


if __name__ == "__main__":
    main()
