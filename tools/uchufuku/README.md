# 宇宙服シリーズ 描画用（GitHub Actions）
- capture.mjs / lib.mjs：receptron/jinglescript tools/music-video（MIT）の写し。capture.mjs に --mute-audio と起動待ち180秒を足しただけ。
- scenes/uchufuku/index.html：試作1本目（2026-11-15・Claude Fable 5.2 が作成）。
- data/：ドビュッシー「月の光」冒頭90秒（楽譜 © 2026 Satoshi Nakajima, CC BY 4.0／ピアノ音源 VCSL, CC0）の notes.json・timing.json。
- 描き直し：status/uchufuku/push_uf.sh "<説明>" go → get_uf.sh <RUN> <置き場>
- scenes/unko-fille/index.html：宇宙うんこシリーズ2本目「亜麻色の髪の乙女」（2026-11-17・Claude Opus 5.5 が作成）。data_fille/ の unko.glb.enc はキットv2の暗号化（鍵は Actions の secret UNKO_KIT_KEY・公開リポに平文で置かない）。
