# 一時ファイルの一覧と削除候補（120042番・2026-10-18 07:0x 実測）

基準：消すのは「作り直せるもの」だけ（git に同じ中身がある／自動で作り直される写し・キャッシュ）。
作り直せない物・持ち主が分からない物・使用中の物・ブラウザ（Brave・Chrome）の物は残す。
消す時は `tools/youryou_jougen.rm()`（FORBIDDEN＋`tools/browser_mamoru.py`）を必ず通した。

## 消した（106件・空き 206.3→211.4GB、+5.2GB・statvfs 実測）

| 場所 | 中身 | 個数 | 作り直せる理由 |
|---|---|---|---|
| $TMPDIR/1191_* | 1191_honyaku_jidou が origin/main を tar 展開した写し（1個 約140MB） | 14 | 中身は joy-relief-station の git に有る。作る側が消し忘れていた（今回 atexit を入れた） |
| $TMPDIR/1192_*・1192h_* | 1192_title_romaji の tar 展開の写し | 92 | 同上 |

残した2件（1192_bdd8ebld・1192h_jsyt8s4t）は作られて1時間未満＝走っている最中の可能性があるので残した。youryou_jougen の使い捨て（1時間）が次の周で消す。

## 残した（迷う・使用中・ブラウザ・小さい）

| 場所 | 容量 | 更新 | 判断 |
|---|---|---|---|
| /private/tmp/push35075_work/repo | 1.9GB | 10-17 11:58（中の最新は 0.9h 前） | git は main・未保存0・HEAD は本家に有＝作り直せる。ただし直前に中が触られていたので今回は残す。shimau の「/private/tmp 上限3GB・12時間」が次に消す |
| /private/tmp/q35040_clean/repo | 229MB | 10-17 01:00 | **使用中**（vite dev --port 5179 がこの中で動いている）→ 残す |
| /private/tmp/q1015_pd/repo・q1015_moon | 233MB×2 | 10-18 04:51 | 今日の作業場（別セッション）。HEAD は joy に有るが新しい→ 残す |
| /private/tmp/hu_sb・hu_i18n | 366MB・232MB | 10-18 03:47／10-17 15:48 | git ではない写し（main.tgz・src0／AGENTS.md…）。持ち主不明→ 残す（迷う物は残す） |
| /private/tmp/claude-501 | 116MB | 使用中 | Claude Code のセッション出力（この作業も使っている）→ 残す |
| $TMPDIR/tsx-501 | 438MB | 使用中 | node（tsx）のコンパイルキャッシュ。作り直せるが使用中→ 残す |
| $TMPDIR/com.google.Chrome.* | 184個（71個が1日超） | — | **ブラウザの物。触らない**（browser_mamoru は「対象外」判定だが、憲法どおり触らない） |
| $TMPDIR/scoped_dir* | 28個（12個が1日超） | — | Chromium 系の一時フォルダ。ブラウザの物として触らない |
| $TMPDIR/hps-patrol-* | 203個（全部1時間以内） | 作られ続けている | youryou_jougen の使い捨て（1時間）が毎時約400個消している＝仕組みは効いている。作る側（joy-relief-station scripts/patrol/loadShelfCards.mjs）に `process.on("exit", rmSync)` を足すのが次の一手（joy 側に未保存119件があり今回は触らなかった） |
| $TMPDIR/admin-login*・shiro*・sekisho*・linetest*・shot* | 各1MB未満・計32個 | 1時間超 | 小さい・持ち主が分からない→ 残す（捨てる基準は件数でなく重さ） |
| $TMPDIR/TemporaryItems | 144MB | — | macOS の物→ 残す |
| ~/Documents/AI作業/.worktrees/*（13本・0.1〜1.0GB） | 計 約4GB | 全部今日 | 走っている子セッションの作業場。worktree_taihi（10分おき）が push 済みを消す→ 触らない |

## 容量の全体（実測 07:0x）

- $TMPDIR：7.9GB・901個 → 1191/1192 の約4GB を消した
- /private/tmp：3.3GB・184個（6個だけが2日超）
- 作業場 .worktrees：13本・約4GB（全部今日の走行中）
- Mac の空き：df -g で 248GB（前）→ 247GB（後・別セッションの書き込みと相殺）。statvfs では削除で +5.2GB

## 直した「穴」（消し忘れが再発しないように）

1. `tools/1191_honyaku_jidou.py`・`tools/1192_title_romaji.py`：mkdtemp の直後に `atexit.register(shutil.rmtree, tmp, True)`。
2. `tools/youryou_jougen.py` TSUKAISUTE に `1191_`・`1192_`・`1192h_` を追加（1時間で消す受け皿）。
3. shimau.py／chukan_shimau.py は今回の実測では穴なし（$TMPDIR 3日・chrome系1日・中間物2時間・/private/tmp 3GB/12h）。
