#!/bin/bash
# Drive の受け取り口 → status/fuukei/ai_in/（写すだけ。消さない）
G="$HOME/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/AI制作物/Claude/マガジン"
D="$HOME/tamago/tamago-shinchoku/status/fuukei/ai_in"; mkdir -p "$D"
cd "$G" && for f in */; do mkdir -p "$D/$f"; cp -n "$f"ch* "$D/$f" 2>/dev/null; done; ls -R "$D" | head -40
