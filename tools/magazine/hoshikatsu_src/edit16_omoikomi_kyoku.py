# -*- coding: utf-8 -*-
"""「思い込み」（小椋佳）の曲ページを joy-relief-station の coverGuide.ts の ogura-kei に1曲足す（2026-10-22・星勝特集 ch06 用）。
棚（worlds.ts / admin_shelf_picks）には置かない。曲ページ＋関連＋コピー・メモ・出典だけ。
使い方：python3 edit16_omoikomi_kyoku.py <jrs のルート>   何度通しても同じ
"""
import json, re, sys
WIKI_T = 'https://ja.wikipedia.org/wiki/%E9%81%A0%E3%81%96%E3%81%8B%E3%82%8B%E9%A2%A8%E6%99%AF'
WIKI_O = 'https://ja.wikipedia.org/wiki/%E5%B0%8F%E6%A4%8B%E4%BD%B3'
WIKI_H = 'https://ja.wikipedia.org/wiki/%E6%98%9F%E5%8B%9D'
YT = '28x7Wirobjw'
P = '/cover-guide?artist='
REL = [
    (P + 'ogura-kei&song=stand-still', '同じ小椋佳×星勝・曲順ですぐ後', 'スタンド・スティル', '小椋佳 / 星勝', 'Pn75eje0b8k', '譜面を書かない歌い手の隣で、編曲家がマイクの前に立つ。'),
    (P + 'ogura-kei&song=cyclamen-no-kahori', '同じ小椋佳×星勝', 'シクラメンのかほり', '小椋佳', '42vMJqDngVg', '銀行員がふと見た鉢植えが、ロックの骨組みで咲き直す。'),
    (P + 'inoue-yousui&song=tabi-kara-tabi', '同じ時期の星勝の編曲', '旅から旅', '井上陽水', '4YM9lH_82vU', 'ロサンゼルスのスタジオで、日本語の寂しさだけがよく通る。'),
    (P + 'inoue-yousui&song=kasa-ga-nai', '同じ多賀英典の陽水', '傘がない', '井上陽水', 'l8bQUsZjYYM', 'ニュースより、きみの町の雨のほうが大事になる。'),
    (P + 'the-mops&song=gekko-kamen', '星勝が歌うモップスの一曲', '月光仮面', 'ザ・モップス', 'qx6gEp_P-4E', 'ブルースを説明するはずが、正義の味方が走り出していた。'),
]
SONG = {
    'id': 'omoikomi',
    'title': '思い込み',
    'note': '1976年10月7日、NHKホールでの小椋佳のコンサートを収めたライブ盤『遠ざかる風景』の1曲。作詞と歌は小椋佳、作曲は星勝。',
    'src': [WIKI_T, WIKI_O, WIKI_H, 'https://www.youtube.com/watch?v=' + YT],
    'year': 1976,
    'copy': '「小椋佳の曲」という思い込みを、作曲欄の一行がほどく。',
    'memo': '当時、第一勧業銀行の行員だった小椋佳は、仕事の合間にリハーサルに出て、当日も午前中まで働いてから午後に早退してステージに立った。このコンサートを収めた『遠ざかる風景』は1976年11月15日にキティレコードから出て、オリコンのLPチャートで1位になった。「思い込み」は作詞が小椋佳、作曲が星勝で、曲順ではすぐ後に同じ二人の「スタンドスティル」が続く。本人いわく「楽譜を書き起こせないし、楽器演奏も苦手」という小椋佳の詞に、元モップスのギタリストが曲をつけた一曲。',
    'bridgeLabel': 'この特集のつづき（君は星勝を知っているか）',
    'bridgeRelated': [r[0] for r in REL],
    'bridgeReasons': {r[0]: r[1] for r in REL},
    'bridgePreviews': {r[0]: {'title': r[2], 'subtitle': r[3], 'thumb': f'https://img.youtube.com/vi/{r[4]}/hqdefault.jpg', 'copy': r[5]} for r in REL},
    'youtubeId': YT,
}

def indent_json(obj, base):
    s = json.dumps(obj, ensure_ascii=False, indent=1)
    return '\n'.join((base + l) if i else l for i, l in enumerate(s.split('\n')))

if __name__ == '__main__':
    root = sys.argv[1]
    f = root + '/src/lib/coverGuide.ts'
    t = open(f, encoding='utf-8').read()
    if '"id": "omoikomi"' in t:
        print('already'); sys.exit(0)
    a = t.index('"id": "ogura-kei",')
    s = t.index('"id": "stand-still",', a)
    # stand-still の { の位置と、対応する } を探す
    ob = t.rindex('{', 0, s)
    depth, i, instr = 0, ob, False
    while True:
        c = t[i]
        if instr:
            if c == '\\': i += 2; continue
            if c == '"': instr = False
        elif c == '"': instr = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: break
        i += 1
    block = t[ob:i + 1]
    m = re.search(r'"entry": (\d+)', block)
    if m: SONG['entry'] = int(m.group(1))
    line_start = t.rindex('\n', 0, ob) + 1
    base = t[line_start:ob]
    new = ',\n' + base + indent_json(SONG, base)
    t = t[:i + 1] + new + t[i + 1:]
    open(f, 'w', encoding='utf-8').write(t)
    print('added omoikomi (entry=%s)' % SONG.get('entry'))
