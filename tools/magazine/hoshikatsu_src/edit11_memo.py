# -*- coding: utf-8 -*-
"""君は星勝を知っているか：本文に残っていた制作側のメモ（投稿者・再生回数）を外す（2026-10-16 たまごさん「制作側のメモは全部消す」）"""
import json, os, sys
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
L4 = ['en', 'zh-Hans', 'es', 'ko']
REP = {
    'ja': [('映像が、一般の方の投稿で残っている。', '映像も残っている。'),
           ('18年前に投稿された映像が、いま37万回再生されている。コメント欄に', 'この映像のコメント欄には、')],
    'en': [('There is footage — posted by a fan — of Konosuke Sakazaki introducing Katz Hoshi on television.', 'There is also footage of Konosuke Sakazaki introducing Katz Hoshi on television.'),
           (' A video posted 18 years ago now has 370,000 views. Someone in the comments wrote:', ' In the comments under this video, someone wrote:')],
    'zh-Hans': [('有一段影像，是坂崎幸之助在电视上介绍星胜的，由网友上传保存了下来。', '还留有一段坂崎幸之助在电视上介绍星胜的影像。'),
                ('18年前上传的视频，如今播放了37万次。评论区有人写道', '这段视频的评论区有人写道')],
    'es': [('Hay unas imágenes, subidas por un fan, en las que Konosuke Sakazaki presenta a Katz Hoshi en televisión.', 'También hay imágenes en las que Konosuke Sakazaki presenta a Katz Hoshi en televisión.'),
           (' Un video subido hace 18 años lleva hoy 370.000 reproducciones. En los comentarios, alguien escribió:', ' En los comentarios de este video, alguien escribió:')],
    'ko': [('사카자키 고노스케가 TV에서 호시 카츠를 소개하는 영상이, 일반인의 업로드로 남아 있다.', '사카자키 고노스케가 TV에서 호시 카츠를 소개하는 영상도 남아 있다.'),
           (' 18년 전에 올라온 영상이 지금 37만 회 재생되었다. 댓글란에는', ' 이 영상의 댓글란에는')],
}
for p in ('share/check/tokushu-hoshi-katsu.html', 'status/magazine_prod/kimi-wa-hoshi-katsu.html'):
    fp = os.path.join(R, p); h = open(fp, encoding='utf-8').read()
    for a, b in REP['ja']:
        h = h.replace(a, b)
    open(fp, 'w', encoding='utf-8').write(MB.unify_look(h))
TRP = os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json')
tr = json.load(open(TRP, encoding='utf-8'))
for l in L4:
    for k in list(tr[l]):
        for a, b in REP[l]:
            tr[l][k] = tr[l][k].replace(a, b)
json.dump(tr, open(TRP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
t = json.dumps(dict(tr, **{l: dict(tr[l], **MB.common_i18n()[l]) for l in L4}), ensure_ascii=False, separators=(',', ':'))
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, 'kimi-wa-hoshi-katsu.i18n.json'), 'w', encoding='utf-8').write(t)
print('ok')
