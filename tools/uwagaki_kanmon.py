#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同時に動く子どうしで、変更を上書きし合わない関所（2026-10-25・たまごさん指示）。

実例（2026-10-25 朝・joy-relief-station）：
  648115b03（検索・関連）が古い写しのファイルを丸ごと載せたため、直前の 9de7ab482（救急箱）の5行が消えた
  → 837cbb0f8 で戻した。その 837cbb0f8 がまた古い写しで、ヴィエンナの公式Xボタンを消した → 411b2b2e9 で戻した。
  原因は毎回同じ：「自分が作業を始めた時点のファイル」を、取り直さずに main へ丸ごと載せた。

決まり：公開（push）の直前に main を取り直し、自分の差分だけを最新の main に載せる。
  丸ごと上書きしない。他の子が足した行を消さない（消すなら commit の説明にその理由を書く）。

使い方
  python3 tools/uwagaki_kanmon.py --push --repo <リポ> --msg "説明" 変えたファイル...
      作業場の各ファイルについて「作業を始めた時点（--base、既定は HEAD と origin/main の分かれ目）→作業場」の差分だけを、
      取り直した origin/main に3方向で重ねる（git merge-file）。ぶつかったら止める（exit 2）。
      作業場・HEAD・ブランチには触らない（一時の索引で commit を作って push）。押し負けたら取り直して3回までやり直す。
  python3 tools/uwagaki_kanmon.py --check <commit> --repo <リポ> [--hours 12]
      その commit が消した行のうち、直近 N 時間に「別の commit」が足した行を数える。あれば exit 2（上書きの疑い）。
  python3 tools/uwagaki_kanmon.py --mimawari      心臓から1時間に1回。直近6時間の main を見て、疑いを status/public/uwagaki_kanmon.json と Dispatch へ
  python3 tools/uwagaki_kanmon.py --self-test
