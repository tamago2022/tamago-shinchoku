import json, html

with open('/Users/mac/Desktop/tamago-shinchoku/share/x-archive/candidates.json', encoding='utf-8') as f:
    cands = json.load(f)

def esc(s):
    return html.escape(s)

rows = []
for i, c in enumerate(cands, 1):
    media_badge = '<span class="badge">🖼️ 画像/動画</span>' if c['media'] else ''
    link_html = f'<div class="link">🔗 {esc(c["links"][0])}</div>' if c.get('links') else ''
    rows.append(f'''
    <div class="item">
      <div class="rank">#{i}</div>
      <div class="meta"><span>{c['date'][:16]}</span><span class="badge">♥ {c['fav']}</span><span class="badge">🔁 {c['rt']}</span>{media_badge}</div>
      <div class="text">{esc(c['text'])}</div>
      {link_html}
    </div>''')

html_out = f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>もう一度出していいやつ候補</title>
<style>
body {{ font-family:-apple-system,"Hiragino Sans",sans-serif; background:#fdf6e9; margin:0; padding:16px; color:#3a2e1f; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
p.sub {{ color:#8a7355; font-size:13px; margin:0 0 16px; }}
.item {{ background:#fff; border:1px solid #e6d5b0; border-radius:10px; padding:12px 14px; margin-bottom:10px; position:relative; }}
.rank {{ position:absolute; top:10px; right:12px; font-size:12px; color:#c9a86a; font-weight:bold; }}
.meta {{ font-size:12px; color:#a08856; margin-bottom:6px; display:flex; gap:10px; }}
.text {{ font-size:14px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }}
.badge {{ background:#fdeecb; color:#b3821b; padding:1px 6px; border-radius:4px; font-size:11px; }}
.link {{ font-size:12px; color:#5a7fa0; margin-top:6px; word-break:break-all; }}
</style></head><body>
<h1>🫙 もう一度出していいやつ（候補 {len(cands)}件）</h1>
<p class="sub">反応数（いいね・リツイート）・画像動画の有無・リンクの有無からスコアをつけ、上位から並べています。ここから選んで、一言添えて再投稿する運用を想定。</p>
{''.join(rows)}
</body></html>'''

with open('/Users/mac/Desktop/tamago-shinchoku/share/x-archive/candidates.html', 'w', encoding='utf-8') as f:
    f.write(html_out)
print('候補ページ生成完了:', len(cands), '件')
