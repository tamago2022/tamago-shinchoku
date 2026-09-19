#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""976番：【珍獣ラシコル】の審査通過を「LINE STOREの公開ページ」から見張る。

たまごさん（2026-09-20）：
  「メールを読む道は諦めました。別の道でやります。」
  「審査が通ったら、LINE STOREに販売ページが公開される。ログインも鍵も要らない。
    外から見える。つまりメールを読む必要は最初から無かった。」
  「新しい常駐を増やさない。既にある5分便に乗せる。」

━━━ 974番（check_line_shinsa.py）との関係 ━━━
974番は Gmail を IMAP で読む見張り。鍵（アプリパスワード）が
/Users/mac/.tamago/gmail_app_password に無いため、2026-09-20 05:04 時点で
state に "blocked": "no_credential" が立ったまま **一度も審査結果を見ていない。**
この976番は、その鍵をまるごと迂回する。974番は消さない（鍵が置かれれば勝手に復活する）。

━━━ 見る場所（全部ログイン不要の公開ページ）━━━
  ① 検索          https://store.line.me/search/sticker/ja?q=珍獣ラシコル
  ② 検索API       https://store.line.me/api/search/sticker?query=... （①のSPAが内部で叩く口）
  ③ 作者ページ    https://store.line.me/stickershop/author/<id>/ja
     作者idは実測で突き止める。既刊「さりげなうんこ2」＝product/23291162 の
     ページに作者リンクが入っているので、そこから1回だけ拾って status に控える。
     （たまごさんの過去ツイート share/x-archive/tweets_data_2.json に載っていたURL）

━━━ この見張りで分かること・分からないこと（正直に）━━━
  ○ 通った  → 公開ページが出るので、外から確実に分かる。
  ✕ 落ちた  → 外からは**分からない。**落ちても店には何も出ないため。
     「まだ出ていない」＝「審査中」と「落ちた」の両方を含む。断定しない。

━━━ 重さ ━━━
5分便から呼ばれる。中で MIN_INTERVAL_SEC に間引くので、何度呼ばれても外へ出るのは
5分に1回・GETが1〜3本だけ。新しいlaunchd常駐は作らない。

━━━ 通知 ━━━
status/dispatch_outbox.jsonl に1行だけ積む（974番と同じ、たまごさんに1行で届く道）。
同じことは二度言わない（.line_store_found フラグ）。
通知に載せるURLは、**自分でGETして200を確認したものだけ。**
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = "/Users/mac/Desktop/tamago-shinchoku"
STATE = os.path.join(ROOT, "status", "line_store_watch.json")
FOUND_FLAG = os.path.join(ROOT, "status", ".line_store_found")
OUTBOX = os.path.join(ROOT, "status", "dispatch_outbox.jsonl")
JST = timezone(timedelta(hours=9))

STICKER_NAME = "珍獣ラシコル"
KNOWN_PRODUCT = "23291162"          # 既刊。作者idを拾うためだけに使う
MIN_INTERVAL_SEC = 300              # 5分。5分便から何度呼ばれてもここで間引く
TIMEOUT = 20

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

PRODUCT_RE = re.compile(r"/stickershop/product/(\d+)")
AUTHOR_RE = re.compile(r"/stickershop/author/([A-Za-z0-9._%-]+)")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
COUNT_RE = re.compile(r"([0-9,]+)\s*件")


def marks(body):
    """『どう返っているか』の控え。実測の跡を残すためだけの、判定に使わない欄。

    ★注意：検索ページのHTMLは、結果が0件でも検索語をそのまま <title> や
      検索窓のvalueに埋めて返す。つまり **『珍獣ラシコル』という文字がある＝出ている、では無い。**
      判定に使ってよいのは商品リンク(/stickershop/product/<id>)が在るかどうかだけ。
    """
    t = TITLE_RE.search(body)
    c = COUNT_RE.search(body)
    return {
        "title": re.sub(r"\s+", " ", t.group(1)).strip()[:120] if t else "",
        "countText": c.group(0) if c else "",
        "productLinks": sorted(set(PRODUCT_RE.findall(body)))[:12],
    }


def now():
    return datetime.now(JST)


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(st):
    st["lastRunAt"] = now().isoformat()
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, STATE)


