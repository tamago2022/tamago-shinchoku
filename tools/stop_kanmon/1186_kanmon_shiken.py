#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1186号【逆テスト】2026-09-29

関所（1186_chrome_kidou_kinshi.mjs）に、わざと違反を流して**赤が出るか**を実測する。
「動いているのに何も取れていない」壊れ方を防ぐための、たまごさんの決まり。

  python3 tools/stop_kanmon/1186_kanmon_shiken.py
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "1186_chrome_kidou_kinshi.mjs")

CH = "Google Chrome"


def node():
    p = shutil.which("node")
    if p:
        return p
    for c in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        if os.path.exists(c):
            return c
    return "node"


def run(payload):
    p = subprocess.run([node(), HOOK], input=json.dumps(payload).encode("utf-8"),
                       capture_output=True, timeout=30)
    return p.returncode


def B(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": "shiken"}


def W(fp, content):
    return {"tool_name": "Write", "tool_input": {"file_path": fp, "content": content},
            "session_id": "shiken"}


def main():
    py = "/Users/mac/tamago/tamago-shinchoku/status/_shiken1186.py"
    md = "/Users/mac/tamago/tamago-shinchoku/status/_shiken1186.md"
    port = "--remote-debugging" + "-port=9222"
    cases = [
        ("openでChromeを開く", B('open -a "%s"' % CH), 2),
        ("open -na でChromeを開く", B('open -na "%s" --args %s' % (CH, port)), 2),
        ("Chrome本体を直接起動", B('"/Applications/%s.app/Contents/MacOS/%s" about:blank' % (CH, CH)), 2),
        ("CDPポート付きで開く", B("chrome %s" % port), 2),
        ("pkillでChromeを落とす", B('pkill -TERM -x "%s"' % CH), 2),
        ("killallでChromeを落とす", B('killall "%s"' % CH), 2),
        ("止めた掃除便を載せ直す",
         B("launchctl load ~/Library/LaunchAgents/com.tamago.chrome-tab-cdp.plist"), 2),
        ("osascriptでChromeを触る", B('osascript -e \'tell application "%s" to activate\'' % CH), 2),
        ("Chrome起動を含む新しいスクリプトを書く", W(py, 'open -a "%s"\n' % CH), 2),
        ("記録(.md)に事実として書くのは止めない", W(md, 'open -a "%s" が犯人だった\n' % CH), 0),
        ("関係ないBashは止めない", B("ls -l /tmp"), 0),
        ("Braveは止めない", B('open -a "Brave Browser"'), 0),
        ("既存タブを読むMCPは管轄外", {"tool_name": "mcp__claude-in-chrome__read_page",
                                       "tool_input": {}, "session_id": "shiken"}, 0),
    ]
    ng, rows = 0, []
    for name, payload, want in cases:
        rc = run(payload)
        ok = rc == want
        if not ok:
            ng += 1
        rows.append("%s %-40s 期待rc=%d 実測rc=%d" % ("○" if ok else "★NG", name, want, rc))
    print("【1186号・逆テスト】" + ("PASS（NG 0件）" if ng == 0 else "★FAIL（NG %d件）" % ng))
    for r in rows:
        print("  " + r)
    return 0 if ng == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
