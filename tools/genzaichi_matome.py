#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# kakeibo: 課金なし（ファイルをまとめるだけ・AIも外部APIも呼ばない）
"""00_現在地.md を 1日1回だけ まとめて書く（2026-10-11・Vault を軽くする）

━━ なぜ ━━
  たまごさん「Obsidian が重くならないことが第一。特にスマホで読み込みが遅くなっているのは確か。
  毎回書き込みが入るから、どうにかして」。
  これまで子セッションは「作業の区切りごと」に 00_現在地.md を書き換えていた（直近7日で AI の直接編集 12回＋
  Bash 経由多数）。1回ごとに iCloud が同期し、スマホが 30KB を読み直していた。

━━ 新しい流れ ━━
  ① 子は Vault に書かない。区切りで status/genzaichi_kouho.md に「## 日時 ｜件名」＋数行を追記するだけ。
       python3 tools/genzaichi_matome.py --kaku "件名" "状態・決まったこと・次の一手（短く）"
  ② 心臓から1時間おきに呼ばれ、22時以降に1回だけ、前回から変化があった時だけ、
     00_現在地.md の「自動まとめ」欄（<!-- 自動まとめ:始 --> 〜 <!-- 自動まとめ:終 -->）を書き換える。
     件名ごとに最新1件・最大30件。欄の外（手で書いた部分）には触らない。
  ③ 変化が無い日は1回も書かない。

    python3 tools/genzaichi_matome.py            # 心臓用（時刻と変化を見て、必要な時だけ書く）
    python3 tools/genzaichi_matome.py --now      # 時刻を無視して今まとめる（変化が無ければ書かない）
    python3 tools/genzaichi_matome.py --kaku 件名 本文
    python3 tools/genzaichi_matome.py --self-test
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
GENZAICHI = os.path.join(VAULT, "00_現在地.md")
KOUHO = os.path.join(REPO, "status", "genzaichi_kouho.md")
STATE = os.path.join(REPO, "status", "vault_kanmon", "genzaichi_matome.json")
START = "<!-- 自動まとめ:始 -->"
END = "<!-- 自動まとめ:終 -->"
HOUR_FROM = 22
MAX_ITEMS = 30


def kaku(kenmei, honbun):
    os.makedirs(os.path.dirname(KOUHO), exist_ok=True)
    with io.open(KOUHO, "a", encoding="utf-8") as f:
        f.write("\n## %s ｜%s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M"), kenmei.strip(), honbun.strip()))
    print("候補に追記しました：%s（Vault への反映は夜に1回）" % KOUHO)


def parse(text, since):
    """候補ファイル → 件名ごとの最新1件（since 以降のもの）"""
    items = {}
    for m in re.finditer(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ｜(.+?)\n(.*?)(?=^## \d{4}-|\Z)", text, re.S | re.M):
        at, ken, body = m.group(1), m.group(2).strip(), m.group(3).strip()
        if at < since:
            continue
        items[ken] = (at, body)
    rows = sorted(items.items(), key=lambda kv: kv[1][0], reverse=True)[:MAX_ITEMS]
    return rows


def build(rows):
    out = [START, "## 今日までに届いた更新（自動まとめ・1日1回／%s）" % time.strftime("%Y-%m-%d %H:%M"), ""]
    for ken, (at, body) in rows:
        body = " ".join(l.strip("- ").strip() for l in body.splitlines() if l.strip())
        out.append("- **%s**（%s）%s" % (ken, at[5:], body[:300]))
    out += ["", "（子セッションは Vault に直接書かない。status/genzaichi_kouho.md に追記→夜にここへ1回だけ反映）", END]
    return "\n".join(out)


def merge(cur, block):
    if START in cur and END in cur:
        a = cur.index(START)
        b = cur.index(END) + len(END)
        return cur[:a] + block + cur[b:]
    return cur.rstrip("\n") + "\n\n" + block + "\n"


def _read_vault(p):
    for i in range(4):
        try:
            return io.open(p, encoding="utf-8").read()
        except FileNotFoundError:
            return ""
        except OSError:
            # iCloud で中身が手元に無い（dataless）と EDEADLK になる。落としてから読み直す
            subprocess.run(["brctl", "download", p], capture_output=True, timeout=30)
            time.sleep(5)
    return None


def run(force=False):
    st = {}
    try:
        st = json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        pass
    today = time.strftime("%Y-%m-%d")
    if not force:
        if time.localtime().tm_hour < HOUR_FROM:
            return "まだ時間ではない"
        if st.get("day") == today:
            return "今日はもう済み"
    try:
        kouho = io.open(KOUHO, encoding="utf-8").read()
    except Exception:
        kouho = ""
    since = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 86400 * 2))
    rows = parse(kouho, since)
    h = hashlib.sha1(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
    st["day"] = today
    if not rows or h == st.get("hash"):
        _save(st)
        return "変化なし（書かない）"
    cur = _read_vault(GENZAICHI)
    if cur is None:
        _save(st)
        return "00_現在地.md が読めない（書かない）"
    new = merge(cur, build(rows))
    if new == cur:
        _save(st)
        return "同じ（書かない）"
    tmp = GENZAICHI + ".matome.tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, GENZAICHI)
    st["hash"] = h
    st["written_at"] = time.strftime("%F %T")
    st["writes"] = st.get("writes", 0) + 1
    _save(st)
    return "書いた（%d件）" % len(rows)


def _save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with io.open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def self_test():
    t = ("\n## 2026-10-10 10:00 ｜A\n古い\n\n## 2026-10-11 09:00 ｜A\n新しい\n\n## 2026-10-11 09:30 ｜B\nb\n")
    rows = parse(t, "2026-10-09 00:00")
    ok1 = [r[0] for r in rows] == ["B", "A"] and rows[1][1][1] == "新しい"
    cur = "# 現在地\n手書き\n"
    m1 = merge(cur, build(rows))
    m2 = merge(m1, build(rows[:1]))
    ok2 = m1.startswith(cur.rstrip("\n")) and m2.count(START) == 1 and "手書き" in m2 and "**A**" not in m2
    ok = ok1 and ok2
    print("逆テスト：%s（件名ごと最新=%s／手書き部分を残して欄だけ差し替え=%s）" % ("合格" if ok else "不合格", ok1, ok2))
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if a[:1] == ["--kaku"] and len(a) >= 3:
        kaku(a[1], " ".join(a[2:]))
        sys.exit(0)
    print(run(force="--now" in a))
