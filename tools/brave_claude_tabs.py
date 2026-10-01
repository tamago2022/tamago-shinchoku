#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Braveの「Claudeが開いたタブ」を数える（読むだけ。Braveには一切触らない）。

2026-10-01 たまごさん：Braveのタブ42枚・12.37GBでスワップ97%。
「Claudeのタブを全部閉じていい。ただし自分で開いたタブは閉じない」。
再発防止として、Braveの中にClaudeのタブが1枚でも残っていたら進捗表で赤を出す。

■ どうやって見分けるか
  Claude in Chrome 拡張は、各セッションのタブを「タブグループ」に入れる。
  Braveのセッションファイル（Sessions/Session_*、SNSS形式）には
  タブ→ウィンドウ、タブ→グループ、グループ→題名 が全部書いてある。
  それを読むだけ（Braveのプロセスにもウィンドウにも触らない＝画面も奪わない）。

  Claudeのグループ＝題名に CLAUDE_TITLE が入るグループ。
  たまごさん本人が作ったグループ・グループ外のタブは「本人のタブ」として数えない。

出力：
  python3 tools/brave_claude_tabs.py            → JSON（標準出力）
  python3 tools/brave_claude_tabs.py --write    → status/brave_claude_tabs.json にも書く
"""
import glob
import io
import json
import os
import re
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "brave_claude_tabs.json")
BRAVE = os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")
CLAUDE_TITLE = re.compile(r"claude|mcp", re.I)

# session_service_commands.cc の番号
C_TAB_WINDOW, C_TAB_INDEX, C_NAV, C_SEL_NAV = 0, 2, 6, 7
C_TAB_CLOSED, C_WIN_CLOSED, C_TAB_GROUP, C_GROUP_META2 = 16, 17, 25, 27


class Pk:
    def __init__(self, b):
        self.b, self.p = b, 4  # 先頭4バイトは payload size

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.p)[0]; self.p += 4; return v

    def u64(self):
        v = struct.unpack_from("<Q", self.b, self.p)[0]; self.p += 8; return v

    def s(self):
        n = self.i32(); v = self.b[self.p:self.p + n]; self.p += (n + 3) & ~3
        return v.decode("utf-8", "replace")

    def s16(self):
        n = self.i32(); v = self.b[self.p:self.p + 2 * n]; self.p += (2 * n + 3) & ~3
        return v.decode("utf-16-le", "replace")


def newest_session(profile):
    fs = glob.glob(os.path.join(profile, "Sessions", "Session_*"))
    return max(fs, key=os.path.getmtime) if fs else None


def parse(path):
    b = io.open(path, "rb").read()
    if b[:4] != b"SNSS":
        raise ValueError("SNSSではない")
    p = 8
    tabs, groups, closed_w = {}, {}, set()

    def T(t):
        return tabs.setdefault(t, {"win": None, "idx": None, "nav": {}, "sel": None, "group": None})

    while p + 3 <= len(b):
        size = struct.unpack_from("<H", b, p)[0]
        if size == 0 or p + 2 + size > len(b):
            break
        cid = b[p + 2]; d = b[p + 3:p + 2 + size]; p += 2 + size
        try:
            if cid == C_TAB_WINDOW:
                w, t = struct.unpack_from("<ii", d); T(t)["win"] = w
            elif cid == C_TAB_INDEX:
                t, i = struct.unpack_from("<ii", d); T(t)["idx"] = i
            elif cid == C_NAV:
                k = Pk(d); t = k.i32(); i = k.i32(); u = k.s(); ti = k.s16()
                T(t)["nav"][i] = (u, ti)
            elif cid == C_SEL_NAV:
                t, i = struct.unpack_from("<ii", d); T(t)["sel"] = i
            elif cid == C_TAB_CLOSED:
                t = struct.unpack_from("<i", d)[0]; tabs.pop(t, None)
            elif cid == C_WIN_CLOSED:
                closed_w.add(struct.unpack_from("<i", d)[0])
            elif cid == C_TAB_GROUP:
                t, _pad, hi, lo, has = struct.unpack_from("<iiQQ?", d)
                T(t)["group"] = ("%016x%016x" % (hi, lo)) if has else None
            elif cid == C_GROUP_META2:
                k = Pk(d); hi = k.u64(); lo = k.u64(); title = k.s16()
                groups["%016x%016x" % (hi, lo)] = title
        except Exception:
            continue
    out = []
    for t, v in tabs.items():
        if v["win"] in closed_w or not v["nav"]:
            continue
        sel = v["sel"] if v["sel"] in v["nav"] else max(v["nav"])
        u, ti = v["nav"][sel]
        g = v["group"]
        out.append({"tab": t, "win": v["win"], "idx": v["idx"], "url": u, "title": ti,
                    "group": g, "groupTitle": groups.get(g) if g else None})
    out.sort(key=lambda x: (x["win"] or 0, x["idx"] or 0))
    return out


def summary():
    """1200_tatamu.py（毎分の計測）から呼ぶ軽い版。読めなかったら claudeTabs=None（0と偽装しない）。"""
    try:
        r = collect()
        return {"tabsTotal": r["tabsTotal"], "claudeTabs": r["claudeTabs"],
                "claudeUrls": [t["url"][:80] for p in r["profiles"] for t in p.get("tabs", []) if t.get("claude")][:10]}
    except Exception as e:
        return {"tabsTotal": None, "claudeTabs": None, "error": str(e)}


def collect():
    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "profiles": []}
    total = claude = 0
    for prof in sorted(glob.glob(os.path.join(BRAVE, "Default")) + glob.glob(os.path.join(BRAVE, "Profile *"))):
        f = newest_session(prof)
        if not f:
            continue
        try:
            tabs = parse(f)
        except Exception as e:
            res["profiles"].append({"profile": os.path.basename(prof), "error": str(e)})
            continue
        for x in tabs:
            x["claude"] = bool(x["groupTitle"] and CLAUDE_TITLE.search(x["groupTitle"]))
        total += len(tabs)
        claude += sum(1 for x in tabs if x["claude"])
        res["profiles"].append({"profile": os.path.basename(prof), "file": os.path.basename(f), "tabs": tabs})
    res["tabsTotal"] = total
    res["claudeTabs"] = claude
    res["aka"] = claude > 0
    res["ichigyou"] = "Brave タブ%d枚（うちClaudeが開いたもの %d枚）" % (total, claude)
    return res


def main():
    res = collect()
    s = json.dumps(res, ensure_ascii=False, indent=1)
    if "--write" in sys.argv:
        tmp = OUT + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(s)
        os.replace(tmp, OUT)
    print(s if "--quiet" not in sys.argv else res["ichigyou"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(0)
