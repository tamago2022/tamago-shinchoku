#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zoomの録音を文字起こしする受け口（2026-10-15・たまごさん「今日20時のZoomの録音を文字起こし」）。

流れ（人は「レコーディング」を押すだけ）：
  1) 心臓から1分おきに呼ばれ、~/Documents/Zoom の下に新しく出てきた録音（.m4a、無ければ .mp4）を探す
     ※Zoomはミーティング終了後に変換してから書き出すので、大きさが2分間変わらなくなってから拾う
  2) 手元の faster-whisper（small・キャッシュ済み・0円・APIを使わない）で日本語の文字起こし（時刻つき）
  3) 「日付_★最新_文書_Zoom文字起こし_HHMM.txt」にして tools/claude_nouhin.py put で納品
     → ドライブ「AI制作物/Claude/その他」へ（心臓の flush が上げて、Dispatch へURLを1行）
  4) 済んだ録音は status/zoom_mihari.json に控え、二度やらない

約束：
  ・初回は、今ある録音を「済み」として控えるだけ（過去の録音を勝手に起こさない）
  ・二重に走らない（flock）。重い処理は nice で後ろに回す
  ・使ったらしまう：中間ファイルは作らない（音声は faster-whisper が直接読む）。書き起こしの下書きは iMac HDD に置き、納品後に消す
  ・ミーティングID・参加者名は公開リポ（status/）に書かない

使い方:
  python3 tools/zoom_mihari.py              # 1回見回る（心臓から）
  python3 tools/zoom_mihari.py --loop --until 2026-10-16T09:00   # 常駐して見回る
  python3 tools/zoom_mihari.py --file X.m4a # この1本を今すぐ起こす
  python3 tools/zoom_mihari.py --self-test
