#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1024番：棚のものに「いつ入荷したか」を持たせる。

■ なぜ要るか
  たまごさん 2026-09-22：
    「最近入荷したなかでも面白いのがありますよ、って案内人に言わせたい。」

  1023番は**言わせなかった。**理由は正しい：**棚のデータに入荷日が1つも無かった。**
  裏の取れない「最近入った」は関所違反。だから言わせないままにした。

■ 入荷日はどこにあるか（でっち上げない）
  棚の正本は joy-relief-station の `src/lib/coverGuide.ts`。**これはgitで管理されている。**
  実測：このファイルに **759本のコミット**がある。コミットの題名にそのまま
  「一括仕入れ第1便：1,514曲を反映」「仕入れ：『ウイスキーが、お好きでしょ』原曲を入れる」
  と書いてある。**入荷日は最初から全部あった。誰も引いていなかっただけ。**

  だから推測しない。**「その `id:` の行が、どのコミットで初めて足されたか」**を引く。
  それがその曲・その人の入荷日。

■ 引き方（Macが重くならないように）
  6.3MBのファイルを759回まるごと読むと 4.7GB 読むことになる。やらない。
  `git log -p -U0` で**足された行だけ**を古い順に流す。1回で済む。

■ 取れなかったものは「不明」
  いちばん古いコミット（2026-06-13）より前から居るものは、その日に「初めて足された」
  ように見えるが、本当にその日に入荷したのかは分からない。**だから「不明」と書く。**
  出力の `d` に載っていない＝入荷日が分からない＝「最近ではない」として扱う。

■ 「最近」は何日か（曖昧にしない。実測で決めた）
  棚に物が入るのは「便」でまとまって来る。実測（棚の34,240曲の入荷日）：

      7/30  5,910曲    8/06  5,090曲    8/12     11曲
      7/31  5,633曲    8/07    701曲    8/15    143曲  ← いちばん新しい
      8/01    248曲    8/09  2,710曲

  だから日数で切るとこうなる：
      直近30日 →      0曲   案内人は何も言えない
      直近45日 →  2,915曲   棚の8.5%。**直近2便ぶん**がちょうど入る ← これにした
      直近60日 → 21,024曲   棚の6割。これを「最近」と呼んだら水道水

  ★45日のあいだに1件も入っていなければ、案内人は**何も言わない**（自動で黙る）。

出力（2つ）
  status/nyuka/daicho.json                  … 入荷台帳の正本（全件・gitには乗らない）
  share/check/assets/953-songs/nyuka.json   … ブラウザに渡すぶん。**窓の中だけ**（約12KB）
"""
import collections
import datetime
import io
import json
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
JOY = pathlib.Path(os.environ.get("JOY_REPO", "/Users/mac/Desktop/joy-relief-station"))
TARGET = "src/lib/coverGuide.ts"
OUT = REPO / "share" / "check" / "assets" / "953-songs" / "nyuka.json"
DAICHO = REPO / "status" / "nyuka" / "daicho.json"
HEAD = REPO / "share" / "check" / "assets" / "953-songs" / "head.json"
SEKISHO = REPO / "status" / "nyuka" / "done"

# ★「最近」＝直近45日。上の■に実測の根拠を書いてある。ここ1か所だけを直せば全部変わる。
MADO = 45

RE_ID = re.compile(r'^\+.*?\bid:\s*"([^"]+)"')
RE_MARK = re.compile(r"^\x00([0-9a-f]{7,40}) (\d{9,11})$")


def hiku():
    """(id -> 初めて足された日) と、いちばん古いコミットの日 を返す。"""
    if not (JOY / ".git").exists():
        print("NG: 棚の正本のgitが無い:", JOY)
        return None, None
    cmd = ["git", "-C", str(JOY), "log", "--reverse", "--no-merges",
           "--format=%x00%h %ct", "-p", "-U0", "--", TARGET]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    first = {}
    hi = None
    furui = None
    for raw in io.TextIOWrapper(p.stdout, encoding="utf-8", errors="replace"):
        m = RE_MARK.match(raw.rstrip("\n"))
        if m:
            hi = datetime.datetime.fromtimestamp(int(m.group(2))).strftime("%Y-%m-%d")
            if furui is None:
                furui = hi
            continue
        if raw[0] != "+":
            continue
        mm = RE_ID.match(raw)
        if mm and hi:
            first.setdefault(mm.group(1), hi)
    p.wait()
    return first, furui


def sekisho_hi():
    """入荷の関所（status/nyuka/done/）を通った曲。こちらは入荷票に日付が書いてある。"""
    out = {}
    if not SEKISHO.exists():
        return out
    for f in sorted(SEKISHO.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        at, sid = d.get("at"), d.get("id")
        if at and sid:
            out[sid] = at[:10]
    return out


def main():
    first, furui = hiku()
    if first is None:
        return 1
    kan = sekisho_hi()
    # 関所を通ったものは、関所の日付を正とする（棚より先に日付が決まっている）
    d = dict(first)
    d.update(kan)

    hi = collections.Counter(d.values())
    kyou = datetime.date.today().isoformat()
    # ★いちばん古いコミットの日に「初めて足された」ように見えるものは、
    #   本当にその日に入ったのか分からない。**不明として落とす。**（でっち上げない）
    fumei = [k for k, v in d.items() if v == furui]
    for k in fumei:
        d.pop(k, None)

    # ── ① 台帳の正本（全件）。ここが「いつ入ったか」の唯一の出どころ ──
    DAICHO.parent.mkdir(parents=True, exist_ok=True)
    DAICHO.write_text(json.dumps(
        {"asOf": kyou, "from": furui, "n": len(d), "fumei": len(fumei),
         "sekisho": len(kan), "d": d, "hi": dict(sorted(hi.items()))},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ── ② ブラウザに渡すぶん。**窓の中の「その人が棚に来た日」だけ。** ──
    #    曲1本ずつの日付まで渡すと147KBになる（探す前に読む棚が3割重くなる）。
    #    札に出したいのは「この人は最近来たばかり」だけなので、人の分だけで足りる。
    kyou_d = datetime.date.fromisoformat(kyou)
    sakai = (kyou_d - datetime.timedelta(days=MADO)).isoformat()
    aids = set()
    if HEAD.exists():
        aids = {a["i"] for a in json.loads(HEAD.read_text(encoding="utf-8"))["A"]}
    hito = {k: v for k, v in d.items() if v >= sakai and (not aids or k in aids)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"asOf": kyou, "mado": MADO, "sakai": sakai, "from": furui,
         "zen": len(d), "fumei": len(fumei), "a": hito},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("入荷日が引けたもの %d件 / 不明（いちばん古い便に紛れている）%d件" % (len(d), len(fumei)))
    print("いちばん古いコミット:", furui, "／ 関所ぶん:", len(kan), "件")
    for n in (7, 14, 30, MADO, 60, 90):
        s = (kyou_d - datetime.timedelta(days=n)).isoformat()
        print("  直近%3d日（%s以降）: %6d件%s"
              % (n, s, sum(1 for v in d.values() if v >= s), "  ←「最近」" if n == MADO else ""))
    print("→ 台帳 %s %.0fKB" % (DAICHO, DAICHO.stat().st_size / 1024))
    print("→ 棚へ %s %.0fKB（窓の中の人 %d組）" % (OUT, OUT.stat().st_size / 1024, len(hito)))
    if not hito:
        print("★窓の中に1組も居ない。案内人は『最近入荷した』とは言わない（自動で黙る）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
