#!/bin/bash
# frames_gh（1〜542・滝）＋ frames_gh_d（543〜1302・雲の上の夜）を合わせて MP4 にする（Mac・nice 19・1本ずつ）
V="$HOME/tamago/tamago-shinchoku/status/uchu_unko/v3_taki"; M=/private/tmp/206316_uu3t_merge; OUT="$HOME/tamago/tamago-shinchoku/status/uchu_unko/261105_宇宙うんこv3滝_写真質感_b.mp4"
L="$V/log/kumitate_d.txt"; cd "$V"
(
date
for i in $(seq -f "%04g" 543 1302); do ln -sf "$V/frames_gh_d/f$i.jpg" "$M/f$i.jpg"; done; echo "merge $(ls $M | wc -l)"
nice -n 19 python3 kumitate_v3t.py $M "$OUT" --part 543-920 && date
nice -n 19 python3 kumitate_v3t.py $M "$OUT" --part 921-1374 && date
UU_STILL=1150 nice -n 19 python3 kumitate_v3t.py $M "$OUT" && date
echo KUMITATE_D_END
) >> "$L" 2>&1
