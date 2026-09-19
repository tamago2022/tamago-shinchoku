#!/usr/bin/env python3
import sys
sys.path.insert(0, "/Users/mac/Desktop/tamago-shinchoku/tools")
from _tmp_877_render import render, YEL, GRN, WHT, RED

lines3 = [
    ("ここから先だけ、たまごさんに30秒お願いしたいこと", 24, YEL, True),
    ("(Brave側の設定は全部確認済み・何も壊れていない・何もいじっていない)", 16, WHT, False),
    ("", 12, WHT, False),
    ("① いつものBraveでYouTubeの動画を1本再生する", 20, GRN, True),
    ("② 下のスピーカーの絵に斜め線(ミュート中)がついていたらクリックして音を出す", 20, GRN, True),
    ("③ 音量バーを一度、右いっぱいまでしっかり上げる", 20, GRN, True),
    ("④ そのままプレイリストを2〜3曲流してみる", 20, GRN, True),
    ("", 15, WHT, False),
    ("YouTubeは「前回どこまでミュート/音量だったか」を", 18, WHT, False),
    ("自分のサイト側(Brave設定の外側)で覚えているため、", 18, WHT, False),
    ("一度手動で音量を上げ直すと、その状態が新しく上書き保存される", 18, WHT, False),
    ("→ 以降は毎回音付きで始まるようになる、というのが今回の見立て", 18, RED, True),
]
render(lines3, "/Users/mac/Desktop/tamago-shinchoku/share/check/img/877-owner-30sec-fix.png")
