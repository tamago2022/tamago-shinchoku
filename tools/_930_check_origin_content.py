import subprocess, json

r = subprocess.run(['git', 'show', 'origin/main:status/public/done_archive.json'],
                    cwd='/Users/mac/tamago/tamago-shinchoku', capture_output=True, text=True)
d = json.loads(r.stdout)
for it in d.get('items', []):
    if it.get('n') in (726, 796, 802, 884):
        print(it.get('n'), it.get('status'))
