#!/usr/bin/env python3
"""白飛びの毎日の見張り（2026-10-27・たまごさん「白飛びが全然直らない。全部なくして」）。

本番 joy-relief-station.lovable.app を頭なしブラウザ（一時プロフィール・使ったら消す）で、
tools/shirotobi_zenbamen.json の全場面（初回アクセス・SPA遷移・戻る・フルリロード・動画の埋め込み・暗い⇔明るい・画像の枠）
を通してコマ撮りし、tools/shirotobi_shirokoma.py で「一瞬だけ出る白」を数える。
  白コマ 0 → 記録だけ（status/public/shirotobi.json）
  白コマ 1以上 → Dispatch へ1行（status/dispatch_outbox.jsonl・type=shirotobi）＋ 作業キューに直す票を1件（同じ日は1件まで）
    ＋ status/shirotobi_tomeru.json に印 → tools/koutai_kanmon.py --pre-publish が「白飛びを直す公開」以外を止める
       （止める期間は印から48時間まで。直す公開そのものは止めない：コミットの説明に「白飛び」を含むものは通す）

使い方
  python3 tools/shirotobi_mimawari.py --daily      心臓から。中で20時間に1回に間引く。Macが混んでいる（負荷/CPU>1.5）ときは次の回へ
  python3 tools/shirotobi_mimawari.py --now        今すぐ測る
  python3 tools/shirotobi_mimawari.py --self-test
作るもの：$TMPDIR/shirokoma-*（shirotobi_zen.sh が終わるときに消す）／share/check/shirotobi/<日付>/ に白いコマの写しだけ（7日で消す）
安全：GETだけ・課金0・たまごさんのChrome/Braveに触らない（一時プロフィールの頭なし）・音を鳴らさない。
"""
import datetime, glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
PUB = os.path.join(ST, "public", "shirotobi.json")
STAMP = os.path.join(ST, ".shirotobi_mimawari_at")
TOMERU = os.path.join(ST, "shirotobi_tomeru.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
KOMA_ROOT = os.path.join(REPO, "share", "check", "shirotobi")
PROD = "https://joy-relief-station.lovable.app"


def now():
    return datetime.datetime.now().astimezone()


def _write(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def konzatsu():
    try:
        l1 = os.getloadavg()[0]
        n = os.cpu_count() or 1
        return l1 / n > 1.5, l1
    except Exception:
        return False, 0.0


def kataduke(days=7):
    """白いコマの写しは7日で消す（使ったらしまう）"""
    if not os.path.isdir(KOMA_ROOT):
        return
    lim = time.time() - days * 86400
    for d in glob.glob(os.path.join(KOMA_ROOT, "*")):
        try:
            if os.path.isdir(d) and os.path.getmtime(d) < lim:
                shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


def matome(res):
    """shirotobi_shirokoma.py の結果 → 1行"""
    bad = [r for r in res.get("場面", []) if r.get("真っ白コマ") or r.get("白い箱コマ")]
    if not bad:
        return 0, "白コマ0（%d場面）" % len(res.get("場面", []))
    n = res.get("真っ白コマ合計", 0) + res.get("白い箱コマ合計", 0)
    return n, "白コマ%d：" % n + "／".join("%s（真っ白%d・白い箱%d）" % (r["場面"], r["真っ白コマ"], r["白い箱コマ"]) for r in bad[:4])


def tsukanai(res):
    """本番に着かなかった場面（回線エラーの画面・行き先不明）"""
    ng = []
    for r in res.get("場面", []):
        u = str(r.get("行き先") or "")
        if not u.startswith(PROD):
            ng.append("%s→%s" % (r.get("場面"), u[:40] or "?"))
    return ng


def sokutei(name):
    """場面表を2つに分けて測る（1本が長いと畳む係に止められるため・1本10分前後）→ 結果を1つにまとめる"""
    allres = {"base": PROD, "場面": [], "真っ白コマ合計": 0, "白い箱コマ合計": 0}
    for part in ("a", "b"):
        nm = "%s-%s" % (name, part)
        env = dict(os.environ, SHIRO_STEPS_FILE=os.path.join(HERE, "shirotobi_zenbamen_%s.json" % part), SHIRO_CPU="1", SHIRO_TIMEOUT="90000")
        p = subprocess.run(["bash", os.path.join(HERE, "shirotobi_zen.sh"), nm, PROD], capture_output=True, text=True, timeout=3600, env=env)
        try:
            r = json.load(open(os.path.join(ST, "shirotobi", nm + ".json"), encoding="utf-8"))
        except Exception:
            return {"error": (p.stdout + p.stderr)[-400:]}
        allres["場面"] += r.get("場面", [])
        allres["真っ白コマ合計"] += r.get("真っ白コマ合計", 0)
        allres["白い箱コマ合計"] += r.get("白い箱コマ合計", 0)
    return allres


def run(force=False):
    if not force:
        try:
            if time.time() - os.path.getmtime(STAMP) < 20 * 3600:
                return 0
        except Exception:
            pass
        kz, l1 = konzatsu()
        if kz:
            return 0
    open(STAMP, "w").write(now().isoformat())
    kataduke()
    name = now().strftime("%m%d")
    res = sokutei(name)
    if "error" in res:
        _write(PUB, {"ts": now().isoformat(), "result": "測れず", "riyuu": res["error"]})
        return 1
    ng = tsukanai(res)
    if ng:
        # 2026-10-28 実例：回線エラー（chrome-error://）の画面を測って「白コマ0＝PASS」と出していた。着いていない場面があれば合否を出さない
        _write(PUB, {"ts": now().isoformat(), "result": "測れず", "riyuu": "本番に着かなかった場面 %d 件（%s）" % (len(ng), "／".join(ng[:3])), "bamen": res.get("場面")})
        try:
            os.remove(STAMP)  # 次の回にもう一度測る
        except Exception:
            pass
        print("SHIROTOBI_MIMAWARI: 測れず", ng[:3])
        return 1
    n, line = matome(res)
    out = {"ts": now().isoformat(), "result": "PASS" if n == 0 else "FAIL", "shirokoma": n, "ichigyou": line,
           "koma": "share/check/shirotobi/%s-a/ ・ %s-b/" % (name, name) if n else None, "bamen": res.get("場面")}
    _write(PUB, out)
    if n:
        _write(TOMERU, {"ts": now().isoformat(), "ichigyou": line, "made": (now() + datetime.timedelta(hours=48)).isoformat()})
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now().isoformat(), "from": "shirotobi_mimawari", "type": "shirotobi",
                                "title": "白飛びが本番に出ました（毎日の見張り）",
                                "message": line + "\nコマ：share/check/shirotobi/%s-a/・%s-b/ ／ 測り方：tools/shirotobi_zen.sh" % (name, name)},
                               ensure_ascii=False) + "\n")
    else:
        try:
            os.remove(TOMERU)
        except Exception:
            pass
    print("SHIROTOBI_MIMAWARI:", out["result"], line)
    return 0 if n == 0 else 2


