#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-18 全開モードの便を積む（1回だけ・何度呼んでも二重には積まない＝zenkaiKey で照合）

たまごさん（10-18 朝）：A マガジン全号の質上げ／B カードのコピー直し811件を25件ずつ／C Macを軽く／D 進行中を止めずに。
Fableを指定できる便はFable（fixedModel=claude-fable-5-1・fableLane）。並び順は fableLaneOrder。

使い方: python3 tools/zenkai_1018_tsumu.py [--dry]
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import queue_store  # noqa: E402
import cost_risk  # noqa: E402

FABLE = "claude-fable-5-1"
JRS = "/Users/mac/Desktop/joy-relief-station"
SHIN = REPO
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")

MAMORU = """
【守ること（全部）】
- 許可ポップアップが出る操作はしない。出そうなら飛ばして「未確認」と書いて先へ進む。
- web_fetch は使わない。調べ物は python3 tools/wiki_lookup.py・python3 tools/mac_fetch.py URL など工場の道具経由。
- ブラウザは使わない（Brave・Chromeに触らない。open URL・webbrowser.open 禁止）。
- 外部の生成サービス・従量のAPIは呼ばない（円がかかるもの禁止）。Claude自身と手元の道具だけ。
- 自分で git worktree を増やさない（いま居る作業場だけで作業する）。
- たまごさんに質問しない。迷ったら安全側で決め、理由を1行残す。
- 事実（年・数字・受賞・「オリジナル」等）は出典を確かめてから書く（sekisho-jijitsu-shutten の基準）。確かめられないものは書かない。
- 作った一時ファイル・中間物は最後に自分で消す（使ったらしまう）。
- 公開：本番URLが変わったことを確かめて完了（python3 tools/koukai_kakunin.py）。Lovableの鍵が切れていて公開が押せないときは、main合流まで進めて「公開待ち（Lovableの鍵）」と書き、止まらず次へ。
- 終わったら本番URL（無ければ確認ページ）を報告の1行目に。
"""

MAG_KATA = """
【型＝「怒れる人々 vol.1」（10-18確定）。CLAUDE.md「マガジン」節と tools/magazine/mag_build.py の MAGAZINE_KATA_1018 が正本】
1. つかみ → 章（10本前後）→ 締め。章と章は「つなぎ」の一文で物語として流す。
2. 章頭：①小さくユーモアのある一言 ②曲名 ③形式 ④年 ⑤「この曲のページへ →」。
3. 本文は燃え殻の温度＋コラムニストの笑い。情報は削らず裏話でぎゅっと。事実は全部出典つき。生活の一コマを混ぜる。
4. 吹き出し（卵コンシェルジュ・運営アイコン・肩書きなし）：1つに役割1つ。笑い（箸休め）と出典つきの濃い裏ネタを半々。章の半分〜3分の2に1つ。
5. 雰囲気の静止画を5〜6枚以上（Wikimedia Commons 等の CC BY / BY-SA / CC0 / PD だけ。撮影年を確かめ、撮影者・ライセンス・元ページを小さく）。軽いwebp・遅延読み込み（tools/magazine/fuukei.py・mag_build.interlude()）。
6. 終わり：締め →「この特集をシェア」→ きっかけの動画 → 出典 → OTHER MAGAZINES → すべてのバックナンバー →「ごきげん補給所をフォロー」。
7. 5言語（ja/en/zh-Hans/es/ko）。曲名・アルバム名は意訳しない。
- 見た目は全マガジン同じ（mag_build.unify_look()、出す前に python3 tools/magazine/unify_look.py --check と python3 tools/magazine_monogatari_kanmon.py --all）。
- 制作側の都合・注記は読者に出さない。存在しないことを書かない。
- 共通部品（mag_build.py・share_bar.py・put_prod.sh）を直すのは「怒れる人々」便だけ。ほかの便で共通部品の直しが要るときは status/zenkai_1018/kyoutsu_irai.md に1行書いて、自分の号の spec・i18n だけで進める（同時に走る便どうしで壊し合わないため）。
- 公開は同じ本番URLを上書き：bash tools/magazine/put_prod.sh（後退の関所 koutai_kanmon も通る）。
"""


