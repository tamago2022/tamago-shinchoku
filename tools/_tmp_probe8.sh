#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
echo "=== note.com search API: LINEスタンプ 自動申請 ==="
curl -sL --max-time 15 -A "$UA" "https://note.com/api/v3/searches?context=note&q=LINEスタンプ%20自動申請&size=10" -o /tmp/note1.json -w 'code=%{http_code}\n'
python3 -c "
import json
try:
    d=json.load(open('/tmp/note1.json'))
    notes = d.get('data',{}).get('notes',{}).get('contents',[])
    print('found', len(notes))
    for n in notes[:10]:
        print('-', n.get('name'), '|', 'https://note.com/'+n.get('user',{}).get('urlname','')+'/n/'+n.get('key',''))
except Exception as e:
    print('err', e)
    print(open('/tmp/note1.json').read()[:500])
"
echo "=== note.com search: LINE Creators Market 自動化 ==="
curl -sL --max-time 15 -A "$UA" "https://note.com/api/v3/searches?context=note&q=LINE%20Creators%20Market%20%E8%87%AA%E5%8B%95%E5%8C%96&size=10" -o /tmp/note2.json -w 'code=%{http_code}\n'
python3 -c "
import json
try:
    d=json.load(open('/tmp/note2.json'))
    notes = d.get('data',{}).get('notes',{}).get('contents',[])
    print('found', len(notes))
    for n in notes[:10]:
        print('-', n.get('name'), '|', 'https://note.com/'+n.get('user',{}).get('urlname','')+'/n/'+n.get('key',''))
except Exception as e:
    print('err', e)
"
echo "=== note.com search: LINEスタンプ アカウント停止 ==="
curl -sL --max-time 15 -A "$UA" "https://note.com/api/v3/searches?context=note&q=LINE%E3%82%B9%E3%82%BF%E3%83%B3%E3%83%97%20%E3%82%A2%E3%82%AB%E3%82%A6%E3%83%B3%E3%83%88%E5%81%9C%E6%AD%A2&size=10" -o /tmp/note3.json -w 'code=%{http_code}\n'
python3 -c "
import json
try:
    d=json.load(open('/tmp/note3.json'))
    notes = d.get('data',{}).get('notes',{}).get('contents',[])
    print('found', len(notes))
    for n in notes[:10]:
        print('-', n.get('name'), '|', 'https://note.com/'+n.get('user',{}).get('urlname','')+'/n/'+n.get('key',''))
except Exception as e:
    print('err', e)
"
