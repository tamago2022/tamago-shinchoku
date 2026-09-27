#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1401番【ポートを開ける係】2026-09-28

CDP（Chrome DevTools Protocol）は **Chromeが --remote-debugging-port 付きで起動していないと開かない。**
これはChromeの仕様で、後からポリシーや設定ファイルで後付けする道は無い（macOSのChromeは
コマンドライン引数をplistから読まない）。＝一度だけChromeを開き直す必要がある。

■ たまごさんの手を借りずに、しかも1枚もタブを失わずにそれをやる
  1. Chromeが既にポート付きで動いている → 何もしない（armed）
  2. Chromeが動いていない → **何もしない。**勝手にChromeを開かない（画面を奪わない）
  3. Chromeが動いているがポートが無い → 次の条件を**全部**満たしたときだけ、1回だけ開き直す
       ・Macが IDLE_MIN 秒以上さわられていない（ioreg。TCC不要・AppleScript不要）
       ・status/1401_cdp.nostop が無い（たまごさんの停止スイッチ）
       ・まだ1回もやっていない（status/.1401_armed_once）
     やり方：pkill -TERM（＝⌘Qと同じ正常終了。セッションは保存される）
             → open -a "Google Chrome" --args --remote-debugging-port=9222 --restore-last-session
     `--restore-last-session` を付けるので、**前のタブはそのまま全部戻る。**

■ 使っていないもの
  AppleScript / osascript / System Events は1行も使っていない。
  Brave には一切触らない（pkill の対象は -x "Google Chrome" の完全一致のみ）。

止め方： touch status/1401_cdp.nostop
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
ONCE = os.path.join(STATUS, ".1401_armed_once")
STOP = os.path.join(STATUS, "1401_cdp.nostop")
LOG = os.path.join(STATUS, "1401_arm.log")
PORT = int(os.environ.get("TAMAGO_CDP_PORT", "9222"))
IDLE_MIN = int(os.environ.get("TAMAGO_CDP_IDLE_MIN", "180"))  # 3分さわっていなければ開き直す
CHROME = "/Applications/Google Chrome.app"


def say(m):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), m))
    except Exception:
        pass
    print(m)


def port_open():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=3) as f:
            json.loads(f.read().decode("utf-8", "replace"))
        return True
    except Exception:
        return False


def chrome_running():
    return subprocess.run(["pgrep", "-x", "Google Chrome"],
                          capture_output=True).returncode == 0


def idle_seconds():
    """ioreg から HIDIdleTime（ナノ秒）を読む。TCC不要。"""
    try:
        r = subprocess.run(["ioreg", "-c", "IOHIDSystem", "-d", "4", "-r"],
                           capture_output=True, text=True, timeout=10)
        m = re.findall(r'"HIDIdleTime"\s*=\s*(\d+)', r.stdout)
        if not m:
            return -1
        return min(int(x) for x in m) / 1e9
    except Exception:
        return -1


def main():
    if port_open():
        if not os.path.exists(ONCE):
            open(ONCE, "w").write(time.strftime("%F %T") + " already-armed\n")
        say("armed: ポート%dは開いています" % PORT)
        return 0
    if os.path.exists(STOP):
        say("skip: 停止スイッチ(status/1401_cdp.nostop)があります")
        return 0
    if not chrome_running():
        say("skip: Chromeが起動していません（勝手に起動しません）")
        return 0
    if os.path.exists(ONCE):
        say("skip: 開き直しは1回だけ。既にやりました（消せばもう1回やります: %s）" % ONCE)
        return 0
    # ★status/1401_cdp.force を置くと、放置時間を待たずに今すぐ開き直す（1回で自動的に消える）。
    #   たまごさんに「今日じゅうに終わらせる」と言われたときの手。タブは全部戻る。
    FORCE = os.path.join(STATUS, "1401_cdp.force")
    forced = os.path.exists(FORCE)
    if forced:
        try:
            os.remove(FORCE)
        except Exception:
            pass
        say("force: 放置時間を待たずに開き直します（status/1401_cdp.force）")
    idle = idle_seconds()
    if not forced and idle < IDLE_MIN:
        say("wait: Macを%.0f秒前に触っています（%d秒放置されたら開き直します）" % (max(idle, 0), IDLE_MIN))
        return 0

    say("arm: Chromeを正常終了→ポート%d付きで開き直します（--restore-last-session でタブは全部戻ります）" % PORT)
    subprocess.run(["pkill", "-TERM", "-x", "Google Chrome"], capture_output=True)
    for _ in range(40):
        if not chrome_running():
            break
        time.sleep(0.5)
    time.sleep(2)
    subprocess.run(["open", "-a", CHROME, "--args",
                    "--remote-debugging-port=%d" % PORT,
                    "--restore-last-session"], capture_output=True)
    open(ONCE, "w").write(time.strftime("%F %T") + " armed\n")
    for _ in range(40):
        time.sleep(1)
        if port_open():
            say("arm: 成功。ポート%dが開きました" % PORT)
            return 0
    say("arm: 開き直したがポートが確認できませんでした（次回に持ち越し）")
    try:
        os.remove(ONCE)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
