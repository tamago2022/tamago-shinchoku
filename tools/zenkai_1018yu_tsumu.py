#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-18夕 全開（〜火曜10-20 18:00）の便を積む。何度呼んでも二重には積まない（zenkaiKey で照合）。

たまごさん（10-18夕）：「リセット済み。火曜18時にまた週の枠がリセットされるので、日・月の2日間はFableで全開に回す。
ただしMacが重くなるのはダメ（負荷判定は守る）。次の便を全部Fableで積む。すでにキューにある同じ内容の便は、
重ねずにFableへ載せ替える。」

期間・本数：status/fable_week.json・status/zenkai.json（until=2026-10-20T18:00+09:00）。
負荷：zenkai.lane_max（4本目以降はメモリ空き40%・ディスク40GB・CPU65%未満）＋ auto_launcher._fable_lane（固まる手前なら出さない）。

使い方: python3 tools/zenkai_1018yu_tsumu.py [--dry]
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
JRS = "/Users/mac/Desktop/joy-relief-station"
SHIN = REPO
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
WHY = "たまごさん指示（10-18夕）：日・月はFableで全開（火曜18:00まで）・負荷判定は守る"

MAMORU = """
【守ること（全部）】
- 許可ポップアップが出る操作はしない。出そうなら飛ばして「未確認」と書いて先へ進む。
- web_fetch は使わない。調べ物は python3 tools/wiki_lookup.py・python3 tools/mac_fetch.py URL など工場の道具経由（status/mac_jobs/pending/*.sh で Mac 上で走らせて読む）。
- ブラウザは使わない（Brave・Chromeに触らない。open URL・webbrowser.open 禁止）。画面の確認は工場の headless（Playwright の使い捨て）だけ。
- 円がかかるAPIは呼ばない（有料の画像生成・動画生成・音声API・外部の従量サービス禁止）。クレジット（Claude・Genspark の既存クレジット）は使ってよい。
- git worktree を増やさない（いま居る作業場だけで作業する）。
- たまごさんに質問しない。迷ったら安全側で決め、理由を1行残す。
- 事実（年・数字・受賞・「オリジナル」等）は出典を確かめてから書く（sekisho-jijitsu-shutten）。確かめられないものは書かない。
- Macを重くしない：重い処理（ffmpeg・ビルド・headless）は1つずつ。並列にしない。
- 途中で切られても続きから再開できるよう、区切りごとに status/zenkai_1018yu/<この便のキー>/ に到達点を1ファイルで残す（最初にそこを読んで続きから）。
- 作った一時ファイル・中間物は最後に自分で消す（使ったらしまう・tools/chukan_shimau.py）。
- 公開：本番URLが変わったことを確かめて完了（python3 tools/koukai_kakunin.py）。工場の鍵（Lovable）が切れていて押せないときは、main合流まで進めて「公開待ち（Dispatchが押す）」と書き、止まらず次へ。
- joy-relief-station を変えたら push の前に prebuild の関所を全部通す（check-i18n-parity ほか）。文言を変えたら同じコミットで src/i18n/overlay/{en,zh-Hans,es,ko}.json に訳。main合流前に python3 tools/koutai_kanmon.py --check（後退の関所）。
- 見せる前に design-critique で採点し、oni-kantoku で点検。報告の1行目は本番URL（無ければ確認ページ／Driveの非公開URL）。
"""

MAG_KATA = """
【型＝「怒れる人々 vol.1」（10-18確定）。CLAUDE.md「マガジン」節と tools/magazine/mag_build.py の MAGAZINE_KATA_1018 が正本・見本 https://joy-relief-station.lovable.app/magazine/ikareru-01.html】
つかみ→章（10本前後・つなぎの一文）→締め／章頭（小さな一言・曲名・形式・年・「この曲のページへ →」）／燃え殻の温度＋コラムニストの笑い・情報は削らず裏話で・事実は全部出典つき・生活の一コマ／
吹き出し（卵コンシェルジュ・運営アイコン・肩書きなし・1つに役割1つ・笑いと出典つき裏ネタ半々・章の半分〜3分の2）／雰囲気の静止画5〜6枚以上（自由ライセンスのみ・撮影者・ライセンス・元ページを小さく・fuukei.py）／
終わり：締め→この特集をシェア→きっかけの動画→出典→OTHER MAGAZINES→すべてのバックナンバー→ごきげん補給所をフォロー／5言語（曲名・アルバム名は意訳しない）／
扱った曲は全部 曲ページ（/cover-guide?artist=…&song=…）へ。無ければ作る（sekisho-artist-song）。出す前に unify_look.py --check と magazine_monogatari_kanmon.py --all。公開は同じ本番URLを上書き（put_prod.sh）。マガジン一覧（backnumber.py・Obsidian「マガジン一覧」）に載せる。
"""


def item(key, order, title, what, repo, limit=180):
    return {"key": key, "order": order, "title": "Fable｜" + title,
            "what": "【全開便 10-18夕〜火曜18:00・Fable】%s\n%s%s" % (title, what, MAMORU), "repo": repo, "limit": limit}


