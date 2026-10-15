#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1160番【タブ掃除係】＝**廃止**。走らせてはいけない。

2026-09-26 たまごさん：
  「止めろ。AppleScript / System Events を使うな。たまごさんの画面にまたmacOSの
   許可ダイアログ（"python3" が "System Events" を制御…）が出た。**これをやった時点で失格。**
   この方針は今日2回目の同じ事故。TCC許可・画面操作が要る手段は全面禁止。」

■ 何をやらかしたか（事実）
  ・このファイルの中身は osascript（AppleScript）で Chrome / Brave / System Events を
    直接叩いてタブを閉じる作りだった。
  ・実測ログ status/tabs_souji.log：
      12:06:17 こけた: osascript 'System Events' timed out after 30 seconds
      12:06:24 同じ
    そして**たまごさんの画面に許可ダイアログが出た。**画面を奪う行為そのもの。
  ・heartbeat.sh と machine_status_push.sh に呼び出しを足してしまった。**両方とも外した。**

■ どうしてこの道は使えないのか（言い換えれば、なぜ戻してはいけないのか）
  Macの外側からブラウザのタブに触る手は、どれもTCC（オートメーション許可）を要求する。
  許可を出す人が座っていない常駐からそれを叩くと、たまごさんの作業中に
  ダイアログが飛び出す。**速さや便利さでは埋まらない禁止事項。**

■ 代わりに何をしたか
  ・閉じるのは Chrome MCP（tabs_close_mcp）＝自分のタブグループの中だけ。確実に閉じられる。
  ・タブグループ外のタブには**届かない。**届かないものは「届かない」と正直に書く。
  ・「開いたら必ず閉じる」を全セッションの決まりにした：
      tools/1161_tab_kanmon.py            … Stopフックの関所。閉じずに終わろうとしたら終了を拒否
      status/KUROMACHI_NO_YARIKATA.md     … やり方に明記
      start_task のプロンプト雛形          … 開く前に読む場所に明記
  ・Braveは**新しく開かないこと**で0に保つ（既にあるものには届かない）。

★このファイルは記録として残している。復活させないこと。
"""
import sys

print("1160_tab_souji.py は廃止されました（AppleScript/TCC禁止）。"
      "tools/1161_tab_kanmon.py と status/KUROMACHI_NO_YARIKATA.md を見てください。",
      file=sys.stderr)
sys.exit(1)
