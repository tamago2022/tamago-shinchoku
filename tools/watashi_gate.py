#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1048番【渡す前の門】― たまごさんに渡すページを、渡す前に実際に開いて押して確かめる係。

■ たまごさんの言葉（2026-09-24・そのまま）
  「俺でテストするなって言ってるじゃん。動くものを出してきてよって。
    まだ不完全なものを俺に触らせないでよ。表示されすらしないよ。
    俺の間に入ってほしい。動かないんだったら突き返してほしい。」

■ 事故の中身（これが作った理由の全部）
  share/ohon/1046-live2d.html を渡した。たまごさんの画面で何も表示されなかった。
  こちらのChromeは WebGL が切ってあり（canvas.getContext('webgl') → false・実測）、
  **動くところを一度も見ずに渡していた。**コードを読んで「たぶん動く」で渡した。

■ ★穴はどこにあったか（道具が無かったのではない）
  tools/fukumen.py（覆面調査員）は、Mac上で本物のブラウザを立ち上げて本番を触る。
  2026-09-23、それで「曲ページが6回中6回止まる／CLS 0.169／LCP 22.5秒」を取っている。
  AIは1回も呼んでいない・0円。**道具は既にあった。**
  なのに **こちらが作った share/ のページには一度も通していなかった。**
  外向けのサイトだけ見て、自分が出すものを見ていなかった。それが穴。
  → だから覆面を作り直さない。**同じ本物のブラウザを、自分の出すものに向ける。**

■ この門が見るもの（「そもそも開いて動くか」だけ）
  絵の良し悪し   → tools/e_gate.py（外部AI）
  書いてある日本語 → tools/oni_gate.py
  数字と出典     → tools/kazu_gate.py
  ★開いて動くか  → ここ

■ 落とす条件（判定文は1行もここに書かない。全部 tools/hantei.py の watashi_han）
  ① 開いて10秒で画面に中身が出ていない　② 押しても何も起きないボタンがある
  ③ consoleにエラー　④ 外から読む部品が200以外　⑤ 375pxではみ出す／出ない
  ⑥ fps30割れ／1MB超／WebGLが要るのに立ち上がらない

■ WebGL（★公式の記述にだけ従う。オリジナルの呪文を書かない）
  Chromium公式 docs/gpu/swiftshader.md：
    「1) As the OpenGL ES driver, SwANGLE … --use-gl=angle --use-angle=swiftshader」
    「2) As the **unsafe** WebGL fallback … --use-gl=angle --use-angle=swiftshader-webgl
        --enable-unsafe-swiftshader」
  https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/gpu/swiftshader.md
  ここでは 1) ＋ --enable-unsafe-swiftshader を使う（GPUの無い機械でも本物と同じ道を通す）。

■ 走らせ方
  ［Mac側］実際にブラウザを開くのはMacだけ。サンドボックスからは外に出られない。
     python3 tools/watashi_gate.py --check share/ohon/1046-live2d.html
     python3 tools/watashi_gate.py --sweep share/check      # 既に渡した分を全部さかのぼる
     python3 tools/watashi_gate.py --selftest               # 門が効いているか
  ［サンドボックス側／kohyou］
     watashi_gate.verdict(path) … 中身のハッシュで「通った記録」を引く。
     ★記録が無ければ通さない。「測っていない＝通っていない」。黙って素通りさせない。