def tomeru_ka(msg=""):
    """koutai_kanmon --pre-publish から呼ぶ。止めるなら理由の文字列、通すなら None"""
    try:
        t = json.load(open(TOMERU, encoding="utf-8"))
    except Exception:
        return None
    try:
        if datetime.datetime.fromisoformat(t["made"]) < now():
            return None
    except Exception:
        return None
    if "白飛び" in (msg or ""):
        return None
    return "本番に白飛びが出ている（%s）。白飛びを直す公開（説明に「白飛び」）以外は止めます" % t.get("ichigyou", "")


def self_test():
    ok = True
    n0, l0 = matome({"場面": [{"場面": "a", "真っ白コマ": 0, "白い箱コマ": 0}], "真っ白コマ合計": 0, "白い箱コマ合計": 0})
    ok &= n0 == 0
    n1, l1 = matome({"場面": [{"場面": "初回", "真っ白コマ": 2, "白い箱コマ": 1}], "真っ白コマ合計": 2, "白い箱コマ合計": 1})
    ok &= n1 == 3 and "初回" in l1
    global TOMERU
    keep = TOMERU
    TOMERU = os.path.join(os.environ.get("TMPDIR", "/tmp"), "shirotobi_tomeru_selftest.json")
    try:
        _write(TOMERU, {"ichigyou": "x", "made": (now() + datetime.timedelta(hours=1)).isoformat()})
        ok &= tomeru_ka("曲ページを足した") is not None
        ok &= tomeru_ka("白飛びを直す") is None
        _write(TOMERU, {"ichigyou": "x", "made": (now() - datetime.timedelta(hours=1)).isoformat()})
        ok &= tomeru_ka("曲ページを足した") is None
    finally:
        try:
            os.remove(TOMERU)
        except Exception:
            pass
        TOMERU = keep
    ok &= len(tsukanai({"場面": [{"場面": "x", "行き先": "chrome-error://chromewebdata/"}, {"場面": "y", "行き先": PROD + "/"}]})) == 1
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--now" in a:
        sys.exit(run(force=True))
    if "--daily" in a:
        sys.exit(run())
    print(__doc__)