def mag(key, title, target, extra=""):
    what = ("【全開便 10-18・マガジン質上げ】%s\n対象：%s\n"
            "やること：確定した型（下）にそろえる。足りない章・吹き出し・静止画・出典・5言語を埋め、事実を出典で裏取りし直し、"
            "ズレていた事実は直す。公開して同じ本番URLを上書き→本番で200と中身を確認。%s\n%s%s"
            % (title, target, extra, MAG_KATA, MAMORU))
    return {"key": key, "title": "Fable｜マガジン質上げ：" + title, "what": what, "repo": SHIN}


def build_items():
    A = [
        mag("A-ikareru", "怒れる人々 vol.1（型の見本そのもの）",
            "https://joy-relief-station.lovable.app/magazine/ikareru-01.html（tools/magazine/spec_ikareru.py）",
            "見本なので7点すべてを満たしているかを機械と目で点検し、欠け（静止画の枚数・シェア/フォローの並び・5言語）を埋める。"
            "共通部品の直し（status/zenkai_1018/kyoutsu_irai.md に来た依頼）もこの便で引き受ける。"),
        mag("A-hoshikatsu", "君は星勝（星勝）",
            "https://joy-relief-station.lovable.app/magazine/kimi-wa-hoshi-katsu.html（tools/magazine/spec_hoshikatsu.py）"),
        mag("A-harakami", "レイ・ハラカミ",
            "https://joy-relief-station.lovable.app/magazine/rei-harakami.html（tools/magazine/spec_harakami.py）"),
        mag("A-takoukan", "なぜ音楽は 01 多幸感",
            "https://joy-relief-station.lovable.app/magazine/naze-ongaku-01-takoukan.html（tools/magazine/spec_takoukan.py）"),
        mag("A-josh", "ジョシュ・ターナー（弾き語り）",
            "https://joy-relief-station.lovable.app/magazine/hikigatari-josh-turner.html（tools/magazine/spec_josh.py）"),
    ]
    feat = ("これは joy-relief-station の特集ページ（React）。文言を変えたら同じコミットで src/i18n/overlay/{en,zh-Hans,es,ko}.json に訳を足し、"
            "push の前に prebuild の関所を全部通す（check-i18n-parity ほか）。")
    A.append({"key": "A-citypop", "title": "Fable｜マガジン質上げ：世界が見つけた日本のシティポップ",
              "what": ("【全開便 10-18・マガジン質上げ】世界が見つけた日本のシティポップ\n対象：https://joy-relief-station.lovable.app/feature/citypop-sekai\n"
                       "やること：確定した型（下）にそろえる（特集ページなので部品は React 側の同等物で）。%s\n%s%s" % (feat, MAG_KATA, MAMORU)),
              "repo": JRS})
    A.append({"key": "A-hikigatari", "title": "Fable｜マガジン質上げ：弾き語り特集",
              "what": ("【全開便 10-18・マガジン質上げ】弾き語り特集\n対象：https://joy-relief-station.lovable.app/feature/hikigatari\n"
                       "やること：確定した型（下）にそろえる（特集ページなので部品は React 側の同等物で）。%s\n%s%s" % (feat, MAG_KATA, MAMORU)),
              "repo": JRS})

    B = []
    md = io.open(os.path.join(REPO, "status", "copy_queue_1018.md"), encoding="utf-8").read()
    bins = re.findall(r"^- 便(\d+)（([^）]*)）：(.+)$", md, flags=re.M)
    for no, tier, keys in bins:
        n_keys = len([k for k in keys.split("、") if k.strip()])
        B.append({"key": "B-bin%02d" % int(no),
                  "title": "Fable｜カードのコピー直し 便%s/%d（%s・%d曲）" % (no, len(bins), tier.replace("…", ""), n_keys),
                  "what": ("【全開便 10-18・カードのコピー直し】status/copy_queue_1018.md の「便%s」の%d曲（曲ページのキー一覧はそのmdの便%sの行。"
                           "直す理由（problems）は status/copy_queue_1018.json の rows で key を引く）。\n"
                           "流れ：調べる（出典）→ 書く → 別の目で照合（Claudeの別セッション＝claude -p --model claude-sonnet-5 で事実と出典を1件ずつ突き合わせ、合わないものは出さない）→ 公開。\n"
                           "決め（たまごさん 10-18 赤入れ）：①名前だけにしない。知らない人が押したくなる出典つきの事実を1つ。ポエム禁止。②題は2行に収まる長さ。"
                           "③アーティストの取り違え・違う動画はゼロ（sekisho-artist-song）。④書いた事実は2つ目の目で照合してから出す。⑤公式MVが複数ある曲は全部載せる。"
                           "コピーの書き方は bonjovi-ojisan-kobun（水道水コピー禁止）。\n"
                           "終わったら status/copy_queue_1018_done.jsonl に1曲1行（key・直した欄・出典URL・照合OK/NG）を足す。\n%s"
                           % (no, n_keys, no, MAMORU)),
                  "repo": JRS})

    C = [{"key": "C-karuku", "title": "Fable｜Macを軽く快適に：重い常駐・定期処理・一時ファイルの棚卸しと関所の直し",
          "what": ("【全開便 10-18・Macを軽く】\n"
                   "実測（10-18 05:36）：ロード平均24〜32（8コア）なのにCPU合計は約3コア分・メモリ空き83%%・ディスク空き200GB。"
                   "上位は Claude Helper・Typeless・Python（心臓の定期処理多数）・brctl（iCloud）・mds_stores（Spotlight）。"
                   "負荷判定（tools/fuka_hassha.py）はロード比で「固まる手前」と判断し、子が0本でも発車を止めていた。\n"
                   "やること：\n"
                   "1. 棚卸し：重い常駐（launchd・心臓 heartbeat.sh / top_status.py の相乗り・cron）と定期処理を、回数×1回の重さで並べ、"
                   "status/zenkai_1018/karuku_tanaoroshi.md と .json に出す（tools/jidou_tanaoroshi.py・tools/jidou_daicho.json を土台に）。\n"
                   "2. 一時ファイル：$TMPDIR・/private/tmp・作業場・中間物を一覧（場所・容量・作り直せるか）にして status/zenkai_1018/kesu_kouho.md に出す。"
                   "消すのは「作り直せるもの」だけ（sakujo-idou-kanmon の基準）。作り直せない物・迷う物は残す。"
                   "ブラウザ（Brave・Chrome）のフォルダ・壺と金庫には触らない（tools/browser_mamoru.py を必ず通す）。\n"
                   "3. 仕組み：同じ処理が重なって走る・数分おきが要らない頻度になっている係を、台帳に理由を書いて間引く（止めるのではなく頻度と重なりを直す）。"
                   "負荷判定はロード平均だけで止めず、CPU使用率とメモリ圧も見るように直す（--self-test を足す）。軽さを保つ関所（youryou_jougen・chukan_shimau・shimau）の穴も直す。\n"
                   "4. 直す前と後で、ロード平均・CPU合計・メモリ空き・空き容量を測って status/zenkai_1018/karuku_jissoku.json に残す。\n%s" % MAMORU),
          "repo": SHIN}]

    D = [
        {"key": "D-118370", "title": "Fable｜118370の続き：シティポップ告知動画を85点まで",
         "what": ("【全開便 10-18・進行中を止めずに続ける】118370番（シティポップ告知動画）の続き。\n"
                  "前回：v10b（13秒）を第三者採点で68点（合格線85点）。確認ページ https://tamago2022.github.io/tamago-shinchoku/share/check/118370-citypop-harakami-promo-v10b.html "
                  "・queue.json の118370番の what / result / inspections を全部読んでから始める。\n"
                  "やること：採点の減点理由を1つずつ潰して85点以上の版を作る（音の拍に合わせたカット・冒頭1秒で掴む・速いカット割り・タイポの衝突など、118370の確定仕様どおり）。"
                  "合格したら同じ型でレイ・ハラカミ版。納品は python3 tools/claude_nouhin.py put <ファイル> --anken その他 --saishin。予約・投稿はしない。"
                  "研究ノート（118369・タイポグラフィ映像）が status/ に出ていれば技の型として使う。\n%s" % MAMORU),
         "repo": SHIN},
        {"key": "D-recipe", "title": "Fable｜レシピレーダー3案（/food-radar-a・-b・-c）を仕上げて公開",
         "what": ("【全開便 10-18・進行中を止めずに続ける】レシピレーダー試作A/B/C（/food-radar-a・-b・-c）。"
                  "dispatch_outbox の food-radar-proto / food-radar-proto-2（main=93256fb0）が前回の到達点。本番の /food-radar は触らない。\n"
                  "やること：3案それぞれの見た目と中身（コンシェルジュのおすすめ在庫・出典）を仕上げ、比べやすい形にする。"
                  "公開はLovableの鍵が切れていれば「公開待ち（Lovableの鍵）」で止めて先へ。\n"
                  "別のセッションが今まさに同じものを触っている（30分以内のコミット）なら重ねて作らず、続きの1歩だけ足す。\n%s" % MAMORU),
         "repo": JRS},
        {"key": "D-genspark-haikan", "title": "Fable｜Genspark納品の配管（届いた納品を自動で受け取り→仕上げ→公開へ）",
         "what": ("【全開便 10-18・進行中を止めずに続ける】Genspark納品の配管。\n"
                  "いまの姿：GitHub joy-relief-station の Issue に【納品】が届くと「GHxxxx 納品の受け取り」便が積まれる（例 118284＝GH1015 月・118330＝GH1018 踊る）。"
                  "納品物は /Users/mac/tamago/_inbox/<Issue番号>/。gsk コマンド（tools/genspark_tanomu.py ほか）で Genspark のドライブから取る経路もある。\n"
                  "やること：前回までの到達点（status/ 配下の gsk・tsuki01・nouhin 関連、00_現在地.md の Genspark の行、dispatch_outbox）を読み、"
                  "届いた→受け取り→マガジンの型にそろえる→公開→Issueに完了、が人の手なしで通るように穴を埋める。"
                  "取りこぼし（届いているのに便が積まれていない納品）が無いかも洗う。新しい定期処理を足すなら tools/jidou_daicho.json に「作るもの・置き場・消す役」を書く。\n%s" % MAMORU),
         "repo": SHIN},
    ]
    return A, B, C, D