安全：GitHub への push 以外は手元の git だけ。課金0。
"""
import argparse, os, shutil, subprocess, sys, tempfile, time


def g(repo, *a, env=None, check=True, inp=None):
    p = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, env=env, input=inp)
    if check and p.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(a), p.stderr.strip()[:400]))
    return p.stdout


def show(repo, rev, path):
    p = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (rev, path)], capture_output=True)
    return p.stdout if p.returncode == 0 else None


def sashibun_push(repo, files, msg, base=None, remote="origin", branch="main", tries=3, push=True):
    tmp = tempfile.mkdtemp(prefix="uwagaki-")
    try:
        if not base:
            g(repo, "fetch", "-q", remote, branch)
            base = g(repo, "merge-base", "HEAD", "%s/%s" % (remote, branch)).strip()
        for n in range(tries):
            g(repo, "fetch", "-q", remote, branch)
            head = g(repo, "rev-parse", "%s/%s" % (remote, branch)).strip()
            idx = os.path.join(tmp, "idx")
            env = dict(os.environ, GIT_INDEX_FILE=idx)
            if os.path.exists(idx):
                os.remove(idx)
            g(repo, "read-tree", head, env=env)
            for f in files:
                mine = os.path.join(repo, f)
                b, t = show(repo, base, f), show(repo, head, f)
                o = os.path.join(tmp, "o"); bb = os.path.join(tmp, "b"); tt = os.path.join(tmp, "t")
                shutil.copyfile(mine, o)
                open(bb, "wb").write(b or b""); open(tt, "wb").write(t or b"")
                if t is not None and b != t:  # 自分が始めた後に他の子が変えた → 差分だけ重ねる
                    r = subprocess.run(["git", "merge-file", "-L", "mine", "-L", "base", "-L", "main", o, bb, tt], capture_output=True)
                    if r.returncode != 0:
                        print("UWAGAKI_KANMON: STOP ｜ %s が他の子の変更とぶつかった（丸ごと上書きはしない。取り直して手で直す）" % f)
                        return 2
                # ★2026-10-27 衝突の印（<<<<<<< ======= >>>>>>>）が残ったファイルは載せない
                #   実例：553c424c0 で package.json に stash pop の衝突の印が入ったまま push され、prebuild が壊れた（69a5d1853 で直した）
                if conflict_marks(open(o, "rb").read()):
                    print("UWAGAKI_KANMON: STOP ｜ %s に衝突の印（<<<<<<< / >>>>>>>）が残っている。載せない" % f)
                    return 2
                blob = g(repo, "hash-object", "-w", o).strip()
                g(repo, "update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, f), env=env)
            tree = g(repo, "write-tree", env=env).strip()
            if tree == g(repo, "rev-parse", head + "^{tree}").strip():
                print("UWAGAKI_KANMON: 変更なし（もう main に入っている）")
                return 0
            c = g(repo, "commit-tree", tree, "-p", head, "-m", msg).strip()
            if check_commit(repo, c, quiet=True, base=base):
                print("UWAGAKI_KANMON: STOP ｜ 他の子が直近に足した行を消す差分になっている（--check %s で中身）" % c[:9])
                return 2
            if not push:
                print("UWAGAKI_KANMON: OK %s" % c)
                return 0
            p = subprocess.run(["git", "-C", repo, "push", remote, "%s:refs/heads/%s" % (c, branch)], capture_output=True, text=True)
            if p.returncode == 0:
                print("UWAGAKI_KANMON: PUSHED %s（main %s の上に差分だけ）" % (c[:9], head[:9]))
                return 0
            time.sleep(2 + n * 3)
        print("UWAGAKI_KANMON: STOP ｜ %d回押し負けた" % tries)
        return 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def conflict_marks(data):
    import re
    return bool(re.search(rb"(?m)^(<{7}|>{7})( |$)", data or b"")) and bool(re.search(rb"(?m)^={7}$", data or b""))


def check_commit(repo, c, hours=12, quiet=False, base=None):
    """c が「丸ごと消した」行（置き換えでなく削除だけの塊）のうち、直近 hours 時間に別の commit が足した行の一覧。
    base を渡すと、base までに入っていた行（自分が見えていた行）は数えない。commit の説明に「消す理由:」があれば通す。"""
    if "消す理由:" in g(repo, "log", "-1", "--format=%B", c):
        return []
    now = int(g(repo, "log", "-1", "--format=%ct", c).strip() or time.time())
    hits = []
    diff = g(repo, "diff", "-U0", c + "^", c)
    path = None
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            path = line[6:]
        elif line.startswith("--- /dev/null"):
            path = None
        elif line.startswith("@@") and path:
            old = line.split()[1][1:]
            new = line.split()[2][1:]
            s, _, n = old.partition(",")
            s, n = int(s), int(n or 1)
            if n == 0 or new.partition(",")[2] != "0":  # 置き換えは数えない（削除だけの塊を見る）
                continue
            bl = g(repo, "blame", "--porcelain", "-L", "%d,%d" % (s, s + n - 1), c + "^", "--", path, check=False)
            cur = None; times = {}
            for b in bl.splitlines():
                parts = b.split()
                if len(parts) >= 3 and len(parts[0]) == 40:
                    cur = parts[0]
                elif b.startswith("committer-time ") and cur:
                    times[cur] = int(b.split()[1])
                elif b.startswith("\t") and cur:
                    t = times.get(cur, 0)
                    seen = base and subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", cur, base]).returncode == 0
                    if now - t < hours * 3600 and b.strip() and not seen:
                        hits.append((path, cur[:9], b.strip()[:100]))
    if hits and not quiet:
        for h in hits[:30]:
            print("消える行 %s（%s が足した）: %s" % h)
    return hits


def mimawari(repo, hours=6):
    """心臓から（中で1時間に1回に間引く）。origin/main に直近 hours 時間に入った commit を1本ずつ --check し、
    上書きの疑いを status/public/uwagaki_kanmon.json に。新しく見つけたものだけ Dispatch に1行。"""
    import json
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stamp = os.path.join(here, "status", ".uwagaki_mimawari_at")
    if os.path.exists(stamp) and time.time() - os.path.getmtime(stamp) < 3600:
        return 0
    open(stamp, "w").close()
    out = os.path.join(here, "status", "public", "uwagaki_kanmon.json")
    old = {}
    try:
        old = json.load(open(out))
    except Exception:
        pass
    seen = set(old.get("mitsuketa", {}).keys())
    g(repo, "fetch", "-q", "origin", "main", check=False)
    revs = g(repo, "log", "--no-merges", "--since=%d hours ago" % hours, "--format=%H %s", "origin/main", check=False).splitlines()
    found = dict(old.get("mitsuketa", {}))
    new = []
    for r in revs:
        h, _, subj = r.partition(" ")
        if h[:9] in found:
            continue
        hits = check_commit(repo, h, quiet=True)
        if hits:
            found[h[:9]] = {"subject": subj[:120], "kieta": [{"file": f, "tashita": c, "gyou": l} for f, c, l in hits[:10]]}
            if h[:9] not in seen:
                new.append((h[:9], subj[:80], hits))
    found = dict(list(found.items())[-50:])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"_": "同時に動く子どうしの上書きの見張り（tools/uwagaki_kanmon.py）", "at": time.strftime("%F %T"),
               "mita": len(revs), "mitsuketa": found}, open(out, "w"), ensure_ascii=False, indent=1)
    for h, subj, hits in new:
        line = {"ts": time.strftime("%FT%T+09:00"), "n": "uwagaki-" + h, "type": "uwagaki_utagai",
                "title": "上書きの疑い：%s が他の子の行を%d行消した" % (h, len(hits)),
                "message": "%s「%s」が %s の行を消した（例：%s）。戻すか確かめる：python3 tools/uwagaki_kanmon.py --check %s" % (h, subj, hits[0][1], hits[0][2][:60], h)}
        open(os.path.join(here, "status", "dispatch_outbox.jsonl"), "a").write(json.dumps(line, ensure_ascii=False) + "\n")
    print("UWAGAKI_MIMAWARI: 見た %d本・新しい疑い %d本" % (len(revs), len(new)))
    return 0


def self_test():
    ok = True
    d = tempfile.mkdtemp(prefix="uwagaki-test-")
    try:
        origin = os.path.join(d, "origin.git"); a = os.path.join(d, "a"); b = os.path.join(d, "b")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", origin], check=True)
        for r in (a,):
            subprocess.run(["git", "clone", "-q", origin, r], check=True, capture_output=True)
        def cfg(r):
            g(r, "config", "user.email", "t@t"); g(r, "config", "user.name", "t")
        cfg(a)
        open(os.path.join(a, "f.txt"), "w").write("1\n2\n3\n4\n5\n")
        g(a, "add", "."); g(a, "commit", "-qm", "base"); g(a, "push", "-q", "origin", "HEAD:main")
        subprocess.run(["git", "clone", "-q", origin, b], check=True, capture_output=True); cfg(b)
        # 子A：救急箱の行を足して push
        open(os.path.join(a, "f.txt"), "w").write("1\n2\nkyukyubako\n3\n4\n5\n")
        g(a, "commit", "-qam", "kyukyubako"); g(a, "push", "-q", "origin", "HEAD:main")
        # 子B：古い写しで5行目だけ変えた
        open(os.path.join(b, "f.txt"), "w").write("1\n2\n3\n4\nFIVE\n")
        rc = sashibun_push(b, ["f.txt"], "five", base=g(b, "rev-parse", "HEAD").strip())
        g(a, "pull", "-q", "origin", "main")
        got = open(os.path.join(a, "f.txt")).read()
        r1 = rc == 0 and "kyukyubako" in got and "FIVE" in got
        print(("OK " if r1 else "NG ") + "差分だけ載せる：他の子の行が残り、自分の変更も入る")
        ok &= r1
        # 古い写しを丸ごと載せた commit は --check で捕まる
        open(os.path.join(a, "f.txt"), "w").write("1\n2\n3\n4\nFIVE\n")
        g(a, "commit", "-qam", "stale overwrite")
        r2 = bool(check_commit(a, "HEAD", quiet=True))
        print(("OK " if r2 else "NG ") + "丸ごと上書き（救急箱が消える）を --check が見つける")
        ok &= r2
        # ふつうの変更は捕まらない
        open(os.path.join(a, "f.txt"), "w").write("1\n2\n3\n4\nFIVE\n6\n")
        g(a, "commit", "-qam", "add 6")
        r3 = not check_commit(a, "HEAD", quiet=True)
        print(("OK " if r3 else "NG ") + "足すだけの変更は通る")
        ok &= r3
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("SELF_TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true"); ap.add_argument("--check", default="")
    ap.add_argument("--repo", default=os.path.expanduser("~/Desktop/joy-relief-station"))
    ap.add_argument("--msg", default=""); ap.add_argument("--base", default=None)
    ap.add_argument("--hours", type=float, default=12); ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--mimawari", action="store_true")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    if a.mimawari:
        sys.exit(mimawari(a.repo))
    if a.check:
        h = check_commit(a.repo, a.check, a.hours)
        print("UWAGAKI_KANMON:", "STOP（上書きの疑い %d行）" % len(h) if h else "PASS")
        sys.exit(2 if h else 0)
    if a.push:
        if not a.files or not a.msg:
            sys.exit("--push には --msg と ファイル が要る")
        sys.exit(sashibun_push(a.repo, a.files, a.msg, base=a.base))
    ap.print_help()
