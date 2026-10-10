#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""無音の関所（muon）— 確認道具は音を鳴らさない。確認はデータで行う。

■ 起きたこと（2026-10-10 17:00〜17:02・実測）
  status/_v1oc/fix_and_test.sh → v2.mjs が Playwright の WebKit（iPhone 15 のふり）で
  曲ページと特集の YouTube を1タップ再生し、muted=false・約5秒、音ありで鳴らした。
  ログ：status/_v1oc/fix_and_test.log（"playingWithSound": true が2件）。
  ＝たまごさんのMacから急に音が出た原因。

■ この1本でやること
  --kanmon   … 静的点検。ブラウザを起動するファイルに無音の指定が無ければ赤（exit 1）。
               音声を鳴らすコマンド（afplay / ffplay / mpg123 / mplayer / mpv / say）も赤。
               結果 status/public/muon_kanmon.json
  --mimawari … Mac上で今鳴っている物を探して止める（pmset のオーディオ表明＋ps）。
               止めるのは afplay/ffplay/say 等と、Playwright が起動したブラウザだけ。
               たまごさんの Chrome / Brave / Safari 本体には触らない。結果 status/muon_mimawari.json
  --self-test… 逆テスト（無音あり／なしのダミーを正しく見分けるか）

■ Python から使う道具
  from muon import CHROMIUM_ARGS, FIREFOX_PREFS, INIT_JS, muon_context
    chromium.launch(args=[..., *CHROMIUM_ARGS])
    firefox.launch(firefox_user_prefs=FIREFOX_PREFS)
    ctx.add_init_script(INIT_JS)        # WebKit は起動引数で消せないので、ページの中で音量を0に固定
  Node は tools/muon.mjs（同じ中身）。

■ WebKit の無音のしかた（muted を書き替えないのがミソ）
  「音ありで再生できるか」の確認は v.muted と v.paused と currentTime のデータで判定する。
  muted を強制すると確認そのものが嘘になるので、muted はページの意図のまま残し、
  **実際の音量（volume）だけを0に固定**する（getter はページが置いた値を返す）。
  WebAudio は出口に音量0の GainNode を挟む。speechSynthesis は黙らせる。
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_KANMON = os.path.join(REPO, "status", "public", "muon_kanmon.json")
OUT_MIMAWARI = os.path.join(REPO, "status", "muon_mimawari.json")

CHROMIUM_ARGS = ["--mute-audio", "--autoplay-policy=user-gesture-required"]
FIREFOX_PREFS = {"media.volume_scale": "0.0", "media.autoplay.default": 5}

INIT_JS = r"""(() => {
  try {
    if (window.__muon) return; window.__muon = 1;
    const P = HTMLMediaElement.prototype;
    const vd = Object.getOwnPropertyDescriptor(P, "volume");
    const zero = (el) => { try { vd.set.call(el, 0); } catch (e) {} };
    Object.defineProperty(P, "volume", { configurable: true,
      get() { return this.__muonV === undefined ? 1 : this.__muonV; },
      set(v) { this.__muonV = v; zero(this); } });
    const op = P.play;
    P.play = function () { zero(this); return op.apply(this, arguments); };
    for (const ev of ["play", "playing", "loadedmetadata", "volumechange"]) {
      document.addEventListener(ev, (e) => { if (e.target instanceof HTMLMediaElement) zero(e.target); }, true);
    }
    setInterval(() => { for (const el of document.querySelectorAll("video,audio")) zero(el); }, 200);
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC && window.AudioNode) {
      const oc = AudioNode.prototype.connect;
      AudioNode.prototype.connect = function (d, ...a) {
        if (window.AudioDestinationNode && d instanceof AudioDestinationNode) {
          const c = d.context;
          if (!c.__muonG) { c.__muonG = c.createGain(); c.__muonG.gain.value = 0; oc.call(c.__muonG, d); }
          return oc.call(this, c.__muonG, ...a);
        }
        return oc.call(this, d, ...a);
      };
    }
    if (window.speechSynthesis) { window.speechSynthesis.speak = () => {}; }
  } catch (e) {}
})();"""


def muon_context(ctx):
    """Playwright(Python) の BrowserContext に無音の仕掛けを入れて返す。"""
    ctx.add_init_script(INIT_JS)
    return ctx


# ------------------------------------------------------------------ 静的点検
EXTS = (".py", ".mjs", ".js", ".cjs", ".ts", ".sh", ".command")
SKIP_DIRS = {"node_modules", ".git", "browsers", "jrs", "src_main", "dist", ".venv", "venv",
             "__pycache__", "ms-playwright", ".tmp_q34468_wt"}
# 点検しない（止める側・説明だけの側）
SELF = {"muon.py", "muon.mjs", "muon_kanmon.mjs", "machine_health.py", "orphan_reaper.py",
        "1200_tatamu.py", "tamago_tatamu.py"}

