#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量トレンド検証（2026-09-08・648番「容量の減りが止まったかを24時間測って証明する」）。

背景：642番でdisk_guardianのDrive走査を15分おき→1日1回に削減、645番で125GB解放。
それで本当に減りが止まったのかを、実測で証明する係。

★新しくdfを叩くプロセスは追加しない。disk_guardian.pyが既に15分おきに
  `空き %.1fGB` をstatus/disk_guardian.logへ記録している（=1時間ごとより細かい）。
  この既存ログを読むだけにする方が軽い（★軽く作る。この見張り自体が容量や
  負荷を食ったら本末転倒、という指示に従う）。

やること：
  ① disk_guardian.logから実測値を全部読み、直近24時間を1時間刻みでまとめる
  ② 1時間で1GB以上減った区間があれば、その時間帯にstatus/history.jsonlで
     走っていたタスク番号を「犯人候補」として記録する（Driveに触れていないか
     どうかは判定できないため、その時間帯の走行タスク一覧を出すだけに留める）
  ③ 前日比を計算し、-5GBを超えたら上の犯人候補つきで警告、それ以外は
     「変化なし」の1行だけを返す
  ④ 結果をstatus/disk_trend_report.jsonへ保存し、確認ページ用の軽量SVG折れ線
     グラフをshare/check/img/へ書き出す（外部ライブラリ不使用＝matplotlib等を
     入れない。文字列だけで描くので依存が増えない）