def get(url, accept_json=False):
    """戻り値: (status_code, body_text, final_url)。例外は投げない。"""
    h = dict(HEADERS)
    if accept_json:
        h["Accept"] = "application/json, text/plain, */*"
        h["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            try:
                body = raw.decode("utf-8", errors="replace")
            except Exception:
                body = ""
            return r.getcode(), body, r.geturl()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body, url
    except Exception as e:
        return 0, "ERR:%s" % e, url


def notify(title, message, n):
    rec = {
        "ts": now().isoformat(),
        "n": n,
        "type": "line_store_watch",
        "title": title,
        "message": message,
    }
    os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def discover_author(st):
    """既刊の商品ページから作者idを1回だけ拾う。拾えたら控えて二度と叩かない。"""
    if st.get("authorId"):
        return st["authorId"]
    if st.get("authorDiscoveryTried", 0) >= 3:
        return None
    url = "https://store.line.me/stickershop/product/%s/ja" % KNOWN_PRODUCT
    code, body, _ = get(url)
    st["authorDiscoveryTried"] = st.get("authorDiscoveryTried", 0) + 1
    st["authorDiscovery"] = {"url": url, "code": code, "bytes": len(body)}
    if code == 200:
        m = AUTHOR_RE.search(body)
        if m:
            st["authorId"] = m.group(1)
            return st["authorId"]
    return None


def scan_for_sticker(body):
    """本文の中に『珍獣ラシコル』の商品リンクがあるか。あれば商品idを返す。"""
    if STICKER_NAME not in body:
        return None
    # 商品名の近く（前後1200字）に出てくる product id を拾う
    for m in re.finditer(re.escape(STICKER_NAME), body):
        window = body[max(0, m.start() - 1200): m.start() + 1200]
        pm = PRODUCT_RE.search(window)
        if pm and pm.group(1) != KNOWN_PRODUCT:
            return pm.group(1)
    pm = PRODUCT_RE.search(body)
    if pm and pm.group(1) != KNOWN_PRODUCT:
        return pm.group(1)
    return None


def main():
    force = "--force" in sys.argv
    st = load_state()

    if os.path.exists(FOUND_FLAG) and not force:
        return 0

    last = st.get("lastCheckedEpoch", 0)
    if not force and (time.time() - last) < MIN_INTERVAL_SEC:
        return 0

    probes = []
    hit_product = None
    hit_via = None

    q = urllib.parse.quote(STICKER_NAME)

    # ① 検索ページ（HTML）
    u1 = "https://store.line.me/search/sticker/ja?q=%s" % q
    c1, b1, _ = get(u1)
    probes.append({"name": "search_html", "url": u1, "code": c1, "bytes": len(b1),
                   "hasName": STICKER_NAME in b1, "marks": marks(b1)})
    if c1 == 200:
        p = scan_for_sticker(b1)
        if p:
            hit_product, hit_via = p, "search_html"

    # ② 検索API（JSON）
    if not hit_product:
        u2 = ("https://store.line.me/api/search/sticker?query=%s&offset=0&limit=36"
              "&type=ALL&includeFacets=false" % q)
        c2, b2, _ = get(u2, accept_json=True)
        probes.append({"name": "search_api", "url": u2, "code": c2, "bytes": len(b2),
                       "hasName": STICKER_NAME in b2, "body": b2[:300]})
        # ★JSONには /stickershop/product/ という文字列が入らないので、
        #   HTML用の scan_for_sticker は使えない（使うと永久に見つからない）。
        #   実測した未公開時の中身：{"totalCount":0,"items":[],"facets":[]}
        #   → totalCount と items[].title を直接見る。ここが一番確かな口。
        if c2 == 200:
            try:
                data = json.loads(b2)
            except Exception:
                data = {}
            for item in (data.get("items") or []):
                title = str(item.get("title") or item.get("name") or "")
                if STICKER_NAME in title:
                    pid = str(item.get("id") or item.get("productId") or "")
                    if pid.isdigit():
                        hit_product, hit_via = pid, "search_api"
                        break

    # ③ 作者ページ
    author = discover_author(st)
    if author and not hit_product:
        u3 = "https://store.line.me/stickershop/author/%s/ja" % author
        c3, b3, _ = get(u3)
        probes.append({"name": "author_page", "url": u3, "code": c3, "bytes": len(b3),
                       "hasName": STICKER_NAME in b3, "marks": marks(b3)})
        if c3 == 200:
            p = scan_for_sticker(b3)
            if p:
                hit_product, hit_via = p, "author_page"

    # ★1回だけ：Creators Market側に「審査の状態を外から取れる公開の口」が有るかを実測する。
    #   結論を書き置くためだけの確認。深追いしない（1回きり・以後は叩かない）。
    #   このスクリプトはCookieを1つも持たないので、送るのはただのGET＝管理画面には何も起きない。
    if "creatorProbe" not in st:
        cu = "https://creator.line.me/ja/mypage/"
        cc, cb, cfinal = get(cu)
        st["creatorProbe"] = {
            "at": now().isoformat(), "url": cu, "code": cc,
            "finalUrl": cfinal, "bytes": len(cb),
            "note": "審査状態はログインの向こうにしか無い＝外から取れる公開の口は無い、"
                    "という判断の根拠。だから店（store.line.me）側を見ている。",
        }

    st["lastCheckedEpoch"] = time.time()
    st["lastCheckedAt"] = now().isoformat()
    st["probes"] = probes
    st["published"] = bool(hit_product)

    # 初回は「出ていない状態」を基準として控える
    if "baseline" not in st:
        st["baseline"] = {"at": now().isoformat(), "probes": probes,
                          "note": "この時点では未公開。以後はここからの差分で見る。"}

    if hit_product:
        product_url = "https://store.line.me/stickershop/product/%s/ja" % hit_product
        code, body, _ = get(product_url)          # ★渡す前に自分で200を確認する
        st["productUrl"] = product_url
        st["productUrlCode"] = code
        if code == 200 and STICKER_NAME in body:
            notify(
                "【珍獣ラシコル】審査通りました",
                "🎉【珍獣ラシコル】審査通りました。販売ページ：%s （%s で発見・200確認済み）"
                % (product_url, hit_via),
                "976-line-store-published",
            )
            open(FOUND_FLAG, "w").write(now().isoformat())
            st["notifiedAt"] = now().isoformat()
        else:
            # 見つけたのに200で本人だと確認できない＝断定しない。次の便でやり直す。
            st["published"] = False
            st["pendingVerify"] = {"product": hit_product, "code": code}

    save_state(st)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