RE_LAUNCH = {
    "chromium": re.compile(r"\bchromium\s*\.\s*launch(PersistentContext|_persistent_context)?\s*\(|puppeteer\s*\.\s*launch\s*\("),
    "webkit": re.compile(r"\bwebkit\s*\.\s*launch(PersistentContext|_persistent_context)?\s*\("),
    "firefox": re.compile(r"\bfirefox\s*\.\s*launch(PersistentContext|_persistent_context)?\s*\("),
    "chrome_cli": re.compile(r"--headless(=new)?\b"),
}
RE_CONNECT = re.compile(r"connectOverCDP|connect_over_cdp")
RE_SOUND = re.compile(
    r"(?:^|[\s\"'`\[(,;|&])(afplay|ffplay|mpg123|mplayer|mpv)(?=[\s\"'`,)\]]|$)"
    r"|\[\s*[\"'`]say[\"'`]|(?:spawn|execFile|execFileSync|spawnSync)\(\s*[\"'`]say[\"'`]|/usr/bin/say\b|(?:^|[;&|]\s*|\$\(\s*)say\s+-",
    re.M)
OK_MARK = re.compile(r"muon:\s*(接続のみ|音なし確認済み)")


def need_of(engine):
    if engine in ("chromium", "chrome_cli"):
        return re.compile(r"--mute-audio|CHROMIUM_ARGS|MUON_ARGS|muonLaunch|muon_launch")
    if engine == "webkit":
        return re.compile(r"INIT_JS|MUON_INIT|muonContext|muon_context|muonLaunch|muon_launch")
    return re.compile(r"media\.volume_scale|FIREFOX_PREFS|MUON_FIREFOX|muonLaunch|muon_launch")


def strip_comments(src, path):
    """コメント内の説明文で誤検知しない（# / // の行コメントだけ落とす）。"""
    out = []
    py = path.endswith((".py", ".sh", ".command"))
    for ln in src.splitlines():
        s = ln.lstrip()
        if py and s.startswith("#") and not s.startswith("#!"):
            continue
        if not py and s.startswith("//"):
            continue
        out.append(ln)
    return "\n".join(out)


def check_text(src, path="x.mjs"):
    """1ファイル分の中身を見て、違反のリストを返す（空なら合格）。"""
    bad = []
    body = strip_comments(src, path)
    for eng, rx in RE_LAUNCH.items():
        if eng == "chrome_cli" and not path.endswith((".sh", ".command", ".mjs", ".js", ".py", ".cjs")):
            continue
        if rx.search(body) and not need_of(eng).search(src):
            bad.append({"engine": eng, "why": "ブラウザ(%s)を起動しているのに無音の指定が無い" % eng})
    if RE_CONNECT.search(body) and not any(r.search(body) for r in RE_LAUNCH.values()):
        if not (OK_MARK.search(src) or need_of("webkit").search(src)):
            bad.append({"engine": "cdp", "why": "既存ブラウザに接続しているのに無音の印（muon: 接続のみ）が無い"})
    m = RE_SOUND.search(body)
    if m:
        bad.append({"engine": "sound", "why": "音を鳴らすコマンド（%s）を使っている" % m.group(0).strip()})
    return bad


def walk(roots):
    for root in roots:
        root = os.path.expanduser(root)
        if os.path.isfile(root):
            yield root
            continue
        base = root.rstrip(os.sep).count(os.sep)
        deep = 1 if root.rstrip(os.sep).endswith(os.sep + "status") else 6   # status は一発物の箱が数千ある＝浅く見る
        for dp, dns, fns in os.walk(root):
            if dp.count(os.sep) - base >= deep:
                dns[:] = []
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".tmp")]
            for fn in fns:
                if fn.endswith(EXTS) and fn not in SELF and not fn.endswith(".bak"):
                    yield os.path.join(dp, fn)


DEFAULT_ROOTS = [os.path.join(REPO, "tools"), os.path.join(REPO, "status"), "~/.tamago"]