"""
import fcntl
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ZOOM_DIR = os.path.expanduser("~/Documents/Zoom")
STATE = os.path.join(REPO, "status", "zoom_mihari.json")
LOCK = os.path.join(REPO, "status", ".zoom_mihari.lock")
WORK = "/Volumes/iMac HDD/Mac標準置き場/AI作業/zoom_mojiokoshi"
EXTS_FIRST = (".m4a", ".aifc", ".wav", ".mp3")
EXTS_SECOND = (".mp4", ".mov")
STABLE_SEC = 120
MODEL = "medium"   # 2026-10-15：キャッシュ済みを確認（日本語は small より聞き違いが少ない）。無ければ small に落とす


def load_state(path=STATE):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st, path=STATE):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def find_recordings(root):
    """録音フォルダごとに1本選ぶ（m4a優先）。戻り値：[(path, size, mtime)]"""
    out = []
    if not os.path.isdir(root):
        return out
    for dp, dns, fs in os.walk(root):
        cand = [f for f in fs if f.lower().endswith(EXTS_FIRST) and not f.startswith(".")]
        if not cand:
            cand = [f for f in fs if f.lower().endswith(EXTS_SECOND) and not f.startswith(".")]
        if not cand:
            continue
        # 同じフォルダに複数（話者別など）あれば一番大きいもの＝全体の音
        best = max(cand, key=lambda f: os.path.getsize(os.path.join(dp, f)))
        p = os.path.join(dp, best)
        try:
            s = os.stat(p)
        except OSError:
            continue
        out.append((p, s.st_size, s.st_mtime))
    return out


def ready(path, size, mtime, st, now=None):
    """大きさが STABLE_SEC 変わらず、0バイトでなければ拾ってよい。"""
    now = now or time.time()
    seen = st.setdefault("sizes", {})
    prev = seen.get(path)
    seen[path] = [size, prev[1] if prev and prev[0] == size else now]
    return size > 0 and (now - seen[path][1]) >= STABLE_SEC and (now - mtime) >= STABLE_SEC


def fmt_ts(sec):
    sec = int(sec)
    return "%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)


def transcribe(path):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from faster_whisper import WhisperModel
    global MODEL
    try:
        m = WhisperModel(MODEL, device="cpu", compute_type="int8")
    except Exception:
        MODEL = "small"
        m = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segs, info = m.transcribe(path, language="ja", beam_size=1, vad_filter=True)
    lines = ["[%s] %s" % (fmt_ts(s.start), s.text.strip()) for s in segs if s.text.strip()]
    return lines, getattr(info, "duration", None)


def nouhin(lines, rec_path, duration):
    t = time.localtime(os.path.getmtime(rec_path))
    name = "%s_★最新_文書_Zoom文字起こし_%s.txt" % (time.strftime("%Y-%m-%d", t), time.strftime("%H%M", t))
    work = WORK if os.path.isdir(os.path.dirname(WORK)) else os.path.join(REPO, "status", "_zoom_tmp")
    os.makedirs(work, exist_ok=True)
    out = os.path.join(work, name)
    head = ["Zoom 文字起こし（手元のWhisper %s・自動）" % MODEL,
            "録音の日時：%s" % time.strftime("%Y-%m-%d %H:%M", t),
            "長さ：%s" % (fmt_ts(duration) if duration else "不明"),
            "※機械の書き起こしです。固有名詞・数字は聞き違いがありえます。", ""]
    with io.open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(head + lines) + "\n")
    r = subprocess.run([sys.executable, os.path.join(HERE, "claude_nouhin.py"), "put", out,
                        "--anken", "その他", "--saishin"], capture_output=True, text=True, timeout=300)
    ok = r.returncode == 0 and '"ok": false' not in (r.stdout or "")
    if ok:
        try:
            os.remove(out)   # 使ったらしまう（納品済みの写しは上げ待ちにある）
            if not os.listdir(work):
                os.rmdir(work)
        except Exception:
            pass
    return ok, name, (r.stdout or r.stderr or "").strip()[:300]


def run_one(path, st):
    t0 = time.time()
    lines, dur = transcribe(path)
    ok, name, msg = nouhin(lines, path, dur)
    st.setdefault("done", {})[path] = {"at": time.strftime("%F %T"), "file": name, "ok": ok,
                                       "lines": len(lines), "took_sec": int(time.time() - t0), "nouhin": msg}
    return ok


def main(argv):
    if "--self-test" in argv:
        return self_test()
    if "--loop" in argv:
        # 心臓に配線しなくても回る常駐（--until まで1分おき）。QuickTime＋BlackHoleの録音を ~/Documents/Zoom に保存すれば拾う。
        until = argv[argv.index("--until") + 1] if "--until" in argv else None
        end = time.mktime(time.strptime(until, "%Y-%m-%dT%H:%M")) if until else time.time() + 86400
        os.makedirs(ZOOM_DIR, exist_ok=True)
        while time.time() < end:
            try:
                main([])
            except Exception as e:
                try:
                    st = load_state(); st["loopErr"] = repr(e)[:200]; save_state(st)
                except Exception:
                    pass
            time.sleep(60)
        return 0
    lk = open(LOCK, "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0   # 先客が書き起こし中
    st = load_state()
    if "--file" in argv:
        p = os.path.abspath(argv[argv.index("--file") + 1])
        ok = run_one(p, st)
        save_state(st)
        return 0 if ok else 1
    recs = find_recordings(ZOOM_DIR)
    if not st.get("initialized"):
        st["initialized"] = time.strftime("%F %T")
        st.setdefault("done", {})
        for p, _, _ in recs:
            st["done"][p] = {"at": st["initialized"], "skip": "受け口を作る前からあった録音"}
        st["zoomDir"] = os.path.isdir(ZOOM_DIR)
        save_state(st)
        return 0
    st["lastCheck"] = time.strftime("%F %T")
    st["zoomDir"] = os.path.isdir(ZOOM_DIR)
    todo = [r for r in recs if r[0] not in st.get("done", {}) and ready(r[0], r[1], r[2], st)]
    save_state(st)
    for p, _, _ in todo:
        st["running"] = p
        save_state(st)
        try:
            run_one(p, st)
        except Exception as e:
            st.setdefault("done", {})[p] = {"at": time.strftime("%F %T"), "ok": False, "err": repr(e)[:300]}
        st.pop("running", None)
        save_state(st)
    return 0


def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    try:
        r1 = os.path.join(d, "2026-10-15 20.00.00 会議", "")
        os.makedirs(r1)
        open(os.path.join(r1, "audio1.m4a"), "wb").write(b"x" * 10)
        open(os.path.join(r1, "video1.mp4"), "wb").write(b"x" * 100)
        r2 = os.path.join(d, "2026-10-15 21.00.00 別")
        os.makedirs(r2)
        open(os.path.join(r2, "video2.mp4"), "wb").write(b"x" * 5)
        recs = sorted(find_recordings(d))
        assert [os.path.basename(p) for p, _, _ in recs] == ["audio1.m4a", "video2.mp4"], recs   # m4a優先・無ければmp4
        st = {}
        p, s, m = recs[0]
        assert ready(p, s, m - 1000, st, now=time.time()) is False       # 初見は待つ
        assert ready(p, s, m - 1000, st, now=time.time() + 200) is True  # 2分変わらなければ拾う
        assert ready(p, s + 1, m - 1000, st, now=time.time() + 300) is False  # 大きくなったら待ち直し
        assert fmt_ts(3725) == "01:02:05"
    finally:
        import shutil
        shutil.rmtree(d)   # 使ったらしまう
    print("self-test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
