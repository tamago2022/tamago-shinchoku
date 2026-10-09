#!/usr/bin/env python3
"""Obsidian Vault の重さ見張り番（毎朝）。閾値超えなら status/vault_weight.md が 🔴 になる。
測るもの：ファイル総数・総容量・1日で更新されたファイル数・1MB超ファイル・音声動画・
自動書き込みで肥大した .md。読むだけで何も変更しない。"""
import os, json, time
VAULT = '/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain'
ST = '/Users/mac/tamago/tamago-shinchoku/status'
TH = dict(files=10000, mb=2500, changed_24h=400, big_md_kb=5000, big_files=780, av_files=25, workspace_mobile_kb=60, tabs_mobile=30)
now = time.time(); n = 0; tot = 0; ch = 0; big = []; av = []; bigmd = []
for r, ds, fs in os.walk(VAULT):
    ds[:] = [d for d in ds if d not in ('.git',)]
    for f in fs:
        p = os.path.join(r, f)
        try: st = os.stat(p)
        except OSError: continue
        n += 1; tot += st.st_size
        if now - st.st_mtime < 86400 and '/.obsidian/' not in p: ch += 1
        if st.st_size > 1048576 and '/.obsidian/' not in p: big.append((st.st_size, p))
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.mp4', '.mov')): av.append(p)
        if f.endswith('.md') and (st.st_size > TH['big_md_kb'] * 1024 or ('/_ルール/' in p and st.st_size > 1500 * 1024)): bigmd.append((st.st_size, p))
wm = os.path.join(VAULT, '.obsidian', 'workspace-mobile.json'); wk = 0; tabs = 0
try:
    s = open(wm, encoding='utf-8').read(); wk = len(s) // 1024; tabs = s.count('"type": "leaf"') + s.count('"type":"leaf"')
except Exception: pass
red = []
if n > TH['files']: red.append('ファイル数 %d > %d' % (n, TH['files']))
if tot / 1048576 > TH['mb']: red.append('総容量 %dMB > %dMB' % (tot / 1048576, TH['mb']))
if ch > TH['changed_24h']: red.append('24時間で %d ファイル更新（同期連発）' % ch)
if len(big) > TH['big_files']: red.append('1MB超ファイルが基準(705)から増加: %d 本' % len(big))
if len(av) > TH['av_files']: red.append('音声・動画がVault内で増加 %d 本（基準22・Vault外へ）' % len(av))
if bigmd: red.append('肥大したmd(自動ログ1.5MB超/一般5MB超): ' + ', '.join(os.path.basename(p) for _, p in bigmd[:3]))
if wk > TH['workspace_mobile_kb'] or tabs > TH['tabs_mobile']: red.append('スマホのタブ記憶が肥大 %dKB/%d枚' % (wk, tabs))
res = dict(time=time.strftime('%F %T'), files=n, mb=round(tot / 1048576), changed_24h=ch, big_files=len(big), av_files=len(av), workspace_mobile_kb=wk, tabs_mobile=tabs, red=red)
json.dump(res, open(ST + '/vault_weight.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
md = '# Vault重さ見張り（%s）\n\n%s\n\n- ファイル %d／容量 %dMB／24h更新 %d／1MB超 %d／音声動画 %d／スマホタブ %d枚(%dKB)\n' % (
    res['time'], ('🔴 ' + '；'.join(red)) if red else '🟢 正常', n, res['mb'], ch, len(big), len(av), tabs, wk)
open(ST + '/vault_weight.md', 'w', encoding='utf-8').write(md)
print(md)