# 既存の便をFableレーンへ載せ替える（新しく積まずに、そのものを走らせる）
TSUKI_ODORU_NOTE = ("\n\n【10-18 全開便から追記】Fableで走らせる。仕上げはマガジンの確定型（怒れる人々 vol.1・tools/magazine/mag_build.py の MAGAZINE_KATA_1018）にそろえる："
                    "雰囲気の静止画5〜6枚（自由ライセンスだけ）・事実の裏取り・コンシェルジュの箸休め・燃え殻風の語り・5言語。"
                    "Lovableの鍵が切れていて公開が押せないときは main 合流まで進めて「公開待ち（Lovableの鍵）」と書いて終える（同じ理由で2回目の stuck にしない）。")
FLICKER_NOTE = ("\n\n【10-18 全開便から追記】Fableで走らせる。118368・118372・118564・119473 の中身もこの便でまとめてやる（同じ曲・同じ棚。別々に走らせると取り合いになるため4本は hold にした）。")


def main():
    dry = "--dry" in sys.argv
    A, B, C, D = build_items()
    # 並び：C → 怒れる人々 → B1 → 118370 → 以降 A と D と B を交互、残りの B
    order = []
    order.append(C[0])
    order.append(A[0])
    order.append(B[0])
    order.append(D[0])
    rest_a = A[1:]
    rest_d = D[1:]
    rest_b = B[1:]
    while rest_a or rest_d:
        if rest_a:
            order.append(rest_a.pop(0))
        if rest_b:
            order.append(rest_b.pop(0))
        if rest_d:
            order.append(rest_d.pop(0))
    order.extend(rest_b)

    added, skipped, moved = [], [], []
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        items = q.get("items") or []
        have = {it.get("zenkaiKey") for it in items if it.get("zenkaiKey")}
        next_n = max([int(it.get("n") or 0) for it in items] + [0]) + 1
        lane_order = 10
        for x in order:
            lane_order += 1
            if x["key"] in have:
                skipped.append(x["key"])
                continue
            it = {
                "n": next_n, "title": x["title"], "hyoudai": x["title"].replace("Fable｜", ""), "hyoudaiSrc": "rule",
                "why": "たまごさん指示（10-18 朝）：12:00まで全開・Fableでガンガン",
                "what": x["what"], "status": "waiting", "limitMin": 180,
                "model": FABLE, "fixedModel": FABLE, "fableLane": True, "fableLaneOrder": lane_order,
                "priority": 1, "urgent": True, "origin": "user", "queuedAt": NOW,
                "repo": x["repo"], "zenkaiKey": x["key"], "costsMoney": False,
            }
            if cost_risk.is_cost_risk(it) or cost_risk.is_fal_task(it):
                it["costsMoney"] = True  # 本当にお金の匂いがあれば止める（守る）
            items.append(it)
            added.append((next_n, x["key"]))
            next_n += 1
        # 既存の便を載せ替え
        by_n = {it.get("n"): it for it in items}
        for n, order_no, note in ((118284, 12, TSUKI_ODORU_NOTE), (118330, 13, TSUKI_ODORU_NOTE),
                                  (118557, 15, FLICKER_NOTE), (118369, 16, "")):
            it = by_n.get(n)
            if not it or it.get("zenkaiMoved"):
                continue
            if it.get("status") not in ("waiting",):
                continue
            it["fixedModel"] = FABLE
            it["model"] = FABLE
            it["fableLane"] = True
            it["fableLaneOrder"] = order_no
            it["zenkaiMoved"] = NOW
            it["priority"] = 1
            if note:
                it["what"] = (it.get("what") or "") + note
            moved.append(n)
        for n in (118368, 118372, 118564, 119473):
            it = by_n.get(n)
            if it and it.get("status") == "waiting" and not it.get("zenkaiMoved"):
                it["status"] = "hold"
                it["holdNote"] = "10-18 全開便：118557番（Fable）にまとめた"
                it["zenkaiMoved"] = NOW
                moved.append(n)
        if not dry:
            ok = queue_store.save_queue(q, snapshot=snap)
            if not ok:
                print("save_queue が拒否しました")
                return 2
    print("積んだ %d便 / 既にあった %d / 載せ替え %s" % (len(added), len(skipped), moved))
    for n, k in added:
        print(n, k)
    if not dry and added:
        try:
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": NOW, "n": "zenkai-1018", "type": "info",
                                    "title": "全開（〜12:00）：Fable便を%d本積みました（A マガジン%d・B コピー%d・C 1・D %d）＋既存%d本をFableへ"
                                    % (len(added), len(A), len(B), len(D), len([m for m in moved if m in (118284, 118330, 118557, 118369)]))},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
