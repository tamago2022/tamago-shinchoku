#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固まる手前の見張り（2026-10-15・たまごさん「Mac が固まる手前まで重い」）。心臓から1分おき。

目安（tools/fuka_hassha.kiken と同じ物差し）：
  1分ロード ≥ コア数×3 ／ スワップ使用率 ≥ 95% ／ memory_pressure の空き < 5%
検知したら：
  ・新規発車を止める（status/no_launch.flag・目印「負荷の番人」。走っている子は殺さない）
  ・工場の重いディスク走査（shimau.py・youryou_*.py・それらが起こした du）を止める
  ・Dispatch へ1行（status/dispatch_outbox.jsonl・30分に1回まで）
5分続けて目安を下回ったら、自分が立てた旗だけ外す。
status/public/fuka_mihari.json に今の数字を残す。status/teishi.go があれば重い走査を今すぐ止める。
"""
import io, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fuka_hassha  # noqa: E402

FLAG = os.path.join(REPO, "status", "no_launch.flag")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
STATE = os.path.join(REPO, "status", "fuka_mihari_state.json")
PUB = os.path.join(REPO, "status", "public", "fuka_mihari.json")
TEISHI = os.path.join(REPO, "status", "teishi.go")
MARK = "負荷の番人"
HEAVY = ("tools/shimau.py", "tools/youryou_", "tools/worktree_taihi.py", "du -skx", "du -xk", "du -sk")


CLEANERS = ("tools/shimau.py", "tools/worktree_taihi.py")


def _disk_free_gb():
    try:
        st = os.statvfs(os.path.expanduser("~"))
        return st.f_bavail * st.f_frsize / 1e9
    except Exception:
        return 99.0


def omoi_wo_tomeru():
    n = 0
    # 2026-10-15 19時：空きが22GB未満の間は、空きを作る係（shimau・worktree_taihi）は止めない。
    #   止めると「重い→掃除停止→ディスク減→発車停止」の悪循環になる（実測 46GB→19GB）。du の走査だけ止める。
    low = _disk_free_gb() < 22
    for pat in HEAVY:
        if low and pat in CLEANERS:
            continue
        r = subprocess.run(["pkill", "-f", pat], capture_output=True)
        n += 1 if r.returncode == 0 else 0
    return n


def load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    m = fuka_hassha.measure()
    k = fuka_hassha.kiken(m)
    st = load(STATE, {})
    now = time.time()
    tometa = 0
    if os.path.exists(TEISHI):
        try:
            os.remove(TEISHI)
        except Exception:
            pass
        tometa = omoi_wo_tomeru()
    if k:
        st["ok_since"] = None
        tometa += omoi_wo_tomeru()
        if not os.path.exists(FLAG):
            io.open(FLAG, "w", encoding="utf-8").write("%s：%s。新規発車を止めました（%s）。5分落ち着いたら自動で外れます。\n"
                                                       % (MARK, k, time.strftime("%F %T")))
        if now - st.get("told_at", 0) > 1800:
            try:
                with io.open(OUTBOX, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "n": "fuka-mihari",
                                        "type": "fuka_akai", "title": "Macが固まる手前：%s" % k,
                                        "message": "新規発車を止め、重いディスク走査を止めました（走行中の子はそのまま）。"},
                                       ensure_ascii=False) + "\n")
                st["told_at"] = now
            except Exception:
                pass
    else:
        st["ok_since"] = st.get("ok_since") or now
        if now - st["ok_since"] >= 300 and os.path.exists(FLAG):
            try:
                if MARK in io.open(FLAG, encoding="utf-8").read():
                    os.remove(FLAG)
            except Exception:
                pass
    json.dump(st, io.open(STATE, "w", encoding="utf-8"))
    flag_mine = False
    try:
        flag_mine = os.path.exists(FLAG) and MARK in io.open(FLAG, encoding="utf-8").read()
    except Exception:
        pass
    json.dump({"at": time.strftime("%F %T"), "kiken": k, "load1": m.get("load1"), "ncpu": m.get("ncpu"),
               "swapPct": m.get("swapPct"), "memFreePct": m.get("memFreePct"),
               "pressureLevel": m.get("pressureLevel"), "launch_stopped_by_me": flag_mine,
               "omoi_sousa_tometa": tometa},
              io.open(PUB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
