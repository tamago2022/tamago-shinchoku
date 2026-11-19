#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週枠の線（2026-10-22 たまごさん指示）。

たまごさん「木曜の今で既に50%、ペースが早い。月・火に急な直しが出た時に天井で止まるのを避けたい。Macも少し重い」
  目標の線：日曜の朝70% → 日曜の終わり80% → 月曜の朝80〜最大85% → 火曜の朝 約92%（残り8%は急な直し用）。

決まり（auto_launcher.py・pace.py・genzaichi.py が読む）：
  - 実績が線を超えたら新規発車を止め、たまごさん名指しの急ぎだけ通す（is_meishi_isogi）。
  - 同時に走るのは最大2本。Macが重い（fuka_hassha の上限が2本以下＝ロード比0.7以上・黄/赤など）ときは1本。
  - 線の正本は status/shuwaku_sen.json（points）。週が替わったら generic の形を使う。

使い方:
  python3 tools/shuwaku_sen.py              # 判定を表示して status/public/shuwaku_sen.json に書く
  python3 tools/shuwaku_sen.py --jissoku 55 # たまごさんがアプリで見た実測を登録（今の時刻）
  python3 tools/shuwaku_sen.py --self-test
"""
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CONF = os.path.join(REPO, "status", "shuwaku_sen.json")
QUOTA = os.path.join(REPO, "status", "quota.json")
OUT = os.path.join(REPO, "status", "public", "shuwaku_sen.json")

# 週が替わったときの形（リセットからの経過時間h, %）。火曜18:00起点。
GENERIC = [(0, 0), (110, 70), (126, 80), (134, 85), (158, 92), (168, 92)]
MAX_CONC = 2
MAX_CONC_HEAVY = 1
# 機械が自動で付けた urgent（名指しではない）を見分ける語
KIKAI_URGENT = ("shikumi.py", "kenpou", "自動検知", "自動で", "hantei_hiduke", "判定日赤")


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _dt(s):
    if not s:
        return None
    s = str(s).strip()
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s[:19] if "S" in f else s[:16], f)
        except Exception:
            pass
    return None


def _interp(pts, now):
    """pts=[(datetime, pct)] を直線でつなぎ、now の値を返す。範囲外は端の値。"""
    pts = sorted(pts)
    if not pts:
        return None
    if now <= pts[0][0]:
        return float(pts[0][1])
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= now <= t1:
            span = (t1 - t0).total_seconds() or 1
            return float(v0) + (float(v1) - float(v0)) * (now - t0).total_seconds() / span
    return float(pts[-1][1])


def _next_reset(now):
    # 火曜18:00
    d = now.replace(hour=18, minute=0, second=0, microsecond=0)
    while d.weekday() != 1 or d <= now:
        d += timedelta(days=1)
        d = d.replace(hour=18, minute=0, second=0, microsecond=0)
    return d


def line_at(now=None, conf=None):
    now = now or datetime.now()
    conf = _load(CONF, {}) if conf is None else conf
    reset = _dt(conf.get("weekResetAt"))
    pts = [(_dt(p[0]), p[1]) for p in (conf.get("points") or []) if _dt(p[0])]
    if reset and pts and reset - timedelta(days=7) <= now <= reset:
        return round(_interp(pts, now), 1), "今週の線（status/shuwaku_sen.json）"
    r = _next_reset(now)
    start = r - timedelta(days=7)
    gp = [(start + timedelta(hours=h), v) for h, v in GENERIC]
    return round(_interp(gp, now), 1), "いつもの形（generic）"


def current_pct(now=None, conf=None):
    """今の使用率。quota.json（実測・推定）と、たまごさんの実測（jissoku）の新しい方。"""
    now = now or datetime.now()
    conf = _load(CONF, {}) if conf is None else conf
    cands = []
    q = _load(QUOTA, {})
    if isinstance(q.get("allPct"), (int, float)):
        t = _dt(q.get("updatedAt"))
        if t and (now - t).total_seconds() < 6 * 3600:
            cands.append((t, float(q["allPct"]), "quota.json（%s）" % ("推定" if q.get("estimated") else "実測")))
    j = conf.get("jissoku") or {}
    jt = _dt(j.get("t"))
    if jt and isinstance(j.get("pct"), (int, float)):
        cands.append((jt, float(j["pct"]), "たまごさんの実測"))
    if not cands:
        return None, "取れない"
    # 新しい方。ただし同じ週の中で実測（たまごさん）より quota が小さいのは推定のズレなので大きい方を採る（安全側）
    cands.sort()
    t, v, src = cands[-1]
    if len(cands) > 1 and cands[0][1] > v and (t - cands[0][0]).total_seconds() < 3 * 3600:
        t, v, src = cands[0]
    return round(v, 1), src


def is_meishi_isogi(it):
    """たまごさんが名指しした急ぎか。tamagoIsogi:true、または urgent で機械が自動で付けたものでない。"""
    if it.get("test"):
        return True  # 空回し・テストはClaudeを使わない
    if it.get("tamagoIsogi"):
        return True
    if it.get("urgent") in (True, "True", "true"):
        why = str(it.get("urgentReason") or "")
        return not any(k in why for k in KIKAI_URGENT)
    return False


def is_atomawashi(it, now=None, conf=None):
    """後回しの列（status/shuwaku_sen.json の atomawashi.words）に当たる仕事か。名指しの急ぎは当たらない。"""
    conf = _load(CONF, {}) if conf is None else conf
    a = conf.get("atomawashi") or {}
    until = _dt(a.get("until"))
    if until and (now or datetime.now()) > until:
        return False
    if is_meishi_isogi(it):
        return False
    t = " ".join(str(it.get(k) or "") for k in ("title", "fullTitle", "label"))
    return any(w and w in t for w in (a.get("words") or []))


def ok_to_launch(it, sen_stop, conf=None):
    """発車してよいか：後回しの列でない ＆（線の内側 or 名指しの急ぎ）。"""
    if is_atomawashi(it, conf=conf):
        return False
    return (not sen_stop) or is_meishi_isogi(it)


def conc_cap(fuka_cap=None, conf=None):
    conf = _load(CONF, {}) if conf is None else conf
    mx = int(conf.get("maxConcurrent") or MAX_CONC)
    heavy = int(conf.get("maxConcurrentHeavy") or MAX_CONC_HEAVY)
    if fuka_cap is None or fuka_cap <= 2:
        return heavy
    return mx


def hantei(now=None, conf=None):
    now = now or datetime.now()
    conf = _load(CONF, {}) if conf is None else conf
    line, line_src = line_at(now, conf)
    pct, src = current_pct(now, conf)
    over = None if pct is None else round(pct - line, 1)
    stop = over is not None and over > 0
    sen_text = "週枠の線：目標%.0f%%／実績%s" % (line, ("%.0f%%" % pct) if pct is not None else "取れない")
    if over is not None:
        sen_text += ("（線を+%.1f%%超え→新規発車は急ぎだけ）" % over) if stop else ("（線の内側・あと%.1f%%）" % abs(over))
    sen_text += "｜日曜朝70・日曜終わり80・月朝85・火朝92"
    return {"at": now.strftime("%Y-%m-%d %H:%M"), "line": line, "lineSrc": line_src, "pct": pct,
            "pctSrc": src, "over": over, "stopNew": stop, "maxConcurrent": int(conf.get("maxConcurrent") or MAX_CONC),
            "maxConcurrentHeavy": int(conf.get("maxConcurrentHeavy") or MAX_CONC_HEAVY), "senLine": sen_text}


def write(d):
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
    except Exception:
        pass


def self_test():
    ng = []

    def eq(a, b, m):
        if a != b:
            ng.append("%s: %r != %r" % (m, a, b))
    conf = _load(CONF, {})
    eq(line_at(datetime(2026, 10, 22, 16, 40), conf)[0], 50.0, "木曜の今")
    eq(line_at(datetime(2026, 10, 25, 8, 0), conf)[0], 70.0, "日曜朝")
    eq(line_at(datetime(2026, 10, 26, 0, 0), conf)[0], 80.0, "日曜終わり")
    eq(line_at(datetime(2026, 10, 26, 8, 0), conf)[0], 85.0, "月曜朝")
    eq(line_at(datetime(2026, 10, 27, 8, 0), conf)[0], 92.0, "火曜朝")
    eq(line_at(datetime(2026, 10, 27, 17, 0), conf)[0], 92.0, "火曜夕")
    # 木→日朝 は1日あたり約6〜7%
    a = line_at(datetime(2026, 10, 23, 16, 40), conf)[0]
    eq(6.0 <= a - 50 <= 8.0, True, "木→金の1日分(%.1f)" % (a - 50))
    # 来週は generic
    eq(line_at(datetime(2026, 11, 1, 8, 0), conf)[0], 70.0, "来週の日曜朝")
    eq(is_meishi_isogi({"urgent": True}), True, "urgent（理由なし）")
    eq(is_meishi_isogi({"urgent": True, "urgentReason": "たまごさんが進捗表の🔥ボタンで指定"}), True, "🔥ボタン")
    eq(is_meishi_isogi({"urgent": True, "urgentReason": "shikumi.pyが自動検知：…"}), False, "機械のurgent")
    eq(is_meishi_isogi({"priority": 1, "title": "判定日赤｜…"}), False, "判定日赤")
    eq(is_meishi_isogi({"tamagoIsogi": True}), True, "tamagoIsogi")
    eq(conc_cap(4, conf), 2, "軽い→2本")
    eq(conc_cap(2, conf), 1, "重い→1本")
    eq(conc_cap(None, conf), 1, "測れない→1本")
    eq(is_atomawashi({"title": "星勝特集に思い込みを差し込む"}, datetime(2026, 10, 23), conf), True, "後回し")
    eq(is_atomawashi({"title": "星勝特集に思い込みを差し込む", "tamagoIsogi": True}, datetime(2026, 10, 23), conf), False, "名指しは後回しにしない")
    eq(is_atomawashi({"title": "クインシー・ジョーンズ"}, datetime(2026, 11, 1), conf), False, "期限後は戻す")
    eq(ok_to_launch({"title": "曲ページ直し"}, False, conf), True, "普通の仕事・線の内側")
    eq(ok_to_launch({"title": "曲ページ直し"}, True, conf), False, "普通の仕事・線超え")
    h = hantei(datetime(2026, 10, 22, 16, 41), dict(conf, jissoku={"t": "2026-10-22T16:41:00", "pct": 60}))
    eq(h["stopNew"], True, "線超え→止める")
    h = hantei(datetime(2026, 10, 22, 16, 41), dict(conf, jissoku={"t": "2026-10-22T16:41:00", "pct": 45}))
    eq(h["stopNew"], False, "線の内側→通す")
    if ng:
        print("SELF-TEST NG\n" + "\n".join(ng))
        return 1
    print("SELF-TEST OK")
    return 0


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    if "--jissoku" in a:
        v = float(a[a.index("--jissoku") + 1])
        conf = _load(CONF, {})
        conf["jissoku"] = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "pct": v, "src": "たまごさんの実測（--jissoku）"}
        json.dump(conf, io.open(CONF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    d = hantei()
    write(d)
    print(json.dumps(d, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