def kanmon(roots=None, write=True, max_depth_status=2):
    roots = roots or DEFAULT_ROOTS
    hits, n = [], 0
    for p in walk(roots):
        rel = os.path.relpath(p, REPO) if p.startswith(REPO) else p
        if rel.startswith("status" + os.sep) and rel.count(os.sep) > max_depth_status:
            continue
        try:
            src = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        n += 1
        for b in check_text(src, p):
            hits.append(dict(b, file=rel))
    res = {"at": time.strftime("%Y-%m-%d %H:%M"), "seen": n, "red": len(hits), "hits": hits,
           "roots": [os.path.expanduser(r) for r in roots], "ok": not hits}
    if write:
        os.makedirs(os.path.dirname(OUT_KANMON), exist_ok=True)
        io.open(OUT_KANMON, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    return res


# ------------------------------------------------------------------ いま鳴っている物を止める（Mac）
SOUND_BIN = re.compile(r"(^|/)(afplay|ffplay|mpg123|mplayer|mpv|say)(\s|$)")
PW_BROWSER = re.compile(r"ms-playwright|/\.tamago/(pwold/)?browsers/|playwright[^ ]*/(webkit|chromium|firefox)"
                        r"|WebKitPlaywright|pw_run\.sh|headless_shell")
NEVER = re.compile(r"/Applications/(Google Chrome|Brave Browser|Safari|Firefox)\.app/Contents/MacOS/")


def mimawari(kill=True):
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "audioPids": [], "found": [], "killed": [], "note": []}
    try:
        a = subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True, timeout=10).stdout
        for m in re.finditer(r"pid (\d+)\(([^)]*)\)[^\n]*\n?[^\n]*(coreaudiod|audio)", a, re.I):
            res["audioPids"].append({"pid": int(m.group(1)), "name": m.group(2)})
        for m in re.finditer(r"Created for PID: (\d+)", a):
            res["audioPids"].append({"pid": int(m.group(1)), "name": "?"})
    except Exception as e:  # noqa: BLE001
        res["note"].append("pmset が読めない：%s" % type(e).__name__)
    try:
        ps = subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,command="], capture_output=True, text=True,
                            timeout=10).stdout
    except Exception as e:  # noqa: BLE001
        res["note"].append("ps が読めない：%s" % type(e).__name__)
        ps = ""
    me = os.getpid()
    for ln in ps.splitlines():
        parts = ln.strip().split(None, 3)
        if len(parts) < 4:
            continue
        pid, cmd = int(parts[0]), parts[3]
        if pid == me or NEVER.search(cmd):   # たまごさんのブラウザ本体には触らない
            continue
        kind = "sound" if SOUND_BIN.search(cmd.split(" ")[0] + " ") else ("pw" if PW_BROWSER.search(cmd) else "")
        if not kind:
            continue
        rec = {"pid": pid, "etime": parts[2], "kind": kind, "cmd": cmd[:160]}
        res["found"].append(rec)
        if kill:
            try:
                os.kill(pid, 15)
                res["killed"].append(pid)
            except Exception as e:  # noqa: BLE001
                res["note"].append("%d を止められない：%s" % (pid, type(e).__name__))
    res["ok"] = True
    os.makedirs(os.path.dirname(OUT_MIMAWARI), exist_ok=True)
    io.open(OUT_MIMAWARI, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def run_job(payload):
    """gaibu_runner kind=muon から呼ばれる（Mac側）。"""
    p = payload or {}
    out = {"totalYen": 0.0}
    if p.get("mimawari", True):
        out["mimawari"] = mimawari(kill=not p.get("dry"))
    if p.get("kanmon", True):
        k = kanmon()
        out["kanmon"] = {"seen": k["seen"], "red": k["red"], "hits": k["hits"][:60]}
    if p.get("install_hooks"):
        r = subprocess.run(["node", os.path.join(HERE, "stop_kanmon", "install_hooks.mjs")],
                           capture_output=True, text=True, timeout=60)
        out["install"] = {"rc": r.returncode, "out": (r.stdout or "")[-1500:], "err": (r.stderr or "")[-800:]}
    out["ok"] = True
    return out


def self_test():
    cases = [
        ("a.mjs", "const b = await chromium.launch({headless:true});", False),
        ("b.mjs", "const b = await chromium.launch({args:['--mute-audio']});", True),
        ("c.mjs", "const b = await webkit.launch({headless:true});", False),
        ("d.mjs", "import {muonContext} from './muon.mjs'; const b = await webkit.launch(); muonContext(ctx)", True),
        ("e.py", "br = pw.firefox.launch()", False),
        ("f.py", "br = pw.firefox.launch(firefox_user_prefs=FIREFOX_PREFS)", True),
        ("g.sh", "afplay /tmp/x.wav", False),
        ("h.sh", "\"$CH\" --headless=new --disable-gpu", False),
        ("i.sh", "\"$CH\" --headless=new --mute-audio", True),
        ("j.mjs", "const b = await chromium.connectOverCDP(u)", False),
        ("k.mjs", "// muon: 接続のみ\nconst b = await chromium.connectOverCDP(u)", True),
        ("l.mjs", "<td class=\"say\">x</td>", True),
        ("l2.mjs", "mark(\"say\", t); ev.push({k: \"say\", text})", True),
        ("m.py", "subprocess.run([\"say\", \"hello\"])", False),
        ("n.py", "# afplay は使わない\nprint(1)", True),
    ]
    ng = []
    for name, src, want_ok in cases:
        got_ok = not check_text(src, name)
        if got_ok != want_ok:
            ng.append(name)
    print(json.dumps({"cases": len(cases), "ng": ng, "ok": not ng}, ensure_ascii=False))
    return 0 if not ng else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--check-stdin" in a:
        # 関所（tools/stop_kanmon/muon_kanmon.mjs）から：標準入力の中身を、名前 a[次] のファイルとして見る
        i = a.index("--check-stdin")
        name = a[i + 1] if len(a) > i + 1 else "x.mjs"
        print(json.dumps(check_text(sys.stdin.read(), name), ensure_ascii=False))
        return
    if "--mimawari" in a:
        print(json.dumps(mimawari(kill="--dry" not in a), ensure_ascii=False, indent=1))
        return
    roots = [x for x in a if not x.startswith("--")] or None
    r = kanmon(roots, write=roots is None)
    print(json.dumps({"seen": r["seen"], "red": r["red"], "hits": r["hits"]}, ensure_ascii=False, indent=1))
    sys.exit(1 if r["red"] else 0)


if __name__ == "__main__":
    main()
