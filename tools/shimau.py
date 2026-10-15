#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使ったらしまう係（2026-10-15・たまごさん「macOS にデータが溜まらない仕組みに。使ったらしまう、使ったら閉じる」）。

心臓から1時間おきに呼ばれ、20時間に1回だけ本体が走る（status/shimau.go があれば今すぐ）。
  ① 測る：Mac本体と iMac HDD の空き、HDD の大きいフォルダ（深さ2）、前回からの増え方の上位、
          メモリを食っているプロセス上位（スワップの元）→ status/public/shimau.json
  ② しまう（作り直せるものだけ。たまごさんのファイル・壺と金庫・Vault・Cookie/ログイン情報には触らない）
     ・$TMPDIR（/var/folders/…/T）：3日以上さわられていないもの（com.apple.*・claude*・TemporaryItems は除く）
       自動操作ブラウザの使い捨てプロフィール（puppeteer/playwright/chromium の一時フォルダ）は1日で
     ・Claude の古いセッション（local-agent-mode-sessions）の outputs：7日以上前のもの（今のセッションは除く）
     ・ブラウザ（Chrome のみ。Brave には触らない）のキャッシュだけ（Cache/Code Cache/GPUCache/シェーダー/Service Worker の CacheStorage）
       ＝Cookie・Local Storage・IndexedDB（ログイン状態やサイトのデータ）は消さない
     ・自動操作用の Chrome（Application Support/Google/Chrome-headless）はまるごと（作り直せる）
  ③ HDD の置き場を日数で片付ける：作業場の控え 14日・控え(_1142_gomi) 30日・Claude上げ済み 30日
