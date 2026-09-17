#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
799番（2026-09-14）仕組みの生死表。

たまごさんの言葉：「作った仕組みが本当に動いているか誰も測っていない」。
鬼監督が7日間waitingのまま動いていなかった等、6つの事故が全部たまごさん自身に見つかっている
（鬼監督waiting放置・検品担当のブラウザ使用禁止不整合・Lovable停止5日・発車0本2.5時間・
週の目盛り3種類不一致・進捗表5秒再描画）。

このスクリプトは、**AIを呼ばず、既存のログ／JSONファイルを読んで数えるだけ**（0円）で、
主要な自動化の仕組みが実際に動いているかを判定する。新しい常駐プロセス（launchd等）は
一切追加しない。既存の `tools/genzaichi.py`（heartbeat.shに相乗りし実質30分おきに動く）が、
このスクリプトをsubprocessで呼ぶことで定期実行を実現する（genzaichi.py側の改修を参照）。

書くもの：
  status/shikumi.json               … 11項目の生死判定（このファイル自身が正本）
  status/shikumi_waiting_since.json … waitingが「いつから」続いているかの自前台帳
                                       （queue.json自体にはcreatedAt/updatedAt等の時刻フィールドが
                                        個々のitemに無いため、これが無いと「24時間放置」を判定できない）
  status/self_repair_log.jsonl      … dead判定 → 自動でタスクを積んだ／重複でスキップした記録
  status/self_repair_weekly.json    … 「自分で見つけた数」vs「たまごさんに言われた数」の週次集計
  status/owner_pointed_log.jsonl    … 「たまごさんに言われた数」のログ（初回だけこのスクリプトが
                                       799番着手時点の6件をシードする。以後は tools/owner_redo.py が
                                       やり直し成功のたびに追記する）

判定の考え方（項目ごとに性質が違うので閾値も変える。一律10分ルールにすると誤検知する）：
  - 心臓・発車のように「常時動いているはず」のものは分単位（10分/30分）で厳しく見る。
  - 鬼監督・憲法点検・AI検品・Lovable公開のように「完了のたび／1日1回」のイベント駆動のものは
    時間単位（24時間/48時間）で見る。鬼監督は二値（alive/dead）とし、途中の"slow"帯は設けない
    （きっかり24時間で切り替わる程度の粒度で十分。分単位で見ると誤検知する）。
  - 費用台帳は「支出が無い日は更新されなくて正常」なので週〜2週間単位のさらに緩い閾値にする。

実行:
  python3 tools/shikumi.py             # 点検してstatus/shikumi.jsonを書く（dead項目は自動でタスクを積む）
  python3 tools/shikumi.py --no-queue  # 赤が出てもタスクを積まない（動作確認用）
