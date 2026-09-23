#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案内人に300問を投げて、機械で採点して、1周ぶんを1行残す。

  python3 tools/annai_mawasu.py --how live              # 本番を触る（★Macの上でしか動かない）
  python3 tools/annai_mawasu.py --how live --limit 30   # 短く試す
  python3 tools/annai_mawasu.py --how offline           # 手元の写しで回す（速い・何百周でも）

★AIを1回も呼ばない。課金0。
★採点は書かない。`tools/hantei.py` の saiten_annai() を呼ぶだけ（規則を2か所に書かない）。
★問は増やさない・減らさない（`status/annai_300.json` v1 固定）。

残すもの
  status/annai/<日付>/r<周>_<how>.json … 1問ずつの生データ（あとで読み返せる）
  status/annai_score.jsonl             … 1周＝1行。日時／✕の数／内訳／悪化したか

★1問終わるごとに保存する。最後にまとめて書くと、1回詰まった日が丸ごと消える。
"""
import argparse
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hantei  # noqa: E402  ★判定はここにしか無い

TOI = os.path.join(ROOT, "status", "annai_300.json")
OUTDIR = os.path.join(ROOT, "status", "annai")
SCORE = os.path.join(ROOT, "status", "annai_score.jsonl")
# ★案内人がいるのは joy-relief-station。1039で直した。
# （前は tamago2022.github.io/tamago-shinchoku を見ていた。そこに案内人はいないので、
#   入力欄が20秒見つからず「無反応(落ちた)」が積み上がるだけだった＝数字が嘘になる）
BASE = "https://joy-relief-station.lovable.app"
CONCIERGE_SEL = 'input[placeholder*="気分でも"]'


def log(s):
    print(time.strftime("%H:%M:%S "), s, flush=True)


def load_toi(limit=0):
    with open(TOI, encoding="utf-8") as f:
        d = json.load(f)
    qs = d["questions"]
    if limit:
        # ★間引くときも区分の比を崩さない（全体から等間隔で抜く）
        step = max(1, len(qs) // limit)
        qs = qs[::step][:limit]
    return qs


def next_round(how):
    n = 0
    if os.path.exists(SCORE):
        with open(SCORE, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("how") == how:
                    n = max(n, int(r.get("round", 0)))
    return n + 1


def prev_rate(how):
    last = None
    if os.path.exists(SCORE):
        with open(SCORE, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("how") == how:
                    last = r
    return last


# ── 本番を触る（★Macの上でしか動かない。サンドボックスからは外に出られない）──
def ask_live(tois, outpath, fixed=""):
    from playwright.sync_api import sync_playwright
    rows = []

    def save():
        tmp = outpath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"how": "live", "base": BASE, "fixed": fixed,
                       "rows": rows}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, outpath)

    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--disable-dev-shm-usage"])

        def fresh():
            ctx = br.new_context(viewport={"width": 390, "height": 844},
                                 user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 "
                                             "like Mac OS X) AppleWebKit/605.1.15"))
            p = ctx.new_page()
            p.goto(BASE + "/cover-guide", wait_until="domcontentloaded", timeout=60000)
            p.wait_for_timeout(2500)
            return ctx, p

        ctx, page = fresh()
        for i, t in enumerate(tois, 1):
            rec = {"q": t["q"], "区分": t["区分"]}
            ans = {"text": "", "lines": [], "error": ""}
            t0 = time.time()
            # ★このMacは混んでいる（load 90超の日がある）。混雑で落ちただけの回を
            #   「案内人が黙った」と数えると、数字が実力より悪くなる。
            #   だから落ちたら必ず1回だけ連れ直して、同じ問をもう一度投げる。
            for attempt in (1, 2):
                try:
                    page.wait_for_selector(CONCIERGE_SEL, timeout=20000)
                    before = set(x.strip() for x in
                                 page.inner_text("body", timeout=20000).split("\n")
                                 if x.strip())
                    page.fill(CONCIERGE_SEL, t["q"], timeout=15000)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(3000)
                    after = [x.strip() for x in
                             page.inner_text("body", timeout=20000).split("\n")
                             if x.strip()]
                    new = [l for l in after if l not in before]
                    ans["lines"] = new
                    ans["text"] = "\n".join(new)
                    ans["error"] = ""
                    break
                except Exception as ex:
                    ans["error"] = "%s: %s（%d回目）" % (
                        type(ex).__name__, str(ex)[:100], attempt)
                    try:
                        ctx.close()
                    except Exception:
                        pass
                    try:
                        ctx, page = fresh()
                    except Exception:
                        break
            rec["ans"] = ans
            rec["retried"] = bool(ans.get("error")) or "（2回目）" in ans.get("error", "")
            rec["seconds"] = round(time.time() - t0, 1)
            rec.update(hantei.saiten_annai(t, ans))
            rows.append(rec)
            if i % 10 == 0 or i == len(tois):
                save()
                log("  %d/%d %s" % (i, len(tois), rec["mark"]))
        save()
        br.close()
    return rows


# ── 手元の写しで回す（★速い。何百周でも0円）───────────────────────
def ask_offline(tois, outpath, fixed=""):
    """本番と同じ選び方を手元で再現して回す。
    ★まだ写しが無い（`tools/annai_mimi.py` が未着）なら、その1点だけ書いて止める。"""
    try:
        import annai_mimi
    except ImportError:
        print("★止めました：手元の写し tools/annai_mimi.py がまだありません。")
        print("  理由：本番の案内人の中身（ConciergeChat）をまだ取れていないため、")
        print("        『本番と同じ選び方』を手元で再現できません。")
        print("        当てずっぽうの写しで数字を出すと、その数字が嘘になります。")
        return None
    rows = []
    for t in tois:
        ans = annai_mimi.kotaeru(t["q"])
        rec = {"q": t["q"], "区分": t["区分"], "ans": ans}
        rec.update(hantei.saiten_annai(t, ans))
        rows.append(rec)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"how": "offline", "fixed": fixed, "rows": rows},
                  f, ensure_ascii=False, indent=1)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--how", default="live", choices=["live", "offline"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--fixed", default="", help="この周の前に直した1つ")
    a = ap.parse_args()

    tois = load_toi(a.limit)
    rnd = next_round(a.how)
    day = time.strftime("%Y-%m-%d")
    outdir = os.path.join(OUTDIR, day)
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, "r%02d_%s.json" % (rnd, a.how))
    log("%d問を %s に投げます（%d周目）" % (len(tois), a.how, rnd))

    try:
        rows = ask_live(tois, outpath, a.fixed) if a.how == "live" \
            else ask_offline(tois, outpath, a.fixed)
    except Exception:
        print(traceback.format_exc()[-1500:])
        return 2
    if rows is None:
        return 3

    m = hantei.saiten_annai_matome(rows)
    ku = hantei.saiten_annai_ku(rows, tois)
    prev = prev_rate(a.how)
    worse = bool(prev and m["ng_rate"] > prev.get("ng_rate", 1.0))

    line = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "round": rnd, "how": a.how,
        "where": BASE + "/cover-guide" if a.how == "live" else "tools/annai_mimi.py",
        "file": os.path.relpath(outpath, ROOT),
        "asked": m["asked"], "ng": m["ng"], "ng_rate": m["ng_rate"],
        "warn": m["warn"], "warn_rate": m["warn_rate"],
        "breakdown": m["breakdown"],
        "ku": {k: v["ng_rate"] for k, v in sorted(ku.items())},
        "fixed": a.fixed, "worse": worse,
        "prev_rate": prev.get("ng_rate") if prev else None,
    }
    with open(SCORE, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

    print("\n== %d周目（%s）==" % (rnd, a.how))
    print("トンチンカン率 %.1f%%（%d／%d問）%s"
          % (m["ng_rate"] * 100, m["ng"], m["asked"],
             "  ★赤：前の周より悪化" if worse else ""))
    if prev:
        print("  前の周 %.1f%% → 今回 %.1f%%"
              % (prev.get("ng_rate", 0) * 100, m["ng_rate"] * 100))
    for k, v in sorted(m["breakdown"].items(), key=lambda x: -x[1]):
        print("  %-14s %3d問" % (k, v))
    print("区分ごとの✕率：")
    for k, v in sorted(ku.items(), key=lambda x: -x[1]["ng_rate"]):
        print("  %-8s %5.1f%%（%d/%d）" % (k, v["ng_rate"] * 100, v["ng"], v["asked"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
