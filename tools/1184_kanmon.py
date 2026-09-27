#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1184号【オリジナル禁止の関所・申告口】2026-09-29

たまごさん（恒久ルール／憲法）：
  「一流に倣って、先人に倣って、常に。オリジナル禁止、憲法で禁止です。」

tools/stop_kanmon/1184_original_kinshi.mjs（PreToolUse）が、
新しい実行物を Write する前にこれを要求する。

  python3 tools/1184_kanmon.py shirabe --nani "…" --koushiki "…" --mcp "…" \
      --sample "…" --jitsurei "…" --gaibu "…" --ketsuron sonomama
  python3 tools/1184_kanmon.py list
  python3 tools/1184_kanmon.py clear
  python3 tools/1184_kanmon.py --shiken     ← 逆テスト（違反を仕込んで赤が出るか見る）

★「似せる」は不合格、「そのまま」が合格。
  --ketsuron sonomama   公式・実例を **そのまま** 使う（本線）
  --ketsuron tsukaenai  ①〜④が全部✕。このときだけ自分で考えてよい。
                        ✕の証拠（「無い」「対応していない」「見つからない」等）が
                        ①〜④の全部に書かれていないと受け付けない。
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HYO = os.path.join(REPO, "status", "original_kinshi")
HOOK = os.path.join(HERE, "stop_kanmon", "1184_original_kinshi.mjs")
TTL = 86400

NEED = [
    ("koushiki", "① 公式ドキュメントの目次を通しで読んだか"),
    ("mcp", "① MCPはあるか（毎回確認する）"),
    ("sample", "② 公式サンプルをそのまま移植できないか"),
    ("jitsurei", "③ 金をかけずに同じことをやっている実例をお手本にできないか"),
    ("gaibu", "④ 外部AIに白紙で聞いたか"),
]

# ✕だった証拠として認める言い回し（これが無い「無理でした」は受け付けない）
BATSU = ["無い", "ない", "無かっ", "なかっ", "見つから", "対応していない", "非対応",
         "存在しない", "×", "✕", "該当なし", "ヒット0", "0件"]
# 「似せる」を自白している言い回し（sonomama のときに出てきたら不合格）
NISERU = ["似せ", "参考に", "独自", "自作", "オリジナル", "ベースに", "アレンジ"]


def _say(*a):
    print(*a)


def shirabe(a):
    missing = [lbl for k, lbl in NEED if len(str(getattr(a, k) or "").strip()) < 4]
    if missing:
        _say("★受け付けません。埋まっていない段があります：")
        for m in missing:
            _say("   - " + m)
        _say("  順番に埋めること。飛ばした段があると⑤には行けません。")
        return 2

    vals = {k: str(getattr(a, k)).strip() for k, _ in NEED}

    if a.ketsuron == "tsukaenai":
        nashi = [lbl for k, lbl in NEED if not any(b in vals[k] for b in BATSU)]
        if nashi:
            _say("★受け付けません。「自分で考えてよい」は①〜④が全部✕のときだけです。")
            _say("  ✕だった証拠が書かれていない段：")
            for m in nashi:
                _say("   - " + m)
            _say("  『探したが無かった』『対応していない』など、"
                 "探して空振りした事実を書くこと。")
            return 2
    else:
        jihaku = [w for w in NISERU if any(w in v for v in vals.values())]
        if jihaku:
            _say("★受け付けません。『そのまま』ではなく『似せる』になっています：%s"
                 % "／".join(jihaku))
            _say("  似せるのは不合格。そのまま移植できないなら --ketsuron tsukaenai で、")
            _say("  ①〜④が全部✕だった証拠を書いてください。")
            return 2

    os.makedirs(HYO, exist_ok=True)
    tid = "hyo-%d" % int(time.time())
    rec = {"at": time.time(), "id": tid, "nani": a.nani, "ketsuron": a.ketsuron}
    rec.update(vals)
    with io.open(os.path.join(HYO, tid + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    _say("通しました（%s）。%d秒間だけ有効です。" % (tid, TTL))
    _say("  結論：%s" % ("公式・実例をそのまま使う" if a.ketsuron == "sonomama"
                      else "①〜④が全部✕だったので自分で考える"))
    _say("  票：status/original_kinshi/%s.json" % tid)
    return 0


def listing():
    if not os.path.isdir(HYO):
        _say("票はありません")
        return 0
    now, n = time.time(), 0
    for name in sorted(os.listdir(HYO)):
        if not name.endswith(".json"):
            continue
        try:
            o = json.load(io.open(os.path.join(HYO, name), encoding="utf-8"))
        except Exception:
            continue
        age = now - float(o.get("at", 0))
        _say("%s  %s  [%s]  (%.0f分前 %s)" % (
            name, o.get("nani", ""), o.get("ketsuron", ""), age / 60,
            "有効" if age < TTL else "期限切れ"))
        n += 1
    if not n:
        _say("票はありません")
    return 0


def clear():
    if os.path.isdir(HYO):
        for name in os.listdir(HYO):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(HYO, name))
                except Exception:
                    pass
    _say("票を消しました")
    return 0


# ── 逆テスト ──────────────────────────────────────────────────────
def _node():
    """nodeの場所。心臓経由（launchd）だとPATHが痩せていて `node` が引けない。"""
    import shutil
    p = shutil.which("node")
    if p:
        return p
    for c in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node",
              os.path.expanduser("~/.volta/bin/node")):
        if os.path.exists(c):
            return c
    for base in (os.path.expanduser("~/.nvm/versions/node"),):
        if os.path.isdir(base):
            for v in sorted(os.listdir(base), reverse=True):
                c = os.path.join(base, v, "bin", "node")
                if os.path.exists(c):
                    return c
    return "node"


