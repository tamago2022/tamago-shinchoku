#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
echo "=== moreoweb note key lookup ==="
curl -sL --max-time 15 -A "$UA" "https://note.com/api/v3/notes/ncce188229732" -o /tmp/n_moreoweb.json -w 'code=%{http_code}\n'
python3 -c "
import json
d=json.load(open('/tmp/n_moreoweb.json'))
data = d.get('data',{})
print('title:', data.get('name'))
print('body(text) len:', len(data.get('body','') or ''))
"
echo "=== knorq_ai ==="
curl -sL --max-time 15 -A "$UA" "https://note.com/api/v3/notes/na50afe19e1b2" -o /tmp/n_knorq.json -w 'code=%{http_code}\n'
python3 -c "
import json
d=json.load(open('/tmp/n_knorq.json'))
data = d.get('data',{})
print('title:', data.get('name'))
print('body(text) len:', len(data.get('body','') or ''))
"
