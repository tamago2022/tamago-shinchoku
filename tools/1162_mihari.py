#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1162番【LINEスタンプ審査の見張り】ラシコルが公開されたら自動で気づく（2026-09-26）

たまごさん：「審査状況が自動で分かる仕組みを作って。毎日見に行って、変わったら進捗表に出して」

■ 976番（tools/line_store_watch.py）との関係
  976番は「珍獣ラシコル」という**名前で検索**して探す見張り。今回のスタンプは
  英語名（Rashikoru the Mysterious Forest Beast）で、名前検索では引っかからない。
  こちらは**スタンプIDを直接叩く**ので取り違えようがない。976番は消さない。

■ 何を見るか（ログイン不要の、外から見える唯一の確実な事実）
  LINE STORE の商品ページ  https://store.line.me/stickershop/product/<ID>/ja
    ・審査が終わっていない間 → 「アイテムが見つかりません」
    ・審査が通って公開された → 商品名が載ったページが出る
  creator.line.me のマイページはログインが要るので機械では見に行けない。
  だから「公開されたかどうか」を外から確認する。これは推測ではなく実物の応答。

■ 残すもの
  status/1162_shinsa.json   いまの状態（1件）
  status/1162_shinsa.jsonl  見に行った記録（1行1回・直近400行）

■ 動かし方
  tools/top_status.py（心臓が15秒おきに呼ぶ）の末尾から投げっぱなしで呼ぶ。
  3時間たっていなければ即座に戻るので、心臓は重くならない。

止め方: status/1162.stop を置く
戻し方: git checkout -- tools/top_status.py && rm -f tools/1162_mihari.py tools/1162_page.py 1162-rashikoru.html
"""
import io
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
JST = timezone(timedelta(hours=9))
KANKAKU = 3 * 60 * 60  # 3時間おき
MAX_GYOU = 400

SETTEI = os.path.join(ST, "1162_settei.json")
IMA = os.path.join(ST, "1162_shinsa.json")
LOG = os.path.join(ST, "1162_shinsa.jsonl")
STOP = os.path.join(ST, "1162.stop")

KIHON = {
    "stickerId": "47502978",
    "name": "Rashikoru the Mysterious Forest Beast",
    "nameJa": "ラシコル",
    # 審査リクエスト日。ちがっていたらここを直すだけでよい。
    "shinseiDate": "2026-09-21",
    # LINE公式の案内：審査完了まで1ヶ月ほど。個別の審査状況の問い合わせは
    # 「リクエストから1か月以上」経たないとフォームが受け付けない（2026-09-26 実測）。
    "toiawaseKanoubi": "2026-10-21",
}


def settei():
    d = dict(KIHON)
    try:
        d.update(json.load(io.open(SETTEI, encoding="utf-8")))
    except Exception:
        pass
    return d


def mite_kuru(sticker_id):
    """LINE STOREの商品ページを1回だけ見に行く。返すのは実物の応答だけ。"""
    url = "https://store.line.me/stickershop/product/%s/ja" % sticker_id
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
        "Accept-Language": "ja",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.getcode()
            honbun = r.read(200000).decode("utf-8", "replace")
    except Exception as e:
        return {"ok": False, "url": url, "error": type(e).__name__}

    minai = ("アイテムが見つかりません" in honbun) or ("Item not found" in honbun)
    return {
        "ok": True,
        "url": url,
        "code": code,
        "koukai": (not minai),
        "state": "公開された" if not minai else "審査中（まだ公開されていない）",
    }


def main():
    if os.path.exists(STOP):
        return
    try:
        if time.time() - os.path.getmtime(IMA) < KANKAKU:
            return
    except OSError:
        pass

    s = settei()
    now = datetime.now(JST)
    r = mite_kuru(s["stickerId"])

    try:
        t0 = datetime.strptime(s["shinseiDate"], "%Y-%m-%d").replace(tzinfo=JST)
        keika = (now.date() - t0.date()).days
    except Exception:
        keika = None

    mae = {}
    try:
        mae = json.load(io.open(IMA, encoding="utf-8"))
    except Exception:
        pass

    ima = {
        "t": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "stickerId": s["stickerId"],
        "name": s["name"],
        "nameJa": s["nameJa"],
        "shinseiDate": s["shinseiDate"],
        "keikaNissu": keika,
        "toiawaseKanoubi": s["toiawaseKanoubi"],
        "storeUrl": r.get("url"),
        "state": r.get("state", "確認できなかった"),
        "koukai": r.get("koukai"),
        "ok": r.get("ok"),
        "error": r.get("error"),
        "kawatta": (mae.get("state") not in (None, r.get("state"))),
    }

    try:
        os.makedirs(ST, exist_ok=True)
        with io.open(IMA, "w", encoding="utf-8") as f:
            json.dump(ima, f, ensure_ascii=False, indent=1)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": ima["t"], "state": ima["state"],
                                "ok": ima["ok"]}, ensure_ascii=False) + "\n")
        with io.open(LOG, encoding="utf-8") as f:
            gyou = f.readlines()
        if len(gyou) > MAX_GYOU:
            with io.open(LOG, "w", encoding="utf-8") as f:
                f.writelines(gyou[-MAX_GYOU:])
    except Exception:
        pass

    # 表を作り直す
    try:
        subprocess.run(["python3", os.path.join(HERE, "1162_page.py")],
                       timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


if __name__ == "__main__":
    main()
