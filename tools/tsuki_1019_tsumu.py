#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-19 月の特集 vol.1 の組み直し便を積む（Fable指定・優先1・1回だけ＝zenkaiKey「Y3-tsuki」で照合）

たまごさん（10-19）：月の特集を新しい原則（6〜8曲・濃く短く・聴き比べは曲ページへ）で組み直して本番を上書き。
訂正（同日）：布袋「DANCING WITH THE MOONLIGHT」も今回に戻す＝7曲。

使い方: python3 tools/tsuki_1019_tsumu.py [--dry]
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import queue_store  # noqa: E402

FABLE = "claude-fable-5-1"
KEY = "Y3-tsuki"
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
URL = "https://joy-relief-station.lovable.app/magazine/hito-wa-naze-tsuki-wo-miru-01.html"

WHAT = """【10-19 たまごさん指示・Fable・優先1】月の特集 vol.1 を新しい原則で組み直し、同じ本番URLを上書きする。
対象：%(url)s（tools/magazine/spec_tsuki01.py・tools/magazine/i18n_tsuki01.json）
前の版：122703番（Y2-tsuki・17章）。その what / result と、GH1015・GH1028（120095・120210番）の店主の指示も読む。ただし曲・筋は下の10-19指示が優先。

【最初に読む】README.md／CLAUDE.md「マガジン」節（10-18確定の型＋【10-19確定】新しい原則）／tools/magazine/mag_build.py の MAGAZINE_KATA_1018／見本 https://joy-relief-station.lovable.app/magazine/ikareru-01.html（tools/magazine/spec_ikareru.py）

【新しい原則（10-19確定・全号共通）】
- 曲は6〜8曲（上限8）。
- 文章は「濃く短く」＝一口サイズ。「一口パクッ、なるほど。次も一口パクッ、なるほど面白いね」のテンポ。背景が分からないほど削らない、疲れるほど説明しない。言葉を減らし、絵と音で見せる。
- 聴き比べ（原曲とカバーなど）は載せない。曲ページへ誘導してそこで聴かせる。例：Mr. Moonlight はビートルズ版だけ。原曲（Dr. Feelgood & the Interns）はビートルズ版の曲ページで聴けるようにする（曲ページに原曲が無ければ足す）。三日月も絢香の公式MVだけ（玉置浩二とのデュエットは三日月の曲ページへ）。

【曲（固定・7曲。並びは話の筋に合わせて決めてよい。冒頭は布袋でもよい）】
1. 布袋寅泰「DANCING WITH THE MOONLIGHT」（今の版の動画 1nqPCbYVGLw）
2. ビートルズ「Mr. Moonlight」（ビートルズ版だけ）
3. 「Moonlight Serenade」（グレン・ミラー）※新規。公式か長く残る再生の多い動画をoEmbedで確かめる
4. オードリー・ヘプバーン「Moon River」（『ティファニーで朝食を』）
5. 絢香「三日月」（公式MV）
6. 童謡「十五夜お月さん」
7. マイケル・ジャクソン（『スリラー』の狼男に変身する場面・ムーンウォーク）
落とした曲の一覧は status/tsuki_dai2dan_kouho.json（月の特集 第2弾の候補・作成済み）。spec から外すだけで、曲ページは消さない。足りない候補があればこのファイルに足す。

【話の筋】
- 人は月を見て、祈った。恋する人を思った。月明かりの下で恋をした。ぼーっと眺め、お餅を食べ、季節を感じてきた。
- 月の謎の側面：月には人を狂わせる（ルナシー、lunatic）という意味がある。そこからマイケル・ジャクソンのムーンウォークと『スリラー』の狼男へ。狼男の伝承は昔からある。潮の満ち引き、犯罪率との関係（俗説なら俗説と書く）、出産や月経との結びつきにも、ちょろっとだけ触れる。
- 東洋と西洋の風習を1つずつ：日本の「十五夜お月さん」と「中秋の名月」（お月見・お団子）と、西洋の風習1つ。それぞれ一口で。
- 結び：「人は昔から色んな思いを月に馳せてきた。けれど、誰も月から返事をもらったことはない。それでも人は、今でも月を眺める」。
- タイトル「月に吠える」・サブタイトル「月を見て歌う人々」はGH1028のまま（変える指示は無い）。

【その他】
- コンシェルジュの吹き出しは箸休め（ぶっ飛んだ例え・ポンコツ変換）。やりすぎない。
- 静止画は Grokボットとたまごさんが決めた月の絵：Googleドライブ「AI制作物/Grok/Grokボット/月に吠える」「MJ生成」。Mac の同期フォルダ（~/Library/CloudStorage/GoogleDrive-*/マイドライブ/AI制作物/Grok/…）から status/mac_jobs/pending/*.sh で取る（コネクタは呼ばない）。joy-relief-station の Issue（gh issue list -R tamago2022/joy-relief-station --search 月）に指定リストが届いていればその通りにする。軽いwebp・遅延読み込み。たまごさんのAI絵なのでクレジットは不要、自由ライセンスの写真を混ぜるなら撮影者・ライセンス・元ページを小さく。
- 出典は本文中に出さず、記事の最後に章ごと（tools/magazine/shutten.py）。事実は出典を取る。俗説は俗説と書く（sekisho-jijitsu-shutten）。
- 載せる曲は全部、独立した曲ページ（関連曲4以上・コピー・メモ）があり、リンクで飛べること（magazine_gate.py で確認。無ければ作る＝sekisho-artist-song）。
- 5言語（曲名・アルバム名は意訳しない）。共有ボタンとフォローは型の通り。
- 機械の裏付け：tools/magazine/magazine_gate.py に「マガジンの曲数8超は不合格」を足す（--self-test つき。既存の号が落ちる場合は落ちた号を列挙して Dispatch に1行、ゲートは警告扱いから始めてよい）。CLAUDE.md の【10-19確定】は書き足し済み。
- 前後の数字を測る：本文の文字数（日本語・読者に見える本文。前＝今の本番、後＝新版）と曲数。status/tsuki_1019/kazu.json に残す。

【公開】mainに入れる → bash tools/magazine/put_prod.sh（unify_look・koutai_kanmon・magazine_gate を通す）→ deploy。工場の鍵（Lovable）が切れていれば、main合流まで進めて status/dispatch_outbox.jsonl に「公開待ち：月の特集 vol.1（main=<コミット>）」を1行（Dispatchが押す）。押せたら python3 tools/koukai_kakunin.py で本番が変わったことを確かめる。

【守ること（全部）】
- 許可ポップアップが出る操作はしない。出そうなら飛ばして「未確認」と書いて先へ進む。
- web_fetch は使わない。調べ物は python3 tools/wiki_lookup.py・python3 tools/mac_fetch.py URL など工場の道具経由（status/mac_jobs/pending/*.sh）。
- ブラウザは使わない（Brave・Chromeに触らない。open URL・webbrowser.open 禁止）。画面の確認は工場の headless だけ。
- 有料APIは呼ばない（円がかかるもの禁止）。
- git worktree を増やさない。たまごさんに質問しない。迷ったら安全側で決め、理由を1行残す。
- Macを重くしない：重い処理は1つずつ。作った一時ファイルは最後に自分で消す。

【報告（1行目）】本番URL ｜ 曲数 前→後 ｜ 本文の文字数 前→後
""" % {"url": URL}


