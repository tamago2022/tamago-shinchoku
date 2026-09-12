import json, re, os

DIR = "/Volumes/iMac HDD/Desktop退避_2026-09-02/twitter-2026-08-05-91a26492ba94a0210d480103a2548fdcd793c19cfb6c29beaf60a324301326c6"
OUT = "/Users/mac/Desktop/tamago-shinchoku/share/x-archive"

def load_js(path, prefix_re):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    content = re.sub(prefix_re, '', content, count=1)
    return json.loads(content)

tweets = load_js(f"{DIR}/data/tweets.js", r'^window\.YTD\.tweets\.part0 = ')

items = []
for row in tweets:
    t = row['tweet']
    if t.get('in_reply_to_status_id'):
        continue  # 他者への返信は除外(自分の独立した発信のみ対象)
    text = t.get('full_text', '')
    if text.startswith('RT @'):
        continue
    fav = int(t.get('favorite_count', 0) or 0)
    rt = int(t.get('retweet_count', 0) or 0)
    ext = t.get('extended_entities', {}) or {}
    media = ext.get('media', []) or []
    media_urls = []
    for m in media:
        u = m.get('media_url_https') or m.get('media_url')
        if u:
            media_urls.append(u)
    urls = t.get('entities', {}).get('urls', []) or []
    expanded = [u.get('expanded_url') for u in urls if u.get('expanded_url')]
    # t.co を実際のリンクに差し替えた本文
    display_text = text
    for u in urls:
        if u.get('url') and u.get('expanded_url'):
            display_text = display_text.replace(u['url'], u['expanded_url'])
    for m in media:
        if m.get('url'):
            display_text = display_text.replace(m['url'], '').strip()
    score = fav + rt * 3 + (10 if media_urls else 0) + (2 if expanded else 0)
    items.append({
        'id': t.get('id_str'),
        'date': t.get('created_at', ''),
        'text': display_text,
        'fav': fav,
        'rt': rt,
        'media': media_urls[:1],
        'links': expanded[:1],
        'score': score,
    })

print('対象件数(返信・RT除外後):', len(items))
items.sort(key=lambda x: -x['score'])

# 検索用データ(全件・軽量フィールドのみ)
search_data = [{
    'id': i['id'], 'date': i['date'][:10] if i['date'] else '',
    'text': i['text'], 'fav': i['fav'], 'rt': i['rt'],
    'media': 1 if i['media'] else 0, 'score': i['score']
} for i in items]

# 2026-09-12(717番)：1ファイルにすると公開リポジトリの1MB超ファイル点検に引っかかるため、
# 5分割して書き出す（share/x-archive/index.html 側もこの分割前提でPromise.allで結合する）。
import math
PARTS = 5
chunk = math.ceil(len(search_data) / PARTS)
for idx in range(PARTS):
    part = search_data[idx * chunk: (idx + 1) * chunk]
    with open(f"{OUT}/tweets_data_{idx+1}.json", 'w', encoding='utf-8') as f:
        json.dump(part, f, ensure_ascii=False, separators=(',', ':'))

# 循環候補(上位300件、テキスト30字以上)
candidates = [i for i in items if len(i['text']) >= 20][:300]
with open(f"{OUT}/candidates.json", 'w', encoding='utf-8') as f:
    json.dump(candidates, f, ensure_ascii=False, indent=1)

size = sum(os.path.getsize(f"{OUT}/tweets_data_{i+1}.json") for i in range(PARTS))
print('検索データサイズ(5分割合計):', size, 'bytes =', round(size/1024/1024,2), 'MB')
print('候補件数:', len(candidates))
print('上位5件プレビュー:')
for c in candidates[:5]:
    print('-', c['date'], f"fav={c['fav']} rt={c['rt']}", c['text'][:60].replace(chr(10),' '))