"""
import argparse
import datetime
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

JST = datetime.timezone(datetime.timedelta(hours=9))

SHIKUMI_OUT = os.path.join(ST, "shikumi.json")
WAITING_SINCE = os.path.join(ST, "shikumi_waiting_since.json")
SELF_REPAIR_LOG = os.path.join(ST, "self_repair_log.jsonl")
SELF_REPAIR_WEEKLY = os.path.join(ST, "self_repair_weekly.json")
OWNER_POINTED_LOG = os.path.join(ST, "owner_pointed_log.jsonl")

# 799番着手時点（2026-09-14）でたまごさんから直接指摘された今週の実例6件。
# owner_pointed_log.jsonlが一度も無い（＝このスクリプトを初めて動かす）時だけ、
# この6件を今日の日付でシードする。以後の追記は tools/owner_redo.py が担当する。
OWNER_POINTED_SEED = [
    "鬼監督がwaitingのまま7日間動いていなかった",
    "検品担当のブラウザ使用禁止ルールと実際の運用が不整合だった",
    "Lovable本番が5日間止まっていた",
    "発車が0本のまま2.5時間止まっていた",
    "週の目盛りが3種類あって数字が一致していなかった",
    "進捗表が5秒おきに再描画されていた",
]


def now_jst():
    return datetime.datetime.now(JST)


def jread(name, default=None):
    try:
        with open(os.path.join(ST, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def jwrite(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def parse_ts(s):
    """ISO(+tzあり/なし)・'%Y-%m-%d %H:%M[:%S]' のどちらでも読む。読めなければNone（でっち上げない）。"""
    if not s:
        return None
    s = str(s).strip()
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.replace(tzinfo=JST)
        except Exception:
            continue
    return None


def hours_since(ts):
    dt = parse_ts(ts)
    if dt is None:
        return None
    return (now_jst() - dt).total_seconds() / 3600.0


def mtime_age_min(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 60.0
    except FileNotFoundError:
        return None


def mtime_iso(path):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path), JST).isoformat()
    except FileNotFoundError:
        return None


def tier(value, alive_max, dead_min):
    """valueがalive_max以下ならalive、dead_minを超えればdead、その間はslow。
    alive_max == dead_min の項目は『中間帯なし（alive/deadの二択）』として扱う
    （鬼監督のように、きっかり24時間で切り替える程度の粒度で足りる項目用）。
    valueがNone（測定不能・ファイルが無い）はdead扱いにする（でっち上げない）。"""
    if value is None:
        return "dead"
    if value <= alive_max:
        return "alive"
    if value > dead_min:
        return "dead"
    return "slow"


def today_str():
    return now_jst().strftime("%Y-%m-%d")


def read_lines(path):
    try:
        with io.open(path, encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def read_jsonl(path):
    rows = []
    for line in read_lines(path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def mk(key, name, last_ran_at, count_today, expect, expect_min, how_measured, verdict):
    return {
        "key": key,
        "name": name,
        "lastRanAt": last_ran_at,
        "countToday": count_today,
        "expect": expect,
        "expectMin": expect_min,
        "howMeasured": how_measured,
        "verdict": verdict,
    }


def _fmt(v, digits=1):
    return ("%%.%df" % digits) % v if v is not None else "計測不能"


# ───────────────────────── ①心臓（heartbeat） ─────────────────────────

def check_heartbeat():
    """843番（2026-09-18）で修正：heartbeat.logのmtimeだけを見る誤検知を直す。

    直す前の欠陥：heartbeat.log は tools/heartbeat.sh が**条件付きでしか書かない**
    （警告発生時・毎正時20秒だけの「心臓は動いています」チェックポイント）。
    machine_status_push.sh 等の外側が健全な時は、心臓のループ自体は15秒おきに
    元気に回っていても、ログには**最大60分近く何も書かれない**。その結果、
    実際は生きているのに「37分沈黙＝dead」と誤検知していた（本番実測：countToday=6）。
    これは #925「発車（auto_launch）」で見つかったのと同じ誤検知パターン
    （イベント駆動ログのmtimeだけで常駐ループの生死を測ると、健全でも沈黙が続くだけでdead扱いになる）。

    直した後の見方：heartbeat.sh が**毎周期（15秒おき）必ずtouchする**
    status/.heartbeat_alive（コメント「ループが回っている事実そのものを、何もしなくても
    毎周期touchするこのファイルで示す」）と、従来のheartbeat.logの**新しい方**をループの
    生死とする。どちらもファイルが存在しない場合だけdead（でっち上げない）。
    """
    log_path = os.path.join(ST, "heartbeat.log")
    alive_path = os.path.join(ST, ".heartbeat_alive")
    log_age = mtime_age_min(log_path)
    alive_age = mtime_age_min(alive_path)
    ages = [a for a in (log_age, alive_age) if a is not None]
    age_min = min(ages) if ages else None
    best_path = log_path
    if alive_age is not None and (log_age is None or alive_age <= log_age):
        best_path = alive_path
    verdict = tier(age_min, 10, 30)
    today = today_str()
    cnt = sum(1 for ln in read_lines(log_path) if ln.startswith(today) and "心臓は動いています" in ln)
    how = (
        "status/.heartbeat_alive（ループが15秒おきに必ずtouch）とstatus/heartbeat.log"
        "（警告時・毎正時のみ書く）のうち新しい方のmtime基準：現在%s分沈黙"
        "（10分以内=alive／30分以内=slow／それ超=dead。heartbeat.logだけを見ると"
        "健全な時でも最大60分近く沈黙し誤ってdead判定していたため、#925と同じ理由で"
        "毎周期更新される.heartbeat_aliveも合わせて見る。2026-09-18・843番で修正）" % _fmt(age_min)
    )
    return mk("heartbeat", "心臓（heartbeat）", mtime_iso(best_path), cnt, "10分以内に更新", 10, how, verdict)


# ───────────────────────── ②発車（auto_launch） ─────────────────────────

def check_auto_launch():
    """発車係の生死を、2つの別々の実測で見る（2026-09-17・925番で修正）。

    直す前の欠陥：`.last_launch_at`（＝**本当に1本着火した**時刻）のmtimeだけを見て
    「10分更新が無ければdead」と判定していた。ところが `.last_launch_at` は
    auto_launcher.py が実際に着火した時にしか書かれない。走行が上限いっぱい（満員）で
    正当に見送っている間は永遠に更新されないので、**発車係が15秒おきに元気に回っていても
    必ず赤になる**。実測（09-17 09:27）：auto_launch.log は17秒おきに
    「見送り: 走行4本／上限4本（空きなし）」を書き続けていた＝発車係は生きていたのに、
    この項目だけが「35.8分沈黙＝dead」と報告し、genzaichi.py本体の7項目の方は
    （894番で入れた満員ガード `_launch_has_room()` のおかげで）同じファイルの中で
    「✅発車：10分以内に動いている」と出していた。**同じ1枚に✅と🔴が両方載る**という
    矛盾の出どころはここ。嘘をついていたのは `.last_launch_at` 側の判定。

    直した後の見方：
      ①発車係そのものの生死＝`status/auto_launch.log` のmtime（周回のたびに必ず書かれる）。
      ②着火が無いこと＝`.last_launch_at`。ただし**空き枠がある時だけ**異常とみなす
        （894番で genzaichi 側に入れた `_launch_has_room()` をそのまま再利用。二重実装しない）。
    """
    import genzaichi  # 既存のlaunch_silence_min()をそのまま使う（798番の判定と二重実装しない）
    age_min = genzaichi.launch_silence_min()
    path = os.path.join(ST, "auto_launch.log")
    loop_age = mtime_age_min(path)          # ①発車係が周回しているか
    try:
        has_room = genzaichi._launch_has_room()
    except Exception:
        has_room = True                     # 測れない時は安全側（通常どおり沈黙を疑う）

    if loop_age is None or loop_age > 30:
        # 発車係そのものが回っていない＝本物のdead（ログが1行も増えていない）
        verdict = "dead"
        why = "発車係のログ自体が%s分伸びていません＝常駐が止まっています" % _fmt(loop_age)
    elif loop_age > 10:
        verdict = "slow"
        why = "発車係のログが%s分伸びていません（遅れ気味）" % _fmt(loop_age)
    elif age_min is None:
        # genzaichi側は「未計測=まだ一度も発車したことが無い新規環境」を異常扱いしない設計。
        # shikumiでも同じ判断（新規環境をいきなりdead扱いしない）を踏襲する。
        verdict = "alive"
        why = "発車係は%s分前に周回済み。着火の記録はまだありません（新規環境）" % _fmt(loop_age)
    elif not has_room:
        verdict = "alive"
        why = ("発車係は%s分前に周回済み。着火が%s分無いのは**走行が上限いっぱいで正当に"
               "見送っている**ためで、異常ではありません" % (_fmt(loop_age), _fmt(age_min)))
    else:
        verdict = tier(age_min, 10, 30)
        why = ("発車係は%s分前に周回済み・空き枠もあるのに、着火が%s分ありません"
               % (_fmt(loop_age), _fmt(age_min)))

    today = today_str()
    cnt = sum(1 for ln in read_lines(path) if ln.startswith(today) and "🚀 自動発車" in ln)
    how = (
        "2つを別々に見る：①発車係の生死＝status/auto_launch.logのmtime（現在%s分）"
        "②着火の間隔＝status/.last_launch_atのmtime（現在%s分沈黙・"
        "genzaichi.launch_silence_min()を再利用）。②は空き枠がある時だけ異常とみなす"
        "（genzaichi._launch_has_room()を再利用。満員での見送りは正常）。判定：%s。"
        "countTodayはauto_launch.logの本日分『🚀 自動発車』行数"
        % (_fmt(loop_age), _fmt(age_min), why)
    )
    return mk(
        "auto_launch", "発車（auto_launch）",
        mtime_iso(genzaichi.LAST_LAUNCH_STAMP), cnt, "10分以内に1本発車", 10, how, verdict,
    )


# ───────────────────────── ③AI検品 ─────────────────────────

def check_ai_verify():
    data = jread("ai_verify_stats.json", {})
    updated = data.get("updatedAt")
    hrs = hours_since(updated)
    verdict = tier(hrs, 24, 48)
    today = today_str()
    hist = data.get("history") or []
    cnt = sum(1 for h in hist if str(h.get("checkedAt") or "")[:10] == today)
    how = (
        "status/ai_verify_stats.jsonのupdatedAt基準：現在%s時間更新なし（24時間以内=alive／"
        "48時間以内=slow／それ超=dead。完了のたびに動くイベント駆動なので時間単位で見る）。"
        "countTodayはhistory配列のうち本日分のchecked件数" % _fmt(hrs)
    )
    return mk("ai_verify", "AI検品", updated, cnt, "24時間以内に更新", 24 * 60, how, verdict)


# ───────────────────────── ④鬼監督 ─────────────────────────

def check_oni_kantoku():
    """866番の実例：2026-09-09 14:03〜09-16 22:24の176時間、鬼監督(3段目AI検品)の
    ログが1行も増えなかった。実体は鬼監督自体の故障ではなく、上流のauto_launcher(発車係)が
    週次利用上限にぶつかって1週間止まっていたため、鬼監督に渡す『完了イベント』自体が
    発生しなかったこと（auto_launcher側の恒久対策は別コミットで対応済み）。

    heartbeat(#843/#861)・auto_launch(#925)で既に採用した『本当に壊れているか、単に
    見るべきイベントが無いだけか』を区別するパターンを、ここにも同じ形で適用する
    （二重実装を避けるためcheck_auto_launch()をそのまま呼ぶ）。発車係自体がdead/slowの間は
    鬼監督の沈黙を別障害として二重にチケット化しない。発車係がalive（イベントは流れているはず）
    なのに鬼監督が24時間沈黙している場合だけ、本物のdeadとして扱う。"""
    rows = read_jsonl(os.path.join(ST, "oni_kantoku_log.jsonl"))
    last_ts = rows[-1].get("checkedAt") if rows else None
    hrs = hours_since(last_ts)
    raw_verdict = tier(hrs, 24, 24)  # 二択（alive/dead）。完了イベント駆動なので中間のslow帯は設けない
    today = today_str()
    cnt = sum(1 for r in rows if str(r.get("checkedAt") or "")[:10] == today)

    verdict = raw_verdict
    suppressed_note = ""
    if raw_verdict == "dead":
        launch = check_auto_launch()
        if launch["verdict"] != "alive":
            verdict = "alive"
            suppressed_note = (
                "。ただし発車（auto_launch）自体がdead/slow（%s）で、完了イベントが発生していない"
                "ため沈黙は正常。二重に故障扱いしない（866番）" % launch["verdict"]
            )

    how = (
        "status/oni_kantoku_log.jsonlの最終行checkedAt基準：現在%s時間更新なし（24時間以内=alive、"
        "それ超=dead。イベント駆動〔完了のたび〕なので中間のslow帯は設けない）%s"
        % (_fmt(hrs), suppressed_note)
    )
    return mk("oni_kantoku", "鬼監督", last_ts, cnt, "24時間以内に記録", 24 * 60, how, verdict)


# ───────────────────────── ⑤Lovable公開 ─────────────────────────

def check_deploy():
    data = jread("deploy_history.json", {})
    at = data.get("at")
    hrs = hours_since(at)
    verdict = tier(hrs, 24, 48)
    today = today_str()
    cnt = 1 if (at and str(at)[:10] == today) else 0
    how = (
        "status/deploy_history.jsonのat基準（x-deployment-idが変わった時刻）：現在%s時間更新なし"
        "（24時間以内=alive／48時間以内=slow／それ超=dead）。ネットワークは叩かずこのファイルの"
        "記録だけで判定する（0円）" % _fmt(hrs)
    )
    return mk("deploy", "Lovable公開", at, cnt, "24時間以内に更新", 24 * 60, how, verdict)


# ───────────────────────── ⑥完了報告の押し出し ─────────────────────────

def check_dispatch_outbox():
    reported = set((jread("dispatch_reported.json", {}) or {}).get("ns") or [])
    rows = read_jsonl(os.path.join(ST, "dispatch_outbox.jsonl"))
    rows = [d for d in rows if not d.get("type")]  # stuck_escalation等は報告対象外(kenpou_checkと同じ)
    unreported = [d for d in rows if d.get("n") not in reported]
    hs = [hours_since(d.get("ts")) for d in unreported]
    hs = [h for h in hs if h is not None]
    oldest_hours = max(hs) if hs else None
    if not unreported:
        verdict = "alive"
    else:
        verdict = tier(oldest_hours, 3, 6)
    last_ts = unreported[-1].get("ts") if unreported else (rows[-1].get("ts") if rows else None)
    how = (
        "status/dispatch_outbox.jsonl（typeなし行）とstatus/dispatch_reported.jsonのns突き合わせ："
        "未報告%d件・最古%s時間経過（3時間以内=alive／6時間以内=slow／それ超=dead）"
        % (len(unreported), _fmt(oldest_hours))
    )
    return mk(
        "dispatch_outbox", "完了報告の押し出し", last_ts, len(unreported),
        "3時間以内に報告", 3 * 60, how, verdict,
    )


# ───────────────────────── ⑦現在地の紙（genzaichi.md） ─────────────────────────

def check_genzaichi_md():
    path = os.path.join(ST, "genzaichi.md")
    age_min = mtime_age_min(path)
    verdict = tier(age_min, 60, 120)
    how = (
        "status/genzaichi.mdのmtime基準：現在%s分更新なし（60分以内=alive／120分以内=slow／"
        "それ超=dead。heartbeat.sh相乗り・実質30分おき更新が前提）" % _fmt(age_min)
    )
    return mk("genzaichi_md", "現在地の紙", mtime_iso(path), None, "60分以内に更新", 60, how, verdict)


# ───────────────────────── ⑧憲法点検 ─────────────────────────

def check_kenpou_check():
    data = jread("kenpou_check.json", {})
    checked_at = data.get("checkedAt")
    hrs = hours_since(checked_at)
    verdict = tier(hrs, 24, 48)
    today = today_str()
    cnt = sum(
        1 for r in read_jsonl(os.path.join(ST, "kenpou_check_log.jsonl"))
        if str(r.get("checkedAt") or "")[:10] == today
    )
    how = (
        "status/kenpou_check.jsonのcheckedAt基準：現在%s時間更新なし（24時間以内=alive／"
        "48時間以内=slow／それ超=dead。1日1回の日次点検なので時間単位で見る）" % _fmt(hrs)
    )
    return mk("kenpou_check", "憲法点検", checked_at, cnt, "24時間以内に更新", 24 * 60, how, verdict)


# ───────────────────────── ⑨費用台帳 ─────────────────────────

def check_fal_ledger():
    path = os.path.join(ST, "fal_cost_ledger.json")
    age_min = mtime_age_min(path)
    age_hours = age_min / 60.0 if age_min is not None else None
    verdict = tier(age_hours, 24 * 7, 24 * 14)
    data = jread("fal_cost_ledger.json", {})
    today = today_str()
    cnt = sum(1 for r in (data.get("records") or []) if str(r.get("date") or "") == today)
    how = (
        "status/fal_cost_ledger.jsonのmtime基準：現在%s日更新なし（7日以内=alive／14日以内=slow／"
        "それ超=dead。支出が無い日は更新されなくて正常なので週〜2週間単位の緩い閾値にしている）"
        % (_fmt(age_hours / 24.0) if age_hours is not None else "計測不能")
    )
    return mk(
        "fal_ledger", "費用台帳", data.get("updatedAt"), cnt,
        "7日以内に更新（支出が無ければ更新なしも正常）", 24 * 7 * 60, how, verdict,
    )


# ───────────────────────── ⑩すぐ見たい枠（urgent・観測値のみ） ─────────────────────────

def check_urgent(items):
    cnt = sum(1 for it in items if it.get("urgent"))
    how = "status/queue.json内 urgent:true の件数をそのまま数えただけ（生死判定ではなく観測値）"
    return mk("urgent_lane", "すぐ見たい枠（urgent）", now_jst().isoformat(), cnt, "-", None, how, "alive")


# ───────────────────────── ⑪仕組みの生死表（自分自身） ─────────────────────────

def check_self():
    how = "status/shikumi.json自身の生成時刻（生成できた時点で生きている証拠）"
    return mk("self", "仕組みの生死表（自分自身）", now_jst().isoformat(), 1, "実行するたびに更新", None, how, "alive")


# ───────────────────────── waiting放置の追跡台帳 ─────────────────────────

def update_waiting_since(items):
    """queue.jsonの各itemにはcreatedAt/updatedAt等の時刻フィールドが無いため、
    『いつからwaitingか』を自前の台帳（status/shikumi_waiting_since.json）で追跡する。
    今回初めてwaitingを確認した番号は現在時刻を書き込み、waitingでなくなった番号は削除する。"""
    ledger = jread("shikumi_waiting_since.json", {})
    now_iso = now_jst().isoformat()
    current = {str(it.get("n")) for it in items if it.get("status") == "waiting"}
    changed = False
    for key in current:
        if key not in ledger:
            ledger[key] = now_iso
            changed = True
    for key in list(ledger.keys()):
        if key not in current:
            del ledger[key]
            changed = True
    if changed:
        jwrite(WAITING_SINCE, ledger)
    return ledger


def compute_waiting_escalations(items, ledger):
    """shikumiCheckKeyが付いたタスクが24時間waitingのまま→urgentへ自動昇格。
    shikumiCheckKey/kenpouCheckKeyが付いた『仕組み系タスク』が3日(72時間)以上waitingなら
    赤旗の1行を作る（genzaichi.pyのredFlagsへ合流させるため）。
    戻り値：(escalations記録リスト, 赤旗の行リスト, queue.jsonを書き換えたか)"""
    now = now_jst()
    escalations = []
    red_lines = []
    changed = False
    for it in items:
        if it.get("status") != "waiting":
            continue
        n = it.get("n")
        since_dt = parse_ts(ledger.get(str(n)))
        age_hours = (now - since_dt).total_seconds() / 3600.0 if since_dt else None
        shikumi_key = it.get("shikumiCheckKey")
        kenpou_key = it.get("kenpouCheckKey")
        if shikumi_key and age_hours is not None and age_hours >= 24 and not it.get("urgent"):
            it["urgent"] = True
            it["urgentReason"] = (
                "shikumi.pyが自動検知：dead判定タスクが24時間waitingのまま(%s)" % shikumi_key
            )
            changed = True
            escalations.append({
                "n": n, "type": "urgent_promoted",
                "waitingHours": round(age_hours, 1), "shikumiCheckKey": shikumi_key,
            })
        if (shikumi_key or kenpou_key) and age_hours is not None and age_hours >= 72:
            title = (it.get("title") or "")[:40]
            red_lines.append(
                "仕組み系タスク #%s「%s」が%.0f時間waitingのまま放置されています" % (n, title, age_hours)
            )
            escalations.append({"n": n, "type": "stale_3days", "waitingHours": round(age_hours, 1)})
    return escalations, red_lines, changed


# ───────────────────────── dead項目への自動対応（kenpou_check.pyのauto_queue_fixを踏襲） ─────────────────────────

def _append_self_repair_log(key, n, action):
    row = {"ts": now_jst().isoformat(), "key": key, "n": n, "action": action}
    try:
        with io.open(SELF_REPAIR_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# 861番（2026-09-18）で拡張：queue.jsonの実際のstatus値は
# waiting/running/hold/stuck/awaiting_check/verifying/touchchecking/merged/done の9種
# （859番がrunning→touchchecking→verifyingと遷移するのを本番で実測して確認）。
# 元の判定は"verifying"と"awaiting_check"は含んでいたが、実在する
# "touchchecking"（外部検品が触って確認中）と"stuck"（詰まって止まっているだけで
# 解決はしていない）が抜けていた。この2つが漏れていたせいで、その状態のあいだに
# 新しい重複チケットが積まれる余地が残っていた（843→849→852→854→859→861と同じ
# heartbeat dead誤検知が6回連続で重複発行された実例。真因は843で直っていたのに、
# 直る前の古い検知がバックログとして残り、1件ずつ別セッションが同じ確認を繰り返した）。
# done/merged/stopped等の終了状態はここに含めない（含めると本当に終わった項目まで
# 「開いている」扱いになり、新規のdead検知が二度と積めなくなってしまう）。
OPEN_QUEUE_STATUSES = (
    "waiting", "running", "hold", "stuck", "touchchecking", "awaiting_check", "verifying",
)


def _already_tagged_open(ci, key):
    q = ci._load_queue()
    for it in q.get("items", []):
        if it.get("shikumiCheckKey") == key and it.get("status") in OPEN_QUEUE_STATUSES:
            return it.get("n")
    return None


def find_duplicate_open_siblings(key, exclude_n=None):
    """同じshikumiCheckKeyでまだ開いている（未doneの）queue項目を全部返す。
    861番の教訓：真因が直った後もバックログの重複チケットが1件ずつ個別セッションで
    処理され、同じ内容の確認ページが6枚も量産された。次に同じ現象が起きた時、
    どのチケットが重複バックログかを1コマンドで洗い出せるようにする（自動でdoneに
    書き換えはしない＝queue.jsonへ直接書かないルールを守るため、洗い出しのみ）。"""
    import command_ingest as ci
    q = ci._load_queue()
    out = []
    for it in q.get("items", []):
        if it.get("shikumiCheckKey") != key:
            continue
        if exclude_n is not None and it.get("n") == exclude_n:
            continue
        if it.get("status") in OPEN_QUEUE_STATUSES:
            out.append({"n": it.get("n"), "status": it.get("status"), "title": it.get("title")})
    return out


def auto_queue_fix(item, do_queue=True):
    key = item["key"]
    if not do_queue:
        _append_self_repair_log(key, None, "skipped_no_queue")
        return {"key": key, "skipped": "--no-queue指定のため積んでいない"}

    import command_ingest as ci

    existing_n = _already_tagged_open(ci, key)
    if existing_n:
        _append_self_repair_log(key, existing_n, "skipped_duplicate")
        return {"key": key, "skipped": "既にこの点検が積んだ%d番が未解決のため積み直さない" % existing_n}

    label = "【自動検知】%s が動いていません" % item["name"]
    text = (
        "【自動検知・799番 仕組みの生死表】次の仕組みがdead判定でした。\n\n"
        "・項目：%s\n・判定方法：%s\n・countToday：%s\n\n"
        "この項目は仕組みの生死表(status/shikumi.json)で定期的（genzaichi.py相乗り・実質30分おき）に"
        "再点検されます。直したら次回の点検でalive/slowになっていることを確認してください。"
        % (item["name"], item["howMeasured"], item.get("countToday"))
    )
    status, msg = ci.queue_add(text, priority=2, label=label, origin="factory")
    result = {"key": key, "status": status, "message": msg}
    n = None
    if status == "done":
        m = re.search(r"(\d+)番として", msg)
        if m:
            n = int(m.group(1))
            with ci.queue_lock():
                q2 = ci._load_queue()
                for it in q2.get("items", []):
                    if it.get("n") == n:
                        it["shikumiCheckKey"] = key
                        break
                ci._save_queue(q2)
            result["n"] = n
    action = "queued" if n else ("skipped_duplicate" if status == "skipped" else "failed")
    _append_self_repair_log(key, n, action)
    return result


# ───────────────────────── 週次「自分で見つけた数 vs 言われた数」 ─────────────────────────

def _week_monday(dt):
    return (dt - datetime.timedelta(days=dt.weekday())).strftime("%Y-%m-%d")


def _seed_owner_pointed_log_if_needed():
    """owner_pointed_log.jsonlがまだ無い（＝このスクリプトを初めて動かした）時だけ、
    799番着手時点でたまごさんから直接指摘された今週の事例6件をシードする。
    以後の追記は tools/owner_redo.py（やり直し成功のたび）が担当し、ここでは二重に足さない。"""
    if os.path.exists(OWNER_POINTED_LOG):
        return
    ts = now_jst().isoformat()
    with io.open(OWNER_POINTED_LOG, "w", encoding="utf-8") as f:
        for note in OWNER_POINTED_SEED:
            f.write(json.dumps({"ts": ts, "note": note, "seed": True}, ensure_ascii=False) + "\n")


def update_weekly():
    _seed_owner_pointed_log_if_needed()
    week_of = _week_monday(now_jst())

    self_found = 0
    for row in read_jsonl(SELF_REPAIR_LOG):
        ts = parse_ts(row.get("ts"))
        if ts and _week_monday(ts) == week_of:
            self_found += 1

    owner_told = 0
    for row in read_jsonl(OWNER_POINTED_LOG):
        ts = parse_ts(row.get("ts"))
        if ts and _week_monday(ts) == week_of:
            owner_told += 1

    data = {
        "weekOf": week_of,
        "selfFoundCount": self_found,
        "ownerToldCount": owner_told,
        "note": (
            "selfFoundCount=このスクリプトが今週dead判定して記録した回数（status/self_repair_log.jsonl、"
            "重複スキップ含む）／ownerToldCount=たまごさんに直接『直ってない』と指摘された今週の回数"
            "（status/owner_pointed_log.jsonl、tools/owner_redo.pyがやり直し成功のたびに追記）。"
            "ownerToldCountがselfFoundCountを大きく上回るほど、自分で気づけずたまごさんに拾わせている。"
        ),
        "generatedAt": now_jst().isoformat(),
    }
    jwrite(SELF_REPAIR_WEEKLY, data)
    return data


# ───────────────────────── まとめて実行 ─────────────────────────

def build(do_queue=True):
    import command_ingest as ci

    with ci.queue_lock():
        q = ci._load_queue()
        items = q.get("items") or []
        ledger = update_waiting_since(items)
        escalations, red_lines_stale, changed = compute_waiting_escalations(items, ledger)
        if changed:
            q["items"] = items
            q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
            ci._save_queue(q)

    check_items = [
        check_heartbeat(),
        check_auto_launch(),
        check_ai_verify(),
        check_oni_kantoku(),
        check_deploy(),
        check_dispatch_outbox(),
        check_genzaichi_md(),
        check_kenpou_check(),
        check_fal_ledger(),
        check_urgent(items),
        check_self(),
    ]

    dead_items = [it for it in check_items if it["verdict"] == "dead"]
    queued = [r for r in (auto_queue_fix(it, do_queue=do_queue) for it in dead_items) if r]

    red_flags = list(red_lines_stale)
    for it in dead_items:
        red_flags.append("⚙️%s が動いていません（%s）" % (it["name"], it["howMeasured"]))

    result = {
        "generatedAt": now_jst().isoformat(),
        "items": check_items,
        "deadCount": len(dead_items),
        "queuedFixes": queued,
        "waitingEscalations": escalations,
        "redFlags": red_flags,
    }
    jwrite(SHIKUMI_OUT, result)
    update_weekly()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true", help="deadが出てもタスクを積まない（動作確認用）")
    ap.add_argument(
        "--find-duplicates", metavar="KEY",
        help="861番の再発防止：指定したshikumiCheckKeyでまだ開いている重複チケットの番号を洗い出す"
             "（queue.jsonは書き換えない・確認専用）",
    )
    args = ap.parse_args()

    if args.find_duplicates:
        sibs = find_duplicate_open_siblings(args.find_duplicates)
        if not sibs:
            print("重複なし：%sで開いているチケットはありません" % args.find_duplicates)
        else:
            print("%s で開いているチケット %d件：" % (args.find_duplicates, len(sibs)))
            for s in sibs:
                print("  #%s [%s] %s" % (s["n"], s["status"], s["title"]))
        return 0

    result = build(do_queue=not args.no_queue)
    print("仕組みの生死表 完了：%d項目中%d件がdead" % (len(result["items"]), result["deadCount"]))
    for it in result["items"]:
        mark = {"alive": "🟢", "slow": "🟡", "dead": "🔴"}.get(it["verdict"], "⚪")
        print("  %s %s：%s" % (mark, it["name"], it["howMeasured"]))
    if result["queuedFixes"]:
        print("---- 自動で積んだ/スキップした結果 ----")
        for q in result["queuedFixes"]:
            print("  %s: %s" % (q["key"], q.get("message") or q.get("skipped")))
    if result["waitingEscalations"]:
        print("---- waiting放置の自動昇格 ----")
        for e in result["waitingEscalations"]:
            print("  #%s %s (%s時間)" % (e["n"], e["type"], e["waitingHours"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