disk_guardian.py本体からは1日1回だけ呼ばれる想定（GDRIVE_CHECK_INTERVAL_SECと
同じパターンでスタンプファイルを見て間引く。呼び出し側は1行追加するだけ）。
"""
import io
import json
import os
import re
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)  # /Users/mac/Desktop/tamago-shinchoku

LOG_PATH = os.path.join(REPO, "status", "disk_guardian.log")
HISTORY_JSONL = os.path.join(REPO, "status", "history.jsonl")
DAILY_HISTORY_JSON = os.path.join(REPO, "status", "disk_daily_history.json")

OUT_JSON = os.path.join(REPO, "status", "disk_trend_report.json")
OUT_SVG = os.path.join(REPO, "share", "check", "img", "648-disk-trend.svg")

DROP_PER_HOUR_GB = 1.0     # これ以上/時 減ったら「犯人候補」を記録
DAILY_DROP_WARN_GB = 5.0   # 既存 maybe_record_daily() と同じ閾値

LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?:空き|片付け後の空き) (\d+\.?\d*)GB")
TASK_NO_RE = re.compile(r"[（(](\d+)番")


def parse_log(path=LOG_PATH):
    """(datetime, free_gb) のリストを時刻昇順で返す。"""
    entries = []
    if not os.path.exists(path):
        return entries
    with io.open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            try:
                dt = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                gb = float(m.group(2))
            except Exception:
                continue
            entries.append((dt, gb))
    entries.sort(key=lambda x: x[0])
    return entries


# 2026-09-09（685番・「61.2GBで横ばい」と実測35.3GBが26GB食い違っていた件の原因）：
# 旧実装は「実測が無い時間はNoneのまま欠測」とコメントしながら、実際には
# 直前の実測値をそのまま埋める(forward-fill)コードになっていた。disk_guardianが
# 一晩(14時間)止まっていた区間がまるごと旧値で埋まり、「横ばい・止まっている」と
# 誤判定していた。実測とスロット時刻の差がこの閾値を超えたら、素直にNone(欠測)にする。
STALE_GAP_HOURS = 1.5  # 実行間隔900秒(15分)の6倍の余裕


def hourly_series(entries, hours=24, end=None):
    """直近hours時間を1時間刻みでリサンプルする。各時刻スロットには、その時刻
    以前で最も近い実測値を採用する。ただしその実測からSTALE_GAP_HOURS以上
    離れている（＝実測が長時間途切れていた）場合はNoneのまま欠測扱いにする。"""
    if end is None:
        end = datetime.datetime.now()
    start = end - datetime.timedelta(hours=hours)
    slots = []
    t = start
    idx = 0
    n = len(entries)
    last_val = None
    last_dt = None
    while t <= end:
        while idx < n and entries[idx][0] <= t:
            last_val = entries[idx][1]
            last_dt = entries[idx][0]
            idx += 1
        if last_dt is not None and (t - last_dt).total_seconds() > STALE_GAP_HOURS * 3600:
            slots.append((t, None))
        else:
            slots.append((t, last_val))
        t += datetime.timedelta(hours=1)
    return slots


def find_culprits(t1, t2):
    """t1〜t2の間にhistory.jsonlへ記録されていたタスク番号(◯◯番)の一覧を返す。"""
    nums = set()
    titles = set()
    if not os.path.exists(HISTORY_JSONL):
        return [], []
    with io.open(HISTORY_JSONL, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = d.get("t")
            if not ts:
                continue
            try:
                # "2026-09-08T16:58:11+09:00" -> naive local time
                dt = datetime.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                continue
            if t1 <= dt <= t2:
                title = d.get("title") or ""
                m = TASK_NO_RE.search(title)
                if m:
                    nums.add(m.group(1) + "番")
                elif title:
                    titles.add(title[:24])
    return sorted(nums), sorted(titles)


def detect_drops(slots, threshold=DROP_PER_HOUR_GB):
    """隣接する1時間スロット間でthreshold以上減った区間を検出し、犯人候補を添える。"""
    drops = []
    for i in range(1, len(slots)):
        t_prev, v_prev = slots[i - 1]
        t_cur, v_cur = slots[i]
        if v_prev is None or v_cur is None:
            continue
        delta = v_prev - v_cur
        if delta >= threshold:
            nums, titles = find_culprits(t_prev, t_cur)
            drops.append({
                "from": t_prev.strftime("%H:%M"),
                "to": t_cur.strftime("%H:%M"),
                "from_idx": i - 1,
                "to_idx": i,
                "delta_gb": round(delta, 1),
                "culprit_tasks": nums,
                "culprit_titles": titles,
            })
    return drops


def _load_json(path, default=None):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def find_measurement_gap_hours(t1, t2, path=LOG_PATH):
    """t1〜t2の間で、実測(空きGB)ログが最大何時間途切れていたかを返す。
    2026-09-09（685番）：18:48→翌08:41の14時間、disk_guardianの記録がまるごと
    無かった（Macがスリープ等）。「特定できず」で終わらせず、少なくとも
    「観測できていない時間帯があった」ことを報告に出す。"""
    entries = parse_log(path)
    in_range = [e[0] for e in entries if t1 <= e[0] <= t2]
    # 区間の両端(t1・t2)も境界として含める。末尾（t2直前で記録が途切れて
    # いたケース＝今回の実例）を見落とすと、大きな空白があるのに0時間台の
    # 結果を返してしまうバグになる（685番で実測して発見・修正）。
    bounds = [t1] + in_range + [t2]
    max_gap = 0.0
    for i in range(1, len(bounds)):
        gap = (bounds[i] - bounds[i - 1]).total_seconds() / 3600
        max_gap = max(max_gap, gap)
    return round(max_gap, 1)


def daily_line():
    """『昨日：67GB→◯GB（増減◯GB）。原因：◯◯』の1行、または『変化なし』を返す。"""
    hist = _load_json(DAILY_HISTORY_JSON, {"days": []})
    days = hist.get("days") or []
    if len(days) < 2:
        return "昨日分のデータがまだ無いため比較不可（記録は継続中）"
    prev, cur = days[-2], days[-1]
    delta = round(prev["free_gb"] - cur["free_gb"], 1)
    if delta > DAILY_DROP_WARN_GB:
        # 前日から今日までの区間で犯人候補を探す
        try:
            t1 = datetime.datetime.strptime(prev["measured_at"], "%Y-%m-%d %H:%M:%S")
            t2 = datetime.datetime.strptime(cur["measured_at"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            t1 = t2 = None
        nums = []
        gap_hours = 0.0
        if t1 and t2:
            nums, _ = find_culprits(t1, t2)
            gap_hours = find_measurement_gap_hours(t1, t2)
        hints = []
        if nums:
            hints.append("・".join(nums))
        if gap_hours >= STALE_GAP_HOURS:
            hints.append("実測に%.1fh空白あり(スリープ等で見えていない時間帯。手動でduの増分確認を)" % gap_hours)
        cause = "・".join(hints) if hints else "特定できず(history.jsonlに手がかり無し)"
        return "昨日：%.1fGB→%.1fGB（増減-%.1fGB）。原因：%s" % (
            prev["free_gb"], cur["free_gb"], delta, cause)
    elif delta < -0.01:
        return "昨日：%.1fGB→%.1fGB（増減+%.1fGB・増えた）" % (
            prev["free_gb"], cur["free_gb"], -delta)
    else:
        return "変化なし（昨日：%.1fGB→今日：%.1fGB）" % (prev["free_gb"], cur["free_gb"])


def render_svg(slots, drops, out_path=OUT_SVG):
    """外部ライブラリ無しで軽量な折れ線グラフSVGを書く。"""
    pts = [(t, v) for t, v in slots if v is not None]
    if len(pts) < 2:
        return None
    W, H = 760, 300
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    vals = [v for _, v in pts]
    vmin, vmax = min(vals), max(vals)
    if vmax - vmin < 1:
        vmax = vmin + 1
    span = vmax - vmin

    def x_of(i):
        return pad_l + (W - pad_l - pad_r) * i / max(1, len(pts) - 1)

    def y_of(v):
        return pad_t + (H - pad_t - pad_b) * (1 - (v - vmin) / span)

    poly = " ".join("%.1f,%.1f" % (x_of(i), y_of(v)) for i, (_, v) in enumerate(pts))
    dot_r = 3
    dots = "".join(
        '<circle cx="%.1f" cy="%.1f" r="%d" fill="#2563eb"/>' % (x_of(i), y_of(v), dot_r)
        for i, (_, v) in enumerate(pts)
    )
    # 目盛りラベル：3時間おきに時刻を出す
    labels = []
    for i, (t, v) in enumerate(pts):
        if i % 3 == 0 or i == len(pts) - 1:
            labels.append(
                '<text x="%.1f" y="%d" font-size="10" fill="#555" text-anchor="middle">%s</text>'
                % (x_of(i), H - pad_b + 15, t.strftime("%H:%M")))
    # 減少区間を赤い帯で強調（slots側のfrom_idx/to_idxを、欠測を除いたpts側の
    # インデックスへ日時一致で変換する。同じ"HH:MM"が複数回出る日跨ぎでも誤爆しない）。
    pts_index_by_dt = {t: i for i, (t, _) in enumerate(pts)}
    drop_marks = []
    for d in drops:
        t_prev, t_cur = slots[d["from_idx"]][0], slots[d["to_idx"]][0]
        i1, i2 = pts_index_by_dt.get(t_prev), pts_index_by_dt.get(t_cur)
        if i1 is not None and i2 is not None:
            x1, x2 = x_of(min(i1, i2)), x_of(max(i1, i2))
            drop_marks.append(
                '<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="#ef4444" opacity="0.12"/>'
                % (x1, pad_t, x2 - x1, H - pad_t - pad_b))

    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="sans-serif">' % (W, H, W, H))
    parts.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H))
    parts.append(
        '<text x="%d" y="16" font-size="13" fill="#111">'
        '空き容量の推移（直近24時間・disk_guardian.log実測）</text>' % pad_l)
    parts.append("".join(drop_marks))
    parts.append('<polyline points="%s" fill="none" stroke="#2563eb" stroke-width="2"/>' % poly)
    parts.append(dots)
    parts.append('<text x="5" y="%.1f" font-size="11" fill="#2563eb">%.1fGB</text>'
                  % (y_of(vmax) + 4, vmax))
    parts.append('<text x="5" y="%.1f" font-size="11" fill="#2563eb">%.1fGB</text>'
                  % (y_of(vmin) + 4, vmin))
    parts.append("".join(labels))
    parts.append("</svg>")
    svg = "\n".join(parts)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path


def build_report(hours=24):
    entries = parse_log()
    slots = hourly_series(entries, hours=hours)
    drops = detect_drops(slots)
    valid = [(t, v) for t, v in slots if v is not None]
    first_v = valid[0][1] if valid else None
    last_v = valid[-1][1] if valid else None
    total_delta = round((first_v - last_v), 1) if (first_v is not None and last_v is not None) else None

    def verdict_of(delta):
        if delta is None:
            return "データ不足"
        if delta > 2.0:
            return "要注意・まだ減っている"
        if delta < -2.0:
            return "増えた（片付け・容量解放があった）"
        return "横ばい・止まっている"

    # 24時間全体の「山」（最大値＝直近の容量解放が完了した直後）以降を安定期間として
    # 別途判定する。24時間まるごとの比較だと容量解放イベント自体の増加を含んでしまい
    # 「解放後、本当に止まったか」の判定にならないため、山から現在までの推移
    # （＝解放後の自然な減り方）を本命の判定として使う。
    stable = None
    if valid:
        max_idx = max(range(len(valid)), key=lambda i: valid[i][1])
        if max_idx < len(valid) - 1:
            peak_t, peak_v = valid[max_idx]
            stable_delta = round(peak_v - last_v, 1)  # 正=減った、負=さらに増えた
            stable = {
                "since": peak_t.strftime("%Y-%m-%d %H:%M"),
                "since_free_gb": peak_v,
                "now_free_gb": last_v,
                "delta_gb": stable_delta,
                "hours": round((valid[-1][0] - peak_t).total_seconds() / 3600, 1),
                "verdict": verdict_of(stable_delta),
            }

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hours": hours,
        "slots": [
            {"t": t.strftime("%Y-%m-%d %H:%M"), "free_gb": v} for t, v in slots
        ],
        "first_free_gb": first_v,
        "last_free_gb": last_v,
        "total_delta_gb": total_delta,
        "verdict": verdict_of(total_delta),
        "stable_period_since_trough": stable,
        "drops_over_1gb_per_hour": drops,
        "daily_line": daily_line(),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    render_svg(slots, drops)
    return report


if __name__ == "__main__":
    r = build_report()
    print(json.dumps(r, ensure_ascii=False, indent=2))
