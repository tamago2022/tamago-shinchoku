# 君は星勝を知っているか（2026-10-16）
# Genspark納品のHTML（シティポップ特集の型そのまま）に、たまごさんの直しを当てて直接組んだページ。
# 中身は share/check/tokushu-hoshi-katsu.html と status/magazine_prod/kimi-wa-hoshi-katsu.html（同じもの）。
# 直しの手順は tools/magazine/hoshikatsu_src/（edit*.py＝映像差し替え・時代の写真、tr*.py＝英中西韓の訳、mk.py＝5言語の切替を入れる）。
# 訳だけ直すときは tools/magazine/i18n_hoshikatsu.json を直して、mag_build.add_i18n で入れ直す。
import os, shutil
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if __name__ == '__main__':
    src = os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
    dst = os.path.join(R, 'status/magazine_prod/kimi-wa-hoshi-katsu.html')
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); print(dst)
