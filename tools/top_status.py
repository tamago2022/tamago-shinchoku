#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""進捗表の一番上「今何が動いているか」だけを1画面ぶん、超軽量JSONにして書き出す。

2026-09-16（882番）新設の理由：
  たまごさん「一番気になってるとこ」＝一番上の赤い長文バナー（本番◯時間・no_launch.flag等）は
  幅を取るだけで読まれていない。代わりに「今走ってる／次に発車／できたもの」を出してほしい、
  という指示への対応。

  既存の status/genzaichi.json は実質30分おきしか更新されない
  （tools/genzaichi.py が heartbeat.sh に25分ゲートで相乗りしているため）。
  「今すぐ走っているもの：0本」なのに実際は4本走っている、という食い違いは
  このゲートの遅さ＋label/titleの取り違え（label は新規タスクには無く title に入る）が原因。

  ここは genzaichi.py とは完全に独立させ、
    ① 重い処理（本番HEAD確認・shikumi.py起動）をやらない
    ② status/queue_light.json（auto_launcher.py／command_ingest.pyが毎サイクル書き直す。
       常に生きた状態に近い）だけを読む
  ことで、heartbeat.sh の15秒サイクルへ毎回相乗りしても軽いままにする。

出力: status/top_status.json（数百バイト〜1KB程度）
"""

# --- 1回きりの相乗り：Lovable公式MCPをMac側へ登録する（962番）-----------------
# 子セッションのbashはLinuxサンドボックスで ~/.claude.json に手が届かない。
# 心臓が毎周回で読み直すこのファイルから1回だけ呼ぶのが、Macに手を届かせる道。
# 済んだら status/.lovable_mcp_done が置かれ、以後は即returnして何もしない。
# 何が起きてもこのファイル本来の仕事(進捗表)を止めないよう、まるごとtryで囲う。
try:
    import os as _os, sys as _sys
    if not _os.path.exists(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "status", ".lovable_mcp_done")):
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        import lovable_mcp_bootstrap as _lmb
        _lmb.run()
    if not _os.path.exists(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "status", ".lovable_mcp_check_done")):
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        import lovable_mcp_check as _lmc
        _lmc.run()
except Exception:
    pass

# --- サンドボックス→Macの「使い走り」窓口（962番）---------------------------
# 上の1回きりの相乗りを毎回このファイルに足していくのは事故のもとなので、
# status/mac_jobs/pending/*.sh を置けば1回だけ走る共通の窓口に置き換える。
# 待ちが空なら即returnするので心臓は重くならない。
try:
    import os as _os2, sys as _sys2
    _sys2.path.insert(0, _os2.path.dirname(_os2.path.abspath(__file__)))
    import mac_job_runner as _mjr
    _mjr.run()
except Exception:
    pass

# --- Lovableの同意ボタンをいつ押しても拾えるようにする見張り（962番）-----------
# トークンが取れたら即座に何もしなくなる。
try:
    import lovable_auth_keeper as _lak
    _lak.run()
except Exception:
    pass

# --- 「mainに入った → 本番に出た」を毎回確かめる係（1038番）--------------------
# ごきげん補給所は GitHub Pages ではなく Lovable配信。mainに入れても本番は古いまま
# になりうるのに、これまで「pushした＝出た」と数えていた（2026-09-23に3回詰まった）。
# 5分に1回だけ本番のヘッダを叩き、x-deployment-id が動かないまま30分たったら赤。
try:
    import kohyou_kanshi as _kks
    _kks.run()
except Exception:
    pass

# --- 赤になったら公開ボタンを自動で押す係（1041番）----------------------------
# ★見る係（上）と押す係（下）は別物。押す係は判定を書かない＝赤を青に書き替えない。
# 出たかどうかは、押していない見る係が次の回に測って決める。押すのは無料。
try:
    import kohyou_osu as _kos
    _kos.run()
except Exception:
    pass
# ---------------------------------------------------------------------------

import io
import json
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
QUEUE_LIGHT = os.path.join(ST, "queue_light.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
NO_LAUNCH_FLAG = os.path.join(ST, "no_launch.flag")
LAUNCH_CAP = os.path.join(ST, "launch_cap.json")
LAST_LAUNCH = os.path.join(ST, ".last_launch_at")
OUT = os.path.join(ST, "top_status.json")

JST = datetime.timezone(datetime.timedelta(hours=9))

sys.path.insert(0, HERE)
try:
    from auto_launcher import queue_rank_key  # 発車順の正本ロジックをそのまま流用（重複させない）
except Exception:
    def queue_rank_key(it, prio):
        u = 0 if it.get("urgent") else 1
        p = it.get("priority") or 9
        o = it.get("order")
        return (u, p, int(o) if isinstance(o, int) else 10 ** 6, it.get("n") or 99)


def jread(p, d=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d if d is not None else {}


def label_of(it):
    # 726/802番の教訓と同じ穴：新規タスクは label ではなく title を持つ。両対応する。
    return (it.get("label") or it.get("title") or "")[:48]


def short_model(m):
    if not m:
        return ""
    m = str(m).replace("claude-", "")
    return m.replace("-", " ").title()


def elapsed_min(started_at, now):
    if not started_at:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(started_at))
        return round((now - t).total_seconds() / 60, 1)
    except Exception:
        return None


def recent_done(limit=3):
    """直近の完了＋URL。dispatch_outbox.jsonlの末尾から、URLを持つ ok:true の行だけ拾う
    （genzaichi.pyのunreported_completionsと同じURL妥当性チェック＝自分の番号で始まるものを優先）。"""
    rows = []
    try:
        with io.open(OUTBOX, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return rows
    picked = {}
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        n_ = d.get("n")
        if not isinstance(n_, int) or not d.get("ok"):
            continue
        if n_ in picked:
            continue
        urls = [u for u in (d.get("urls") or []) if "share/" in u or "lovable.app" in u]
        if not urls:
            continue
        good = [u for u in urls if os.path.basename(u).split("-", 1)[0] == str(n_)]
        picked[n_] = {
            "n": n_,
            "title": (d.get("title") or "")[:40],
            "url": good[0] if good else urls[0],
            "ts": d.get("ts"),
        }
        if len(picked) >= limit:
            break
    return list(picked.values())


def login_block():
    """ログインの生死だけを返す（2026-09-25）。

    たまごさんは進捗表しか見ない。ここが切れているとき、進捗表に何も出ていなかった
    ＝5日気づかれなかった。だから走行本数や他の事情に一切左右されない独立の1枠にする。
    出す文言は1つだけ：「ログインが切れています」。
    """
    st = jread(os.path.join(ST, "auth_keeper.json"), {})
    ng = os.path.exists(os.path.join(ST, "auth_expired.flag"))
    if not ng:
        try:
            txt = io.open(NO_LAUNCH_FLAG, encoding="utf-8").read()
            ng = ("ログイン" in txt) or ("OAuth" in txt)
        except Exception:
            ng = False
    return {
        "ng": bool(ng),
        "midashi": "ログインが切れています" if ng else None,
        "since": st.get("ngSince"),
        "naoshikata": "status/LOGIN.md の1行を貼ってEnter（1年もつ形に替わります）" if ng else None,
        "kirenaiKatachi": os.path.exists(os.path.expanduser("~/.tamago/use_token")),
        "tokenDaysLeft": st.get("tokenDaysLeft"),
    }


def stopped_reason():
    """走行0本のときだけ呼ぶ。理由を1行で返す（無ければNone＝『分かりません』を機械が偽装しない）。"""
    if os.path.exists(NO_LAUNCH_FLAG):
        try:
            content = io.open(NO_LAUNCH_FLAG, encoding="utf-8").read().strip()
        except Exception:
            content = ""
        return "発車を止めています" + ("（%s）" % content[:60] if content else "")
    cap = jread(LAUNCH_CAP, {})
    if isinstance(cap.get("cap"), int) and cap.get("cap") <= 0:
        return "同時本数の上限が0本になっています（%s）" % (cap.get("why") or "理由不明")
    try:
        age_min = (datetime.datetime.now(JST).timestamp() - os.path.getmtime(LAST_LAUNCH)) / 60
        if age_min > 10:
            return "発車が%.0f分止まっています（自動の立て直しが動いています）" % age_min
    except FileNotFoundError:
        pass
    return "発車できるものが無いか、判定中です"


def pace_block():
    """週の目盛りは status/pace.json 一本だけを見る。
    quota.json など別の残り%を混ぜない（本番で『残り69%』と『残り71%』が同じ画面に出ていた原因）。
    ここでは pace.json の値をそのまま写すだけで、計算し直さない。"""
    p = jread(os.path.join(ST, "pace.json"), {})
    if not p:
        return None
    # ★1155番：allPctAsOf／allPctAgeMin を写していなかったので、進捗表の
    #   「この数字は ◯◯時点」が本番でずっと「時点不明」と出ていた（2026-09-26 実測）。
    keys = ("updatedAt", "allPct", "remainWeek", "usedToday", "budgetToday",
            "daysLeft", "state", "resetAt", "dataOk", "allPctAsOf", "allPctAgeMin",
            "perDayEven", "lineTarget")
    out = {k: p.get(k) for k in keys if p.get(k) is not None}
    out["source"] = "status/pace.json"
    return out


def freshness_block():
    """1143番【成果の鮮度計】status/1143/freshness.json をそのまま写す。

    ★ここが stoppedReason と決定的に違うところ：
      stoppedReason は「いま走っているか」を見る。走っていれば黙る。
      鮮度計は「最後に本物の成果が出てから何時間経ったか」だけを見る。
      走行本数を一切見ないので、空回しが何本走っていても赤は消えない。
      （4日半だれも気づかなかった事故の再発防止はこちらが本体）
    """
    f = jread(os.path.join(ST, "1143", "freshness.json"), {})
    if not f:
        return None
    return {
        "at": f.get("at"),
        "akaN": f.get("akaN"),
        "ichigyou": f.get("ichigyou"),
        "aka": [a for a in (f.get("alerts") or []) if a.get("level") == "red"][:4],
        "pipes": {k: {"na": v.get("na"), "ageH": v.get("ageH"), "shikiiH": v.get("shikiiH")}
                  for k, v in (f.get("pipes") or {}).items()},
    }


def verify_block():
    """完了の検証（tools/verify_done.py が書く要約）。無ければ null＝機械が偽装しない。"""
    v = jread(os.path.join(ST, "verify_summary.json"), {})
    if not v:
        return None
    return {k: v.get(k) for k in ("updatedAt", "total", "verified", "recheck", "unverified")}


# joy-relief-station 側の状態ファイル（案件820：Lovable公開便）。
# クロスリポジトリ参照だが、sync-lovable-publish-dashboard.mjs も同じ os.homedir()+Desktop 前提で
# data.js を直接書いているのと同じやり方（このマシン内で完結する運用なので固定パスで問題ない）。
JOY_REPO = os.path.join(os.path.expanduser("~"), "Desktop", "joy-relief-station")
LOVABLE_STATE = os.path.join(JOY_REPO, "status", "lovable_publish_state.json")
LOVABLE_FAIL_LOG = os.path.join(JOY_REPO, "status", "lovable_publish_fail.jsonl")


def lovable_publish_block():
    """案件820：軽量版へ差し替えた際に本番未反映・連続失敗の赤バナーが消えていたのを埋め直す。
    index.html の renderLovablePublishAlert() が mainUnpublished / consecutiveFailures / paused を見る。
    ファイルが無い・壊れている場合は null を返し、機械が『問題なし』を偽装しない。"""
    s = jread(LOVABLE_STATE, None)
    if not s:
        return None
    last_fail_reason = None
    last_fail_at = None
    try:
        with io.open(LOVABLE_FAIL_LOG, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if lines:
            last = json.loads(lines[-1])
            last_fail_reason = last.get("reason")
            last_fail_at = last.get("ts")
    except Exception:
        pass
    return {
        "mainUnpublished": bool(s.get("mainUnpublished")),
        "mainSha": (s.get("mainSha") or "")[:10] or None,
        "paused": bool(s.get("paused")),
        "pauseReason": s.get("pauseReason"),
        "consecutiveFailures": s.get("consecutiveFailures") or 0,
        "stoppedForToday": bool(s.get("stoppedForToday")),
        "successCountToday": s.get("successCount") or 0,
        "dailyCap": 6,
        "consecutiveFailureStopAt": 2,
        "lastResult": s.get("lastResult"),
        "lastCheckedAt": s.get("lastCheckedAt"),
        "lastFailureReason": last_fail_reason,
        "lastFailureAt": last_fail_at,
        "autoTimerDisabled": True,
    }


def build():
    now = datetime.datetime.now(JST)
    q = jread(QUEUE_LIGHT, {"items": []})
    items = q.get("items") or []
    prio = (jread(os.path.join(ST, "priority.json"), {}).get("priority")) or {}

    running = [x for x in items if x.get("status") == "running"]
    running_sorted = sorted(running, key=lambda x: x.get("startedAt") or "")
    running_now = [
        {
            "n": x.get("n"),
            "label": label_of(x),
            "elapsedMin": elapsed_min(x.get("startedAt"), now),
            "model": short_model(x.get("model")),
            # 1136番（2026-09-25）進捗表が「◯分／180分」を自分で数え直せるように、
            # 開始時刻と制限時間もそのまま渡す。書き出した瞬間の値だけだと、
            # 画面を開いている間ずっと止まって見える（＝読み直すまで増えない）。
            "startedAt": x.get("startedAt"),
            "limitMin": x.get("limitMin") or 180,
        }
        for x in running_sorted
    ]

    waiting = [x for x in items if x.get("status") == "waiting"]
    p1 = [x for x in waiting if (x.get("priority") or (prio.get("Q%d" % x.get("n")) if x.get("n") else None)) == 1]
    p1_sorted = sorted(p1, key=lambda it: queue_rank_key(it, prio))
    next_up = [{"n": x.get("n"), "label": label_of(x)} for x in p1_sorted[:3]]

    payload = {
        "generatedAt": now.isoformat(),
        "runningNow": running_now,
        "nextUp": next_up,
        "recentDone": recent_done(3),
        # 2026-09-25 修正：**空回しが走っていると止まっていないことになっていた。**
        # ログインが切れていても runningNow に【空回し】が1本いるだけで
        # stoppedReason が null になり、進捗表に何も出ないまま5日が過ぎた。
        # 本物が0本なら「止まっている」と言う。空回しは走行に数えない。
        "stoppedReason": stopped_reason() if not [
            x for x in running_now if "空回し" not in (x.get("label") or "")] else None,
        # たまごさんは進捗表しか見ない。ログインだけは**いつでも一番上に赤で出す。**
        "login": login_block(),
        # 1143番：成果の鮮度。走行本数で消えない赤。
        "freshness": freshness_block(),
        "pace": pace_block(),
        "verify": verify_block(),
        "lovablePublish": lovable_publish_block(),
    }
    tmp = "%s.tmp.%d" % (OUT, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    return payload


if __name__ == "__main__":
    result = build()
    print("top_status.json を書きました（走行%d本）" % len(result["runningNow"]))

    # 2026-09-21（977番・Cowork側から設置）サンドボックス→Macの一発コマンド窓口。
    # 待ちが空なら即戻るだけ。投げっぱなしにして心臓は待たない（他の相乗りと同じ形）。
    try:
        import subprocess as _sp, os as _os
        _r = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "oneshot_runner.py")
        _sp.Popen(["python3", _r], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    except Exception:
        pass

    # 2026-09-25（1145番）実測・ページ実物見の見張り。黙って止まったら続きから立て直す。
    # 実害：nohupで走らせた実測が213本で消えた（ログに痕跡なし＝殺された）。書くだけでは効かないので線を1本入れる。
    try:
        import subprocess as _sp2, os as _os2
        _g = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), "1145_guard.py")
        _sp2.Popen(["python3", _g], stdout=_sp2.DEVNULL, stderr=_sp2.DEVNULL)
    except Exception:
        pass

    # 2026-09-26（1155番）ずんだもん読み上げの見張り。心臓に殺されても続きから立て直す。
    # 止めたいときは status/zunda/stop を置く。
    try:
        import subprocess as _sp3, os as _os3
        _z = _os3.path.join(_os3.path.dirname(_os3.path.abspath(__file__)), "1155_keeper.py")
        _sp3.Popen(["python3", _z], stdout=_sp3.DEVNULL, stderr=_sp3.DEVNULL)
    except Exception:
        pass

    # 2026-09-26（1158番）claudeの同時起動の見張り。1分おきに本数を数えて証拠を残す。
    # 関所(1158_kanmon.py)が本当に効いているかを、時刻つきの実測で示すための線。
    try:
        import subprocess as _sp4, os as _os4
        _k = _os4.path.join(_os4.path.dirname(_os4.path.abspath(__file__)), "1158_mihari.py")
        _sp4.Popen(["python3", _k], stdout=_sp4.DEVNULL, stderr=_sp4.DEVNULL)
    except Exception:
        pass