def main():
    dry = "--dry" in sys.argv
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        items = q.get("items") or []
        for it in items:
            if it.get("zenkaiKey") == KEY:
                print("既に積んであります:", it.get("n"), it.get("status"))
                return 0
        n = max([int(it.get("n") or 0) for it in items] + [0]) + 1
        title = "Fable｜月の特集 vol.1：7曲・濃く短くに組み直して本番を上書き"
        items.append({
            "n": n, "title": title, "hyoudai": "月の特集を7曲・濃く短くに組み直す", "hyoudaiSrc": "rule",
            "why": "たまごさん指示（10-19）：新しいマガジンの原則（6〜8曲・濃く短く・聴き比べは曲ページへ）で月の特集を再構成",
            "what": WHAT, "status": "waiting", "limitMin": 180,
            "model": FABLE, "fixedModel": FABLE, "fableLane": True, "fableLaneOrder": 1,
            "priority": 1, "urgent": True, "origin": "user", "queuedAt": NOW,
            "repo": REPO, "zenkaiKey": KEY, "costsMoney": False, "touchUrl": URL,
        })
        q["items"] = items
        if dry:
            print("dry:", n)
            return 0
        if not queue_store.save_queue(q, snapshot=snap):
            print("save_queue が拒否しました")
            return 2
    with io.open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": NOW, "n": str(n), "type": "info",
                            "title": "%d番を積みました（Fable・優先1）：月の特集 vol.1 を7曲・濃く短くに組み直し" % n},
                           ensure_ascii=False) + "\n")
    print("積んだ:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