"""
import glob, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import hdd_okiba  # noqa: E402

HOME = os.path.expanduser("~")
AS = HOME + "/Library/Application Support"
GO = os.path.join(REPO, "status", "shimau.go")
STAMP = os.path.join(REPO, "status", ".shimau_at")
OUT = os.path.join(REPO, "status", "public", "shimau.json")
HIST = os.path.join(REPO, "status", "shimau_hist.json")
CUR_SESSION = "67542e85-a104-4946-bcde-7c7916354942"
DAY = 86400
BROWSER_CACHE = ("Cache", "Code Cache", "GPUCache", "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
                 "GrShaderCache", "ShaderCache", "Service Worker/CacheStorage", "Service Worker/ScriptCache")
HDD_DAYS = {"作業場の控え": 14, "控え": 30, "Claude上げ済み": 30}


def free_gb(p="/System/Volumes/Data"):
    try:
        st = os.statvfs(p)
        return round(st.f_bavail * st.f_frsize / 1e9, 2)
    except Exception:
        return None


def du_gb(p, t=900):
    try:
        r = subprocess.run(["du", "-skx", p], capture_output=True, text=True, timeout=t)
        return round(int(r.stdout.split()[0]) / 1048576, 2)
    except Exception:
        return None


def rm(p):
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.lexists(p):
        try:
            os.remove(p)
        except Exception:
            pass


def newest(p, limit=3000):
    m = os.lstat(p).st_mtime
    if not os.path.isdir(p) or os.path.islink(p):
        return m
    n = 0
    for dp, dns, fns in os.walk(p):
        for x in dns + fns:
            try:
                m = max(m, os.lstat(os.path.join(dp, x)).st_mtime)
            except Exception:
                pass
            n += 1
            if n > limit:
                return m
    return m


def save(res):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def step(res, name, fn):
    b = free_gb()
    try:
        r = fn()
    except Exception as e:
        r = "失敗 %s" % str(e)[:120]
    res["shimatta"].append({"what": name, "gb": round((free_gb() or 0) - (b or 0), 2), "detail": r})
    save(res)


def tmpdir():
    t = tempfile.gettempdir()
    now = time.time()
    out = []
    for n in os.listdir(t):
        p = os.path.join(t, n)
        if n.startswith(("com.apple", "claude", "TemporaryItems", ".")) or os.path.islink(p):
            continue
        low = n.lower()
        days = 1 if any(k in low for k in ("puppeteer", "playwright", "chromium", "chrome", "lighthouse", "pw-")) else 3
        try:
            if now - newest(p) > days * DAY:
                rm(p)
                out.append(n)
        except Exception:
            pass
    return "%d個" % len(out)


def claude_sessions():
    now = time.time()
    n = 0
    for o in glob.glob(AS + "/Claude/local-agent-mode-sessions/*/*/*/outputs") + \
            glob.glob(AS + "/Claude/local-agent-mode-sessions/*/*/outputs"):
        if CUR_SESSION in o:
            continue
        try:
            if now - newest(o) > 7 * DAY:
                rm(o)
                n += 1
        except Exception:
            pass
    return "outputs %d個" % n


def browser_cache():
    n = 0
    # 2026-10-16 たまごさん「Braveには触らない」→ Brave はキャッシュも対象外（Chrome だけ）
    for base in (AS + "/Google/Chrome",):
        for prof in glob.glob(base + "/*/"):
            for c in BROWSER_CACHE:
                p = os.path.join(prof, c)
                if os.path.isdir(p):
                    rm(p)
                    n += 1
        for c in ("GrShaderCache", "ShaderCache", "component_crx_cache", "extensions_crx_cache"):
            p = os.path.join(base, c)
            if os.path.isdir(p):
                rm(p)
                n += 1
    p = AS + "/Google/Chrome-headless"
    if os.path.isdir(p):
        rm(p)
        n += 1
    return "%dか所（Cookie・ログイン情報は残した）" % n


def hdd_okiba_souji():
    if not hdd_okiba.ok():
        return "HDDが無い"
    now = time.time()
    n, b = 0, 0
    for top, days in HDD_DAYS.items():
        root = os.path.join(hdd_okiba.ROOT, top)
        for dp, dns, fns in os.walk(root):
            for fn in fns:
                p = os.path.join(dp, fn)
                try:
                    st = os.lstat(p)
                    if now - st.st_mtime > days * DAY:
                        b += st.st_size
                        os.remove(p)
                        n += 1
                except Exception:
                    pass
    return "%d個 %.2fGB" % (n, b / 1e9)


def hakaru(res):
    res["hdd_free_gb"] = free_gb(hdd_okiba.HDD) if os.path.isdir(hdd_okiba.HDD) else None
    big = {}
    if os.path.isdir(hdd_okiba.HDD):
        for a in sorted(os.listdir(hdd_okiba.HDD)):
            pa = os.path.join(hdd_okiba.HDD, a)
            if a.startswith(".") or not os.path.isdir(pa):
                continue
            big[a] = du_gb(pa, 2400)
            if a == "Mac標準置き場":
                for b in os.listdir(pa):
                    if os.path.isdir(os.path.join(pa, b)):
                        big[a + "/" + b] = du_gb(os.path.join(pa, b), 1800)
            res["hdd_big_gb"] = dict(sorted(big.items(), key=lambda x: -(x[1] or 0)))
            save(res)
    mac = {}
    for k, p in {"$TMPDIR": tempfile.gettempdir(), "/private/tmp": "/private/tmp", "Claude": AS + "/Claude",
                 "Chrome": AS + "/Google/Chrome", "Brave": AS + "/BraveSoftware", "~/.claude": HOME + "/.claude",
                 "~/Library/Caches": HOME + "/Library/Caches", "AI作業": HOME + "/Documents/AI作業",
                 "工場status": REPO + "/status", "~/.tamago": HOME + "/.tamago", "Movies": HOME + "/Movies"}.items():
        mac[k] = du_gb(p)
    res["mac_big_gb"] = dict(sorted(mac.items(), key=lambda x: -(x[1] or 0)))
    try:
        prev = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        prev = {}
    cur = dict(("mac:" + k, v) for k, v in mac.items())
    cur.update(("hdd:" + k, v) for k, v in big.items())
    res["fueta_jouni"] = sorted([{"what": k, "gb": round((v or 0) - (prev.get(k) or 0), 2)}
                                 for k, v in cur.items() if prev.get(k) is not None],
                                key=lambda x: -x["gb"])[:10]
    json.dump(cur, open(HIST, "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run(["ps", "-axo", "rss,comm"], capture_output=True, text=True)
    rows = []
    for l in r.stdout.splitlines()[1:]:
        try:
            rss, comm = l.strip().split(None, 1)
            rows.append((int(rss), comm))
        except Exception:
            pass
    agg = {}
    for rss, comm in rows:
        k = comm.split("/Contents/")[0].split("/")[-1]
        agg[k] = agg.get(k, 0) + rss
    res["memory_top_gb"] = [{"app": k, "gb": round(v / 1048576, 2)} for k, v in sorted(agg.items(), key=lambda x: -x[1])[:12]]
    res["swap"] = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True).stdout.strip()


def jougen_run():
    import youryou_jougen
    return youryou_jougen.run()


def omoi():
    """2026-10-15 たまごさん「重いディスク走査は負荷が下がるまで再開しない」。重い間は「測る」を飛ばす。
    2026-10-16 実測：この判定（スワップ90%超・Braveのせいで一日中）で shimau.go が18:58から5時間放置され、
    片付けまで一度も走らなかった。→ 片付け（消す）は負荷に関係なく走る。重いのは du の「測る」だけ。"""
    try:
        import fuka_hassha
        m = fuka_hassha.measure()
        r = (m.get("load1") or 0) / float(m.get("ncpu") or 8)
        return r >= 1.0 or fuka_hassha.kiken(m) is not None
    except Exception:
        return False


def main():
    force = os.path.exists(GO)
    try:
        recent = time.time() - os.path.getmtime(STAMP) < 20 * 3600
    except Exception:
        recent = False
    if force:
        os.remove(GO)
    elif recent:
        return
    if not recent:
        open(STAMP, "w").close()   # 「測る」（重い du）は20時間に1回。shimau.go の臨時便は片付けだけ
    try:
        os.setsid()
    except Exception:
        pass
    res = {"at": time.strftime("%F %T"), "mac_free_gb_before": free_gb(), "state": "しまっている", "shimatta": []}
    save(res)
    step(res, "$TMPDIR の古いもの", tmpdir)
    step(res, "Claude の古いセッションの outputs", claude_sessions)
    step(res, "ブラウザのキャッシュ", browser_cache)
    step(res, "HDD の置き場（日数で）", hdd_okiba_souji)
    step(res, "場所ごとの上限（youryou_jougen）", jougen_run)
    step(res, "動画・音声の中間ファイル（chukan_shimau）", lambda: __import__("chukan_shimau").run())
    if recent:
        res["state"] = "片付けだけ（測るのは20時間に1回）"
    elif omoi():
        res["state"] = "測るのは重いので次回"
    else:
        res["state"] = "測っている"
        save(res)
        hakaru(res)
    res.update(state="完了", finished=time.strftime("%F %T"), mac_free_gb_after=free_gb())
    save(res)


if __name__ == "__main__":
    import fcntl
    lf = open(os.path.join(REPO, "status", ".shimau.lock"), "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        sys.exit(0)
    main()