def build_items():
    return [
        item("Y1-kokuchi", 1, "シティポップ告知動画を3パターン（世界観・書体・動きを別物に）",
             "対象：特集「世界が先に見つけた日本の夜」（https://joy-relief-station.lovable.app/feature/citypop-sekai）の告知動画。\n"
             "たまごさんの言葉（そのまま）：「今のAnthropicの持てる力を全部使って最大限で。タイポグラフィやアニメーションのパターン、世界観も変えて、デザインの種類を見たい」\n"
             "仕様：13秒×3本。最後の2秒は新ロゴのカット（ズームなし・見本の半分の大きさ。新ロゴの置き場は status/ と share/check/assets を「ロゴ」で探す）。音の拍に合わせてカット・文字を動かす（拍は音から機械で取る）。\n"
             "3案ははっきり別物に：A＝80年代の東京の夜のネオンとカセット／B＝Flickermood型の文字が跳ねて崩れるキネティックタイポ／C＝ソール・バス型の幾何学と切り絵。"
             "書体・色・動きの文法を3案で重ねない。基準はGensparkの見本以上。\n"
             "作り方：コード（HTML/CSS/Canvas/SVG・Remotion等の無料の道具）＋ffmpeg。有料の画像生成・動画生成は使わない。素材は既存（特集のサムネイル・自由ライセンス）だけ。\n"
             "合格線：design-critique で85点以上。未満は作り直す（各案ごと）。\n"
             "前回の到達点：118370番（v10b・68点）・120045番（5回途中で切られた＝区切りごとに到達点を残すこと）・118369番（タイポグラフィ映像の研究）・118557番（Flickermood）。queue.json で読んでから始める。\n"
             "納品：python3 tools/claude_nouhin.py put <mp4> --anken その他 --saishin（Drive・非公開）。報告に非公開URLを3本と各案の点数。予約・投稿はしない。中間ファイル（フレーム・音の切り出し）は消す。",
             SHIN, limit=240),
        item("Y2-tsuki", 2, "月の特集 vol.1：燃え殻風に書き直して確定型で本番公開",
             "Gensparkの叩き（GH1015・GH1028「月に吠える」の店主の修正指示 10/18・120095／120210番の what を全部読む）を、燃え殻風の語りで書き直す。\n"
             "月の並びは 布袋 → Mr. Moonlight → 昔の曲（昔の曲は削らない）。\n" + MAG_KATA, SHIN),
        item("Y2-odoru", 3, "踊るの特集 vol.1：燃え殻風に書き直して確定型で本番公開",
             "Gensparkの叩き（GH1018・120096／120098番の what と /Users/mac/tamago/_inbox/ の納品）を、燃え殻風の語りで書き直す。\n" + MAG_KATA, SHIN),
        item("Y3-kyoku", 4, "曲ページの質上げ：マガジンに出た曲とSNSに出した曲",
             "対象：①マガジン・特集で扱った曲の曲ページ ②SNSに投稿した曲（status/public/toukou_daicho.json・toukou_tenken.json で落ちている曲を先に）。\n"
             "CLAUDE.md「曲ページを5点そろえる」（検索で出る・関連4本以上・メモと出典・マガジンへの入口・動画が生きている）を全部そろえる。"
             "「この流れで」の抜けは status/copy_queue_1018.* のカードのコピー直し便（B-bin）が埋めるので、ここでは重ねず、それ以外の欠けを直す。\n"
             "コピーは bonjovi-ojisan-kobun、事実は出典、アーティストの取り違えゼロ（sekisho-artist-song）、page-kenpin で検品。", JRS),
        item("Y4-howitholds", 5, "HowItHolds EP01（男の子版）：音だけ整えてもう一度見せる",
             "3Dをコードで組む方式はやらない。前に作ったEP01の男の子版（男の子の顔でつまずいた回。86065番・Drive「棒人間」・status/ を EP01 で探す）の映像はそのまま、"
             "音（声・効果音・BGM）の質だけを整える：音量の揃え（ラウドネス）・声の明瞭さ（ノイズ・こもり）・効果音の位置と大きさ・BGMの入りと抜け・声の下でBGMを下げる。"
             "今ある音の素材と無料の道具（ffmpeg・sox 等）だけ。\n"
             "有料の音声APIが要ると判断したら使わずに「何を◯本で◯円（出典つきの単価）」の見積りを報告に書く。\n"
             "納品：python3 tools/claude_nouhin.py put <mp4> --anken 棒人間 --saishin（非公開URLを報告）。整える前と後の違いを3行で。", SHIN),
        item("Y5-avatar", 6, "トーキングアバター（コンシェルジュが話す・口パク）を完成まで",
             "これまでの便（61600番 GH458 talking egg avatar HTML demo の差し戻し・1937番・80946番・80949番・2020番）の what と到達点を全部読み、続きから完成まで。\n"
             "コンシェルジュ（運営アイコンのキャラ）が話し、口が音に合わせて動く。無料の道具（ブラウザ内の音声解析で口パク・既存の声素材）で作れる所は全部作る。"
             "有料APIが要る所（声の生成など）は見積り（何を◯本で◯円・単価の出典）だけ出してそこで止める。\n"
             "置き場は joy-relief-station（本番のどこに出すかは今の導線を崩さない場所。決められなければ非公開の確認ページ）。", JRS),
        item("Y6-site", 7, "サイト全体の見直し：導線・重さ・迷子",
             "トップ→棚→曲ページの導線、重さ（スマホ相当で画面の切り替えの秒数を工場の headless で測る・koutai_kijun.json と並べる）、迷子になる場所（行き止まり・戻れない・同じ曲が2系統に分裂など）を洗い出して一覧（status/zenkai_1018yu/Y6-site/ichiran.md）にし、直せるものは直す。\n"
             "気に入られている見た目は変えない。見た目を変える案は本番に出さず、非公開の確認ページでA/B/Cとして並べる。\n"
             "関連する古い便（35351・35394・60763・55199・67741・1316 など）は材料として読む（重ねて別便にしない）。後退の関所（koutai_kanmon）を必ず通す。", JRS),
        item("Y7-chef", 8, "料理：シェフのアーティストページ37人分を充実＋料理を49品→倍に（データだけ）",
             "①シェフのアーティストページ37人分を、音楽アーティストと同じ型で充実（経歴・代表料理・本人チャンネルへの導線・出典）。"
             "②料理を49品から98品以上へ。一流のシェフ・料理研究家の動画だけ（本人チャンネル・公式のみ。素人・転載は入れない。チャンネルの取り違えゼロ＝1312番の事故を繰り返さない）。\n"
             "レシピレーダーのUIは別便で進行中なので触らない。ここではデータだけ。\n"
             "関連する古い便（35121・35122・35139・35231・80805〜80812・41481 など）は材料として読む。レシピ本文の丸ごと引用はしない。", JRS),
    ]