■ お金：AIを1回も呼ばない。0円。
"""
import argparse
import glob
import hashlib
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT = os.path.join(REPO, "status", "watashi_gate")
LOG = os.path.join(REPO, "status", "watashi_gate.log")
SHOT = os.path.join(OUT, "shots")

# 公式の記述どおり（上のURL）。ここを勝手に増やさない。
CHROME_ARGS = [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--disable-dev-shm-usage",
]

WEBGL_RE = re.compile(r"webgl|three\.|three\.min|live2d|pixi|babylon|getContext\(\s*['\"]webgl",
                      re.I)
ANIM_RE = re.compile(r"requestAnimationFrame|@keyframes|<video|animation\s*:", re.I)


def _log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), line))
    except Exception:
        pass


def key_of(path):
    """中身のハッシュ。1文字でも直したら別物＝門を通し直す。"""
    full = path if os.path.isabs(path) else os.path.join(REPO, path)
    raw = io.open(full, "rb").read()
    return hashlib.sha1(raw).hexdigest()[:16]


# ── ページの中で走らせる観測器 ────────────────────────────────────────
SNAP_JS = r"""
() => {
  const body = document.body;
  const txt = (body && body.innerText || '').replace(/\s+/g, ' ').trim();
  // 「描画された要素」＝実際に面積を持って見えているもの。display:none は数えない。
  let painted = 0;
  const all = document.querySelectorAll('body *');
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if (r.width > 1 && r.height > 1) painted++;
    if (painted > 4000) break;
  }
  const cans = [];
  for (const c of document.querySelectorAll('canvas')) {
    let sig = 'unreadable', blank = null;
    try {
      const g = c.getContext('2d', {willReadFrequently:true});
      if (g && c.width > 0 && c.height > 0) {
        const d = g.getImageData(0, 0, Math.min(c.width,64), Math.min(c.height,64)).data;
        let s = 0, first = d[0] + ',' + d[1] + ',' + d[2] + ',' + d[3], same = true;
        for (let i = 0; i < d.length; i += 4) {
          s = (s * 31 + d[i] + d[i+1]*3 + d[i+2]*7 + d[i+3]*11) % 2147483647;
          if (same && (d[i]+','+d[i+1]+','+d[i+2]+','+d[i+3]) !== first) same = false;
        }
        sig = String(s); blank = same;
      } else {
        // WebGLのcanvasは2dで読めない。toDataURLで代用する。
        const u = c.toDataURL(); sig = String(u.length) + ':' + u.slice(-24);
        blank = (u.length < 400);
      }
    } catch (e) { sig = 'err'; }
    cans.push({w: c.width, h: c.height, sig: sig, blank: blank});
  }
  return {
    text_bytes: new Blob([txt]).size,
    painted_nodes: painted,
    html_len: (body ? body.innerHTML.length : 0),
    scroll_w: Math.max(document.documentElement.scrollWidth, body ? body.scrollWidth : 0),
    href: location.href,
    canvases: cans,
  };
}
"""

WEBGL_JS = r"""
() => {
  try {
    const c = document.createElement('canvas');
    const g = c.getContext('webgl2') || c.getContext('webgl') || c.getContext('experimental-webgl');
    if (!g) return {ok:false, why:'getContext が false を返しました'};
    const d = g.getExtension('WEBGL_debug_renderer_info');
    return {ok:true, renderer: d ? String(g.getParameter(d.UNMASKED_RENDERER_WEBGL)) : 'unknown'};
  } catch (e) { return {ok:false, why:String(e).slice(0,120)}; }
}
"""

FPS_JS = r"""
() => new Promise((res) => {
  let n = 0; const t0 = performance.now();
  const tick = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(tick);
                       else res({frames:n, ms: performance.now() - t0}); };
  requestAnimationFrame(tick);
})
"""


def _sig(snap):
    """画面の今の見た目を1本の文字列にする。押す前後の比較に使う。"""
    return "|".join([str(snap.get("html_len")), str(snap.get("painted_nodes")),
                     str(snap.get("text_bytes")), str(snap.get("href")),
                     ",".join(str(c.get("sig")) for c in (snap.get("canvases") or []))])


def measure(path, shots=True):
    """★実際にブラウザを開いて数字を取る。Macでしか走らない。判定はしない。"""
    from playwright.sync_api import sync_playwright

    full = path if os.path.isabs(path) else os.path.join(REPO, path)
    raw = io.open(full, encoding="utf-8", errors="replace").read()
    obs = {
        "path": os.path.relpath(full, REPO),
        "key": key_of(full),
        "at": time.strftime("%FT%T"),
        "bytes": os.path.getsize(full),
        "needs_webgl": bool(WEBGL_RE.search(raw)),
        "is_animated": bool(ANIM_RE.search(raw)),
        "console_errors": [], "resources": [], "dead_buttons": [],
        "buttons_total": 0,
    }
    url = "file://" + full
    os.makedirs(SHOT, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=CHROME_ARGS)
        try:
            ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                                      locale="ja-JP", timezone_id="Asia/Tokyo")
            page = ctx.new_page()
            page.set_default_timeout(15000)

            def on_console(m):
                if m.type == "error":
                    obs["console_errors"].append("console: " + (m.text or "")[:200])
            page.on("console", on_console)
            page.on("pageerror", lambda e: obs["console_errors"].append("pageerror: " + str(e)[:200]))

            def on_resp(r):
                u = r.url or ""
                if u.startswith("http"):
                    obs["resources"].append({"url": u, "status": r.status})
            page.on("response", on_resp)
            page.on("requestfailed", lambda r: obs["resources"].append(
                {"url": r.url, "status": 0, "why": (r.failure or "")[:80]}))

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as ex:
                obs["open_error"] = str(ex)[:200]
                return obs

            # ★「開いて10秒」。たまごさんが見るのはこの状態。
            page.wait_for_timeout(10000)
            try:
                snap = page.evaluate(SNAP_JS)
            except Exception as ex:
                obs["open_error"] = "10秒たっても画面を読めませんでした: %s" % str(ex)[:140]
                return obs
            obs.update({"text_bytes": snap["text_bytes"],
                        "painted_nodes": snap["painted_nodes"],
                        "canvases": snap["canvases"]})
            blanks = [("%dx%d" % (c["w"], c["h"])) for c in snap["canvases"] if c.get("blank")]
            if blanks:
                obs["canvas_blank"] = "／".join(blanks[:3])

            # WebGLが本当に立ち上がるか
            if obs["needs_webgl"]:
                try:
                    w = page.evaluate(WEBGL_JS)
                except Exception as ex:
                    w = {"ok": False, "why": str(ex)[:100]}
                obs["webgl_ok"] = bool(w.get("ok"))
                obs["webgl"] = w

            if shots:
                sp = os.path.join(SHOT, obs["key"] + "-1280.png")
                try:
                    page.screenshot(path=sp)
                    obs["shot"] = os.path.relpath(sp, REPO)
                except Exception:
                    pass

            # ② ボタンを全部押す。押す前後で画面が1ミリも変わらなければ死んでいる。
            sel = ("button, [role=button], input[type=button], input[type=submit], "
                   "a[href^='#'], [onclick]")
            try:
                n = page.locator(sel).count()
            except Exception:
                n = 0
            obs["buttons_total"] = n
            for i in range(min(n, 12)):
                try:
                    b = page.locator(sel).nth(i)
                    if not b.is_visible():
                        continue
                    label = (b.inner_text(timeout=2000) or "").strip().replace("\n", " ")[:24]
                    label = label or (b.get_attribute("aria-label") or "")[:24] or "（名前なし#%d）" % i
                    before = _sig(page.evaluate(SNAP_JS))
                    b.click(timeout=4000, force=True)
                    page.wait_for_timeout(900)
                    after = _sig(page.evaluate(SNAP_JS))
                    if before == after:
                        obs["dead_buttons"].append(label)
                except Exception as ex:
                    obs["dead_buttons"].append("%s（押せません:%s）"
                                               % (("#%d" % i), str(ex)[:40]))

            # ⑥ 動くもののfps
            if obs["is_animated"]:
                try:
                    f = page.evaluate(FPS_JS)
                    obs["fps"] = round(f["frames"] / (f["ms"] / 1000.0), 1)
                except Exception:
                    obs["fps"] = None

            # ⑤ 375px
            try:
                mctx = browser.new_context(viewport={"width": 375, "height": 812},
                                           is_mobile=True, has_touch=True,
                                           device_scale_factor=2, locale="ja-JP")
                mp = mctx.new_page()
                mp.set_default_timeout(15000)
                mp.goto(url, wait_until="domcontentloaded", timeout=30000)
                mp.wait_for_timeout(6000)
                ms = mp.evaluate(SNAP_JS)
                obs["mobile"] = {"scroll_w": ms["scroll_w"],
                                 "text_bytes": ms["text_bytes"],
                                 "painted_nodes": ms["painted_nodes"]}
                if shots:
                    sp = os.path.join(SHOT, obs["key"] + "-375.png")
                    try:
                        mp.screenshot(path=sp)
                        obs["shot_375"] = os.path.relpath(sp, REPO)
                    except Exception:
                        pass
                mctx.close()
            except Exception as ex:
                obs["mobile"] = {}
                obs["mobile_error"] = str(ex)[:140]
            ctx.close()
        finally:
            try:
                browser.close()
            except Exception:
                pass
    return obs


def check(path, shots=True):
    """測って→判定して→記録に残す。返り値: (止める理由の一覧, 観測の記録)"""
    import hantei
    try:
        obs = measure(path, shots=shots)
    except Exception as ex:
        obs = {"path": path, "key": key_of(path), "at": time.strftime("%FT%T"),
               "open_error": "門が走れませんでした: %s" % str(ex)[:200]}
    # ★ブラウザ自体が立ち上がらなかったときは「NG」として記録に残さない。
    #   残すと「測ったのに落ちた」と「測れなかった」が混ざり、直しようのない赤が居座る。
    #   （2026-09-24 実測：サンドボックスから走らせると Executable doesn't exist で
    #     全部NGになり、記録が嘘で埋まった。）
    oe = str(obs.get("open_error") or "")
    if "Executable doesn't exist" in oe or "playwright install" in oe:
        raise RuntimeError("この機械にはブラウザが入っていません。Mac側で走らせてください：%s" % oe[:160])

    stop = hantei.watashi_han(obs)
    obs["stop"] = stop
    obs["ok"] = not stop
    os.makedirs(OUT, exist_ok=True)
    with io.open(os.path.join(OUT, obs["key"] + ".json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(obs, ensure_ascii=False, indent=1))
    _log("%s %s key=%s%s" % ("OK" if obs["ok"] else "NG", obs["path"], obs["key"],
                             ("  理由=" + stop[0][:100]) if stop else ""))
    return stop, obs


def verdict(path):
    """★サンドボックス側の窓口。中身のハッシュで「通った記録」を引くだけ。

    記録が無ければ通さない。**測っていない＝通っていない。**
    ここが緩むと、また「動くところを一度も見ずに渡す」に戻る。
    """
    try:
        k = key_of(path)
    except Exception as e:
        return ["ファイルが読めません: %s" % e]
    p = os.path.join(OUT, k + ".json")
    if not os.path.exists(p):
        return ["この中身（key %s）はまだ一度も実際に開いていません。"
                "Mac側で `python3 tools/watashi_gate.py --check %s` を通してから出すこと。"
                % (k, path)]
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        return ["通った記録が読めません: %s" % e]
    return list(d.get("stop") or [])


def sweep(folder="share/check", limit=0, shots=False):
    """既に渡してしまった分を、さかのぼって全部通す。"""
    d = folder if os.path.isabs(folder) else os.path.join(REPO, folder)
    files = sorted(glob.glob(os.path.join(d, "*.html")))
    if limit:
        files = files[:limit]
    rows = []
    for i, f in enumerate(files, 1):
        rel = os.path.relpath(f, REPO)
        stop, obs = check(rel, shots=shots)
        rows.append({"path": rel, "ok": not stop, "stop": stop, "key": obs.get("key")})
        print("[%d/%d] %s %s" % (i, len(files), "OK" if not stop else "NG", rel))
        if stop:
            print("        " + stop[0][:120])
    out = os.path.join(OUT, "sweep-%s.json" % time.strftime("%Y%m%d-%H%M"))
    with io.open(out, "w", encoding="utf-8") as fp:
        fp.write(json.dumps({"at": time.strftime("%FT%T"), "folder": folder,
                             "total": len(rows),
                             "ng": sum(1 for r in rows if not r["ok"]),
                             "rows": rows}, ensure_ascii=False, indent=1))
    print("\n通した:%d 落ちた:%d → %s" % (len(rows), sum(1 for r in rows if not r["ok"]),
                                      os.path.relpath(out, REPO)))
    return rows


def selftest():
    """門が効いているか。①判定の見本試験 ②わざと壊したHTMLを本当に落とすか"""
    import hantei
    r = hantei.watashi_kanmon()
    print(r.get("line") or r.get("blocked") or r)
    ok1 = bool(r.get("line"))

    tmp = os.path.join(OUT, "_selftest")
    os.makedirs(tmp, exist_ok=True)
    warui = os.path.join(tmp, "warui.html")
    io.open(warui, "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>わざと壊した見本</title>"
        "<script src='https://tamago-nai-url.example.com/nai.js'></script>"
        "<body><button id=b>押しても何も起きない</button>"
        "<script>document.getElementById('b').onclick=function(){};"
        "undefined_function_wo_yobu();</script>")
    yoi = os.path.join(tmp, "yoi.html")
    io.open(yoi, "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>正しい見本</title>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<body style='font:16px/1.8 system-ui;margin:0;padding:16px'>"
        "<h1>正しい見本</h1><p>" + ("これは画面に出ている本文です。" * 20) + "</p>"
        "<button id=b>押すと増える</button><div id=o></div>"
        "<script>document.getElementById('b').onclick=function(){"
        "document.getElementById('o').innerHTML+='<p>押された</p>';};</script>")

    s1, _ = check(warui, shots=False)
    s2, _ = check(yoi, shots=False)
    print("わざと壊した見本 → %s（%d件）" % ("落ちた✅" if s1 else "通ってしまった🔴", len(s1)))
    for x in s1[:6]:
        print("   ・" + x[:110])
    print("正しい見本 → %s" % ("通った✅" if not s2 else "落ちた🔴：%s" % s2[0][:110]))
    ok = ok1 and bool(s1) and not s2
    print("\n門は%s" % ("効いています" if ok else "効いていません"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", help="1枚を実際に開いて確かめる")
    ap.add_argument("--verdict", help="通った記録を引くだけ（サンドボックス可）")
    ap.add_argument("--sweep", nargs="?", const="share/check", help="フォルダを全部さかのぼる")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())
    if a.check:
        stop, obs = check(a.check, shots=not a.no_shots)
        print(json.dumps({"path": obs.get("path"), "key": obs.get("key"),
                          "ok": not stop, "止めた理由": stop,
                          "実測": {k: obs.get(k) for k in
                                   ("text_bytes", "painted_nodes", "buttons_total",
                                    "dead_buttons", "fps", "webgl", "mobile", "bytes")
                                   if k in obs},
                          "consoleエラー": obs.get("console_errors", [])[:5]},
                         ensure_ascii=False, indent=1))
        sys.exit(0 if not stop else 1)
    if a.verdict:
        v = verdict(a.verdict)
        print(json.dumps({"ok": not v, "止めた理由": v}, ensure_ascii=False, indent=1))
        sys.exit(0 if not v else 1)
    if a.sweep:
        sweep(a.sweep, limit=a.limit, shots=not a.no_shots)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
