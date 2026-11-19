#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全開モード（期限つき）— 2026-10-18 たまごさん指示

たまごさん（10-18 朝）：「週のクレジットは83%。23日に期限のリセット券があるので、今日のお昼(12:00)までに
天井を打ってよい。ガンガン回して。普段使えないFableでもいい」「Macが重くならない範囲で最大。ブラウザを使う子は0本」
「12:00には元の設定に自動で戻す」

■ 何をするか
  status/zenkai.json の until までの間だけ、Fableレーン（auto_launcher._fable_lane と 1158_kanmon の
  fable_slot）の上限を FABLE_LANE_MAX(3) から zenkai.json の fableLaneMax へ上げる。
  until を過ぎたら何もしない＝自動で元の3本に戻る（タイマーも書き戻しも要らない。消し忘れても害なし）。

■ Macを重くしない線（全開中でも必ず守る）
  - 4本目からは「メモリ空き40%以上」かつ「ディスク空き40GB以上」のときだけ足す。満たさなければ3本まで。
  - ディスク空き30GB未満なら全開を無効（＝通常の3本・既存の20GB線もそのまま）。
  - ロード平均は使わない（実測 10-18 05:36：ロード24〜32でもCPU合計は約3コア分・メモリ空き83%。
    iCloud(brctl)・Spotlight(mds)の入出力待ちでロードだけが膨らむため、子の本数の物差しにならない）。

使い方:
  python3 tools/zenkai.py            # 今が全開中かと、いまの上限を表示
  python3 tools/zenkai.py --self-test
戻し方（今すぐ止める）: status/zenkai.json を消す（または until を過去にする）
"""
import io
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CONF = os.path.join(REPO, "status", "zenkai.json")
JST = timezone(timedelta(hours=9))
BASE = 3          # 通常のFableレーン上限（auto_launcher.FABLE_LANE_MAX と同じ）
DISK_OFF_GB = 30  # これ未満は全開を無効
DISK_ADD_GB = 40  # 4本目以降を足すのに要る空き
MEM_ADD_PCT = 40  # 4本目以降を足すのに要るメモリ空き%
CPU_ADD_PCT = 65  # 4本目以降を足すのに要るCPU使用率の上限（fuka_hassha.CPU_3 と同じ線・2026-10-18夕「負荷判定は守る」）


def _load(path):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def active(now=None, conf_path=CONF):
    """(全開中か, 設定dict or None, 理由)"""
    c = _load(conf_path)
    if not c or not c.get("until"):
        return False, None, "zenkai.json なし"
    try:
        until = datetime.fromisoformat(c["until"])
        if until.tzinfo is None:
            until = until.replace(tzinfo=JST)
    except Exception:
        return False, None, "until が読めない"
    now = now or datetime.now(JST)
    if now >= until:
        return False, c, "期限切れ（%s）→ 通常に戻っています" % c["until"]
    return True, c, "全開中（%s まで）" % c["until"]


def _disk_free_gb():
    try:
        st = os.statvfs("/System/Volumes/Data")
    except Exception:
        try:
            st = os.statvfs("/")
        except Exception:
            return None
    return st.f_bavail * st.f_frsize / 1e9


def _cpu_busy():
    try:
        sys.path.insert(0, HERE)
        import fuka_hassha as _f
        return _f.cpu_busy_pct()
    except Exception:
        return None


def lane_max(mem_free_pct=None, disk_free_gb=None, now=None, conf_path=CONF, cpu_busy_pct=None):
    """Fableレーンの上限本数。全開でなければ BASE。"""
    ok, c, _ = active(now, conf_path)
    if not ok:
        return BASE
    want = int(c.get("fableLaneMax") or BASE)
    if disk_free_gb is None:
        disk_free_gb = _disk_free_gb()
    if disk_free_gb is not None and disk_free_gb < DISK_OFF_GB:
        return BASE
    if want <= BASE:
        return want
    if disk_free_gb is not None and disk_free_gb < DISK_ADD_GB:
        return BASE
    if mem_free_pct is not None and mem_free_pct < MEM_ADD_PCT:
        return BASE
    if cpu_busy_pct is None and conf_path == CONF:
        cpu_busy_pct = _cpu_busy()
    if cpu_busy_pct is not None and cpu_busy_pct >= CPU_ADD_PCT:
        return BASE  # 2026-10-18夕：Macを重くしない（負荷判定は守る）
    return want


def _self_test():
    import tempfile
    d = tempfile.mkdtemp()
    cp = os.path.join(d, "z.json")
    now = datetime(2026, 10, 18, 9, 0, tzinfo=JST)
    assert lane_max(80, 200, now, cp) == 3                         # ファイル無し→3
    json.dump({"until": "2026-10-18T12:00:00+09:00", "fableLaneMax": 6}, open(cp, "w"))
    assert lane_max(80, 200, now, cp) == 6                         # 全開中→6
    assert lane_max(30, 200, now, cp) == 3                         # メモリ空き少→3
    assert lane_max(80, 35, now, cp) == 3                          # ディスク40GB未満→3
    assert lane_max(80, 25, now, cp) == 3                          # 30GB未満→無効
    assert lane_max(80, 200, now, cp, cpu_busy_pct=70) == 3        # CPU65%以上→3（負荷判定は守る）
    assert lane_max(80, 200, now, cp, cpu_busy_pct=40) == 6
    later = datetime(2026, 10, 18, 12, 0, tzinfo=JST)
    assert lane_max(80, 200, later, cp) == 3                       # 12:00で自動で戻る
    assert active(later, cp)[0] is False
    os.remove(cp)
    os.rmdir(d)  # 使ったらしまう
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        ok, c, why = active()
        print(why, "／Fableレーン上限 %d本" % lane_max())