def _hook(payload):
    p = subprocess.run([_node(), HOOK], input=json.dumps(payload).encode("utf-8"),
                       capture_output=True, timeout=30)
    return p.returncode, (p.stderr or b"").decode("utf-8", "replace")


def _put_hyo(name, **kw):
    os.makedirs(HYO, exist_ok=True)
    rec = {"at": time.time(), "id": name, "nani": "試験", "ketsuron": "sonomama"}
    rec.update(kw)
    with io.open(os.path.join(HYO, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)


def _rm_hyo():
    if not os.path.isdir(HYO):
        return
    for n in os.listdir(HYO):
        if n.startswith("_shiken"):
            try:
                os.remove(os.path.join(HYO, n))
            except Exception:
                pass


FULL = {"koushiki": "目次を通読した", "mcp": "MCPを探したが無かった",
        "sample": "公式サンプルをそのまま移植", "jitsurei": "同じことをやっている人の実装",
        "gaibu": "白紙で聞いた答え"}


def shiken():
    _rm_hyo()
    tmp_new = os.path.join(REPO, "status", "_shikenA_new.py")
    tmp_old = os.path.join(REPO, "status", "_shikenA_old.py")
    for p in (tmp_new, tmp_old):
        if os.path.exists(p):
            os.remove(p)
    io.open(tmp_old, "w").write("# already here\n")

    ng, rows = 0, []

    def t(name, payload, want_rc, setup=None):
        nonlocal ng
        _rm_hyo()
        if setup:
            setup()
        rc, err = _hook(payload)
        ok = (rc == want_rc)
        if not ok:
            ng += 1
        rows.append("%s %-46s 期待rc=%d 実測rc=%d" % ("○" if ok else "★NG", name, want_rc, rc))

    W = lambda p: {"tool_name": "Write", "tool_input": {"file_path": p}, "session_id": "shiken"}

    t("票なしで新しい .py を Write する", W(tmp_new), 2)
    t("票なしで新しい .mjs を Write する",
      W(os.path.join(REPO, "status", "_shikenA_new.mjs")), 2)
    t("票なしで .md を Write する（止めない）",
      W(os.path.join(REPO, "status", "_shikenA.md")), 0)
    t("既にあるファイルを Write（作り直しは新方式ではない）", W(tmp_old), 0)
    t("Edit は止めない",
      {"tool_name": "Edit", "tool_input": {"file_path": tmp_new}, "session_id": "shiken"}, 0)
    t("Read は止めない",
      {"tool_name": "Read", "tool_input": {"file_path": tmp_new}, "session_id": "shiken"}, 0)
    t("心臓へ渡す一発物は止めない",
      W(os.path.join(REPO, "status", "oneshot", "pending", "_shiken.sh")), 0)
    t("5段階のうち1つ欠けた票では通さない", W(tmp_new), 2,
      setup=lambda: _put_hyo("_shiken_kake", **{k: v for k, v in FULL.items() if k != "gaibu"}))
    t("5段階そろった票なら通す", W(tmp_new), 0,
      setup=lambda: _put_hyo("_shiken_full", **FULL))
    t("期限切れの票では通さない", W(tmp_new), 2,
      setup=lambda: (_put_hyo("_shiken_furui", **FULL),
                     json.dump({"at": time.time() - TTL - 60, "ketsuron": "sonomama", **FULL},
                               io.open(os.path.join(HYO, "_shiken_furui.json"), "w",
                                       encoding="utf-8"))))

    # CLI側の逆テスト（票を作らせない側）
    class A:
        pass
    a = A()
    a.nani = "試験"
    for k, v in FULL.items():
        setattr(a, k, v)
    a.ketsuron = "tsukaenai"
    rc = shirabe(a)
    rows.append("%s %-46s 期待rc=2 実測rc=%d" % ("○" if rc == 2 else "★NG",
                "✕の証拠が無いのに『自分で考える』", rc))
    if rc != 2:
        ng += 1
    a.ketsuron = "sonomama"
    a.sample = "公式サンプルを参考に自作した"
    rc = shirabe(a)
    rows.append("%s %-46s 期待rc=2 実測rc=%d" % ("○" if rc == 2 else "★NG",
                "『似せた』と書いてあるのに『そのまま』", rc))
    if rc != 2:
        ng += 1

    _rm_hyo()
    for p in (tmp_new, tmp_old, os.path.join(REPO, "status", "_shikenA.md")):
        if os.path.exists(p):
            os.remove(p)

    _say("")
    _say("【1184号・逆テスト】" + ("PASS（NG 0件）" if ng == 0 else "★FAIL（NG %d件）" % ng))
    for r in rows:
        _say("  " + r)
    return 0 if ng == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shiken", action="store_true", help="逆テストを走らせる")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("shirabe")
    s.add_argument("--nani", required=True)
    s.add_argument("--koushiki", default="")
    s.add_argument("--mcp", default="")
    s.add_argument("--sample", default="")
    s.add_argument("--jitsurei", default="")
    s.add_argument("--gaibu", default="")
    s.add_argument("--ketsuron", choices=["sonomama", "tsukaenai"], default="sonomama")
    sub.add_parser("list")
    sub.add_parser("clear")
    a = ap.parse_args()
    if a.shiken:
        return shiken()
    if a.cmd == "shirabe":
        return shirabe(a)
    if a.cmd == "clear":
        return clear()
    return listing()


if __name__ == "__main__":
    sys.exit(main())