# 同じ内容の既存便：Fableへ載せ替え（その便をそのまま走らせる）／統合して止める
ODORU_NOTE = "\n\n【10-18夕 全開から】この便はFableの「Y2-odoru」便に統合しました（重ねて走らせない）。"
MERGE = {  # n: 統合先キー
    118370: "Y1-kokuchi", 120045: "Y1-kokuchi",
    120095: "Y2-tsuki", 120210: "Y2-tsuki",
    120096: "Y2-odoru",
    61600: "Y5-avatar", 1937: "Y5-avatar", 80946: "Y5-avatar", 80949: "Y5-avatar",
}


def main():
    dry = "--dry" in sys.argv
    xs = build_items()
    added, skipped, merged, reorder = [], [], [], []
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        items = q.get("items") or []
        have = {it.get("zenkaiKey") for it in items if it.get("zenkaiKey")}
        next_n = max([int(it.get("n") or 0) for it in items] + [0]) + 1
        for x in xs:
            if x["key"] in have:
                skipped.append(x["key"])
                continue
            items.append({
                "n": next_n, "title": x["title"], "hyoudai": x["title"].replace("Fable｜", ""), "hyoudaiSrc": "rule",
                "why": WHY, "what": x["what"], "status": "waiting", "limitMin": x["limit"],
                "model": FABLE, "fixedModel": FABLE, "fableLane": True, "fableLaneOrder": x["order"],
                "priority": 1, "urgent": True, "origin": "user", "queuedAt": NOW,
                "repo": x["repo"], "zenkaiKey": x["key"], "costsMoney": False,
            })
            added.append((next_n, x["key"]))
            next_n += 1
        by_n = {it.get("n"): it for it in items}
        for n, key in MERGE.items():
            it = by_n.get(n)
            if not it or it.get("zenkaiYuMerged"):
                continue
            if it.get("status") in ("waiting", "awaiting_check", "hold", "stuck"):
                it["prevStatus"] = it.get("status")
                it["status"] = "hold"
                it["holdNote"] = "10-18夕 全開：Fable便「%s」に統合（重ねない）" % key
                it["zenkaiYuMerged"] = NOW
                merged.append(n)
        # 既存のFable便（カードのコピー直し B-bin・マガジン質上げ A-*・Genspark配管）はそのまま。新しい7便の後ろへ並べる
        for it in items:
            if it.get("fableLane") and it.get("status") == "waiting" and str(it.get("zenkaiKey", ""))[:1] in ("A", "B", "D"):
                o = it.get("fableLaneOrder") or 99
                if o < 10:
                    it["fableLaneOrder"] = o + 10
                    reorder.append(it.get("n"))
        if not dry:
            ok = queue_store.save_queue(q, snapshot=snap)
            if not ok:
                print("save_queue が拒否しました")
                return 2
    lane_wait = len([it for it in items if it.get("fableLane") and it.get("status") == "waiting"])
    print("積んだ %d便 / 既にあった %s / 統合して止めた %s / 並べ替え %s / Fableレーン待ち %d便"
          % (len(added), skipped, merged, reorder, lane_wait))
    for n, k in added:
        print(n, k)
    if not dry and added:
        try:
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": NOW, "n": "zenkai-1018yu", "type": "info",
                                    "title": "全開（〜火曜18:00）：Fable便を%d本積みました・既存%d本を統合・Fableレーン待ち%d便"
                                    % (len(added), len(merged), lane_wait)}, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
