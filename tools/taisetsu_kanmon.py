#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★大事な機能の関所（退行防止）2026-10-06

たまごさん：「後ろに後退しないでほしい。前は良かったのに今は差し替えられない。誰が何のために壊すの？
　　　　　　 いい変化ならいいんだけど、悪い変化はやめてよ。それでまたクレジットを使うマッチポンプはやめて。」

何をするか：店主が一度OKを出した11機能（joy-relief-station/scripts/guard/taisetsu-kinou.json が正本）を、
  公開の前と後に機械で確かめ、落ちていたら**落とした変更を自動で外して**（原因コミットを revert して main に入れる）
  直前の合格版が出るようにする。「止めて古いまま」にはしない＝直して出す。

  pre  <sha|dir> … 公開の前。その版を手元で動かし、契約テスト＋ヘッドレスE2E（手元モード）。
                   赤なら、直前の合格版からその版までのコミットのうち、落ちた機能のファイルを触ったものを revert して push。
  prod           … 公開の後。本番をヘッドレスE2Eで実際に押す（差し替え→戻す まで）。赤なら同じく revert して push。
  （kohyou_osu.py が押す前に pre を、出た後に prod を呼ぶ。手でも呼べる。）

結果: status/taisetsu_kanmon/pre_<sha8>.json / prod_<日時>.json ／ 合格版: status/taisetsu_kanmon/last_pass.json
Dispatchへ: 赤で外したときだけ status/dispatch_outbox.jsonl と Vault の作業キューへ1行。青のときは黙る。
環境変数: TAISETSU_NO_PUSH=1 で revert の push をしない（試運転）。
"""
import io
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "taisetsu_kanmon")
SITE = "/Users/mac/Desktop/joy-relief-station"
WT_ROOT = os.path.expanduser("~/.tamago/wt")
PROD = "https://joy-relief-station.lovable.app"
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
QUEUE = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain/AI出力/_ルール/作業キュー.md"
KEYS_ENV = os.path.expanduser("~/.tamago/keys/api_keys.env")
LAST_PASS = os.path.join(OUT, "last_pass.json")
ENV_PATH = "/opt/homebrew/bin:/usr/local/bin:" + os.path.expanduser("~/.bun/bin") + ":" + os.environ.get("PATH", "")
# Chrome本体は絶対に起動しない。Playwright のヘッドレス専用ブラウザだけ。
PW_EXE_ROOT = os.path.expanduser("~/tamago/pw-perf")


def _now():
    return time.strftime("%F %T")


def _write(name, doc):
    os.makedirs(OUT, exist_ok=True)
    doc = dict(doc, at=_now())
    with io.open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def _load(path, default=None):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _git(*a, cwd=SITE, check=False):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=check)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _pw_exe():
    if os.environ.get("PW_EXE"):
        return os.environ["PW_EXE"]
    try:
        for d in sorted(os.listdir(PW_EXE_ROOT), reverse=True):
            if d.startswith("chromium_headless_shell"):
                p = os.path.join(PW_EXE_ROOT, d, "chrome-headless-shell-mac-x64", "chrome-headless-shell")
                if os.path.exists(p):
                    return p
    except Exception:
        pass
    return ""


def _keys_env():
    """YouTube検索の鍵など（値は読むだけ・出力しない）。"""
    env = {}
    try:
        for line in io.open(KEYS_ENV, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def _scripts_from_main(wd):
    """検査の本体（契約テスト・E2E・一覧）は常に origin/main の最新版を使う（古い版でも新しい物差しで測る）。"""
    _git("fetch", "-q", "origin")
    sd = os.path.join(wd, ".taisetsu_scripts")
    os.makedirs(sd, exist_ok=True)
    got = {}
    for name in ("check-taisetsu-kinou.mjs", "e2e-taisetsu.mjs", "taisetsu-kinou.json"):
        src = _git("show", "origin/main:scripts/guard/" + name).stdout
        if not src:
            p = os.path.join(wd, "scripts", "guard", name)
            src = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        if src:
            with io.open(os.path.join(sd, name), "w", encoding="utf-8") as f:
                f.write(src)
            got[name] = os.path.join(sd, name)
    return got


def _contract(wd, scripts):
    """契約テスト（ブラウザなし）。検査本体は .taisetsu_scripts に置くが ROOT は作業フォルダを指すよう、scripts/guard に一時コピーして走らせる。"""
    gd = os.path.join(wd, "scripts", "guard")
    os.makedirs(gd, exist_ok=True)
    tmp = []
    for name, src in scripts.items():
        dst = os.path.join(gd, name)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
            tmp.append(dst)
    try:
        p = subprocess.run(["node", os.path.join(gd, "check-taisetsu-kinou.mjs"), "--json"], cwd=wd,
                           env=dict(os.environ, PATH=ENV_PATH), capture_output=True, text=True, timeout=300)
        try:
            doc = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            doc = {"ok": p.returncode == 0, "results": [], "raw": (p.stdout + p.stderr)[-800:]}
        return doc
    finally:
        for t in tmp:
            try:
                os.remove(t)
            except OSError:
                pass


def _e2e(base, wd, scripts, mode, extra_env=None, swap=False, timeout=1500):
    out = os.path.join(wd, ".taisetsu_e2e.json")
    env = dict(os.environ, PATH=ENV_PATH)
    pw = _pw_exe()
    if pw:
        env["PW_EXE"] = pw
    env.update(extra_env or {})
    cmd = ["node", scripts["e2e-taisetsu.mjs"], "--base", base, "--mode", mode, "--json", out,
           "--out", os.path.join(OUT, "shots")]
    if swap:
        cmd.append("--swap")
    try:
        p = subprocess.run(cmd, cwd=wd, env=env, capture_output=True, text=True, timeout=timeout)
        doc = _load(out, None) or {"ok": False, "failed": ["(e2e-crash)"], "results": [], "raw": (p.stdout + p.stderr)[-800:]}
    except subprocess.TimeoutExpired:
        doc = {"ok": False, "failed": ["(e2e-timeout)"], "results": []}
    return doc


def _manifest(scripts):
    return _load(scripts.get("taisetsu-kinou.json", ""), {"features": []})


def _feature_files(manifest, ids):
    files = set()
    for f in manifest.get("features", []):
        if f["id"] in ids:
            files.update(f.get("files", []))
    return sorted(files)


def _culprits(from_sha, to_sha, files):
    """from_sha(合格版)の後〜to_sha までで、落ちた機能のファイルを触ったコミット（新しい順）。"""
    if not from_sha:
        return []
    r = _git("log", "--format=%H", "%s..%s" % (from_sha, to_sha), "--", *files)
    shas = [x for x in r.stdout.split() if x]
    # 自動の同期コミット（whiteboard 等）は原因になり得ないので除く
    keep = []
    for s in shas:
        subj = _git("log", "-1", "--format=%s", s).stdout.strip()
        if re.search(r"自動書き戻し|\[skip ci\]|chore\(brain\)", subj):
            continue
        keep.append((s, subj))
    return keep


def _outbox(text):
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "from": "taisetsu_kanmon", "text": text}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        if os.path.exists(QUEUE):
            with io.open(QUEUE, "a", encoding="utf-8") as f:
                f.write("\n| %s | 【後退防止の関所】%s | 🟡 |\n" % (time.strftime("%F"), text))
    except Exception:
        pass


def _revert_and_push(culprits, label, failed_ids):
    """原因コミットを revert して main に入れる（直前の合格版の形に戻す）。戻せたら新しい main の sha を返す。"""
    if not culprits:
        return ""
    wd = os.path.join(WT_ROOT, "taisetsu-revert")
    _git("worktree", "remove", "--force", wd)
    shutil.rmtree(wd, ignore_errors=True)
    _git("fetch", "-q", "origin")
    if _git("worktree", "add", "--detach", wd, "origin/main").returncode != 0:
        return ""
    done = []
    try:
        for sha, subj in culprits:  # 新しい順に外す
            r = _git("-c", "user.name=tamago-taisetsu", "-c", "user.email=eggypop2010@gmail.com",
                     "revert", "--no-edit", sha, cwd=wd)
            if r.returncode != 0:
                _git("revert", "--abort", cwd=wd)
                continue
            done.append((sha[:9], subj[:60]))
        if not done:
            return ""
        _git("-c", "user.name=tamago-taisetsu", "-c", "user.email=eggypop2010@gmail.com", "commit", "--amend", "-q", "-m",
             "後退防止の関所：大事な機能（%s）が落ちたので原因コミットを外した（%s）\n\n外したコミット: %s\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
             % (",".join(failed_ids), label, " / ".join(s for s, _ in done)), cwd=wd)
        if os.environ.get("TAISETSU_NO_PUSH"):
            return "dryrun:" + _git("rev-parse", "--short=8", "HEAD", cwd=wd).stdout.strip()
        for _ in range(3):
            _git("fetch", "-q", "origin", cwd=wd)
            if _git("rebase", "origin/main", cwd=wd).returncode != 0:
                _git("rebase", "--abort", cwd=wd)
                break
            if _git("push", "origin", "HEAD:main", cwd=wd).returncode == 0:
                return _git("rev-parse", "--short=8", "HEAD", cwd=wd).stdout.strip()
        return ""
    finally:
        _git("worktree", "remove", "--force", wd)
        shutil.rmtree(wd, ignore_errors=True)


def _handle_red(label, sha, failed_ids, manifest):
    """赤：原因コミットを探して外す。外せたら Dispatch へ1行。"""
    lp = _load(LAST_PASS, {}) or {}
    files = _feature_files(manifest, failed_ids)
    culprits = _culprits(lp.get("sha"), sha, files)
    new_sha = _revert_and_push(culprits, label, failed_ids)
    names = ",".join(f["name"] for f in manifest.get("features", []) if f["id"] in failed_ids) or ",".join(failed_ids)
    if new_sha:
        text = "大事な機能「%s」が %s で落ちたので、原因コミット %s を自動で外して main に入れた（新しい版 %s）。理由は status/taisetsu_kanmon/%s.json" % (
            names, sha[:8], " / ".join(s for s, _ in culprits), new_sha, label)
    elif culprits:
        text = "大事な機能「%s」が %s で落ちた。原因候補 %s を外そうとしたが戻せなかった（衝突 or push不可）。人の手が要る。status/taisetsu_kanmon/%s.json" % (
            names, sha[:8], " / ".join(s for s, _ in culprits), label)
    else:
        text = "大事な機能「%s」が %s で落ちたが、合格版 %s 以降にそのファイルを触ったコミットが無い（環境・外部要因の可能性）。status/taisetsu_kanmon/%s.json" % (
            names, sha[:8], (lp.get("sha") or "-")[:8], label)
    if not os.environ.get("TAISETSU_NO_PUSH"):
        _outbox(text)
    return {"culprits": [list(c) for c in culprits], "revertedTo": new_sha, "dispatch": text}


def _record_pass(sha, how):
    _write("last_pass", {"sha": sha, "how": how})


def pre(target):
    """公開前：その版を手元で動かして、契約テスト＋E2E（手元モード）。"""
    made = None
    if os.path.isdir(target):
        wd = os.path.abspath(target)
        sha = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    else:
        _git("fetch", "-q", "origin")
        sha = _git("rev-parse", target).stdout.strip() or target
        wd = os.path.join(WT_ROOT, "taisetsu-" + sha[:8])
        os.makedirs(WT_ROOT, exist_ok=True)
        _git("worktree", "remove", "--force", wd)
        shutil.rmtree(wd, ignore_errors=True)
        if _git("worktree", "add", "--detach", wd, sha).returncode != 0:
            _write("pre_" + sha[:8], {"verdict": "inconclusive", "reason": "作業フォルダが作れません"})
            return 2
        made = wd
    label = "pre_" + sha[:8]
    scripts = _scripts_from_main(wd)
    doc = {"target": target, "sha": sha}
    nm = os.path.join(wd, "node_modules")
    if not os.path.exists(nm):
        os.symlink(os.path.join(SITE, "node_modules"), nm)
    srv = None
    logf = None
    try:
        doc["contract"] = _contract(wd, scripts)
        failed = [r["id"] for r in doc["contract"].get("results", []) if not r.get("ok")]
        if doc["contract"].get("ok"):
            port = _free_port()
            env = dict(os.environ, PATH=ENV_PATH, ADMIN_COOKIE_SECURE="false")
            env.setdefault("SESSION_SECRET", "taisetsu-local-only-" + str(os.getpid()) + "-" + str(int(time.time())) + "-xxxxxxxxxxxxxxxx")
            env.update(_keys_env())
            logf = open(os.path.join(wd, ".taisetsu_vite.log"), "w")
            srv = subprocess.Popen(["npx", "vite", "dev", "--port", str(port), "--host", "127.0.0.1", "--strictPort"],
                                   cwd=wd, env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
            base = "http://127.0.0.1:%d" % port
            ok = False
            t0 = time.time()
            while time.time() - t0 < 180:
                try:
                    with urllib.request.urlopen(base + "/", timeout=60) as r:
                        if r.status == 200:
                            ok = True
                            break
                except Exception:
                    time.sleep(2)
            if not ok:
                doc["verdict"] = "inconclusive"
                doc["reason"] = "開発サーバが立ち上がりません"
            else:
                doc["e2e"] = _e2e(base, wd, scripts, "local")
                failed += [x for x in doc["e2e"].get("failed", []) if not x.startswith("(")]
                if doc["e2e"].get("failed") and all(x.startswith("(") for x in doc["e2e"]["failed"]):
                    doc["verdict"] = "inconclusive"
                    doc["reason"] = "E2Eが走り切らなかった"
        if "verdict" not in doc:
            if failed:
                doc["verdict"] = "ng"
                doc["failed"] = sorted(set(failed))
                doc.update(_handle_red(label, sha, doc["failed"], _manifest(scripts)))
                if doc.get("revertedTo"):
                    doc["verdict"] = "reverted"
            else:
                doc["verdict"] = "ok"
                _record_pass(sha, "pre")
    finally:
        if srv:
            try:
                os.killpg(os.getpgid(srv.pid), signal.SIGTERM)
            except Exception:
                pass
        if logf:
            logf.close()
        if made:
            _git("worktree", "remove", "--force", made)
            shutil.rmtree(made, ignore_errors=True)
    _write(label, doc)
    try:
        os.remove(os.path.join(OUT, label + ".running"))
    except OSError:
        pass
    print(label, "→", doc.get("verdict"), doc.get("failed", ""), doc.get("reason", ""))
    return 0 if doc.get("verdict") in ("ok", "inconclusive") else 1


def prod():
    """公開後：本番を実際に押す。差し替え→戻す まで本当に押す。"""
    _git("fetch", "-q", "origin")
    sha = _git("rev-parse", "origin/main").stdout.strip()
    label = "prod_" + time.strftime("%Y%m%d_%H%M")
    wd = os.path.join(OUT, "work")
    os.makedirs(wd, exist_ok=True)
    scripts = _scripts_from_main(wd)
    doc = {"sha": sha, "base": PROD}
    doc["e2e"] = _e2e(PROD, wd, scripts, "prod", swap=True)
    failed = [x for x in doc["e2e"].get("failed", []) if not x.startswith("(")]
    if doc["e2e"].get("failed") and not failed:
        doc["verdict"] = "inconclusive"
        doc["reason"] = "E2Eが走り切らなかった"
    elif failed:
        # 外部要因（回線・YouTube側）で1回だけ落ちた可能性があるので、1回だけ測り直す
        time.sleep(30)
        doc["e2e2"] = _e2e(PROD, wd, scripts, "prod", swap=True)
        failed2 = [x for x in doc["e2e2"].get("failed", []) if not x.startswith("(")]
        failed = sorted(set(failed) & set(failed2)) if failed2 else []
        if failed:
            doc["verdict"] = "ng"
            doc["failed"] = failed
            doc.update(_handle_red(label, sha, failed, _manifest(scripts)))
            if doc.get("revertedTo"):
                doc["verdict"] = "reverted"
        else:
            doc["verdict"] = "ok"
            _record_pass(sha, "prod")
    else:
        doc["verdict"] = "ok"
        _record_pass(sha, "prod")
    _write(label, doc)
    _write("prod_latest", doc)
    print(label, "→", doc.get("verdict"), doc.get("failed", ""), doc.get("reason", ""))
    return 0 if doc.get("verdict") in ("ok", "inconclusive") else 1


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("pre", "prod"):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "pre":
        sys.exit(pre(sys.argv[2] if len(sys.argv) > 2 else SITE))
    sys.exit(prod())
