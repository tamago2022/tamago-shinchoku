#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仕入れ候補の動画を「機械が確かめられるところまで」確かめる（2026-09-22）。

■ なぜ要るか
  たまごさん：「公式チャンネルか／静止画だけでないか。静止画だけの動画は候補から外す。」
  前の回は候補28件が**全件『未確認』**のまま残っていた。
  人が1本ずつ開くやり方では次の回もまた全件未確認になる。だから機械に一段やらせる。

■ 何ができて、何ができないか（ここを曖昧にしない）
  できる ○ その動画が**誰のチャンネルに載っているか**（oEmbed の author_name / author_url）
        ○ 自動生成の「◯◯ - Topic」チャンネルかどうか
          ── これは YouTube が音源から自動で作る枠で、**画は静止画1枚**（いわゆる art track）。
             つまり「静止画だけ」を機械で確実に落とせる唯一の手がかりがここ。
        ○ 動画がそもそも生きているか（消えている／非公開なら oEmbed が落ちる）
  できない ×**中身が動いているかを目で見ること。**
             Topic ではない普通のチャンネルでも、静止画1枚のリリック動画はありうる。
             だからこの道具は「静止画だけでないことを確かめた」とは**言わない**。
             言えるのは「Topic ではない＝自動生成の静止画枠ではない」まで。
             そこから先は人が見る。**取れていないものは取れていないと書く。**

■ 使う先（0円・鍵なし）
  https://www.youtube.com/oembed?url=...&format=json だけ。ここ以外は叩かない。
  POSTもしない。認証もしない。よって**課金0**。

■ 呼ばれ方
  gaibu_kuchi.enqueue_job("douga", {"videos": [{"n":1,"name":"...","url":"https://youtu.be/..."}]})
"""
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

ALLOW = "https://www.youtube.com/oembed"
UA = "tamago-douga/1.0 (+shiire)"

# 自動生成の「静止画1枚」枠。ここに載っているものは候補から外す。
TOPIC_RE = re.compile(r"\s-\sTopic$")
# 素人カバー・切り抜き。題名の段階で落とす（skill sekisho-artist-song）。
NG_WORDS = ("歌ってみた", "弾いてみた", "cover by", "カラオケ", "karaoke",
            "耳コピ", "fan made", "fanmade", "ai cover", "切り抜き",
            "作業用", "1時間耐久", "睡眠用", "reaction", "リアクション")

VID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([0-9A-Za-z_-]{11})")


def video_id(url):
    m = VID_RE.search(url or "")
    return m.group(1) if m else None


def _one(item):
    url = (item or {}).get("url") or ""
    r = {"n": item.get("n"), "name": item.get("name"), "url": url,
         "verdict": "取れていない"}
    vid = video_id(url)
    if not vid:
        r["why"] = "YouTubeの動画IDが読み取れないURLです"
        return r
    watch = "https://www.youtube.com/watch?v=%s" % vid
    q = "%s?url=%s&format=json" % (ALLOW, urllib.parse.quote(watch, safe=""))
    try:
        req = urllib.request.Request(q, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20,
                                    context=ssl.create_default_context()) as res:
            j = json.loads(res.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        # 401/403/404 はだいたい「消えた・非公開・埋め込み禁止」
        r["why"] = "oEmbedがHTTP %d（消えた／非公開／埋め込み禁止のいずれか）" % e.code
        r["verdict"] = "外す"
        return r
    except Exception as e:
        r["why"] = "%s: %s" % (type(e).__name__, str(e)[:160])
        return r

    author = j.get("author_name") or ""
    r.update({"title": j.get("title"), "channel": author,
              "channelUrl": j.get("author_url"), "src": q})
    low = ("%s %s" % (j.get("title") or "", author)).lower()
    if TOPIC_RE.search(author):
        r["verdict"] = "外す"
        r["why"] = ("自動生成の「%s」チャンネル＝画は静止画1枚(art track)。"
                    "たまごさんの指示どおり候補から外す。" % author)
        return r
    if any(w in low for w in NG_WORDS):
        r["verdict"] = "外す"
        r["why"] = "題名かチャンネル名に素人カバー・切り抜きの語がある"
        return r
    r["verdict"] = "Topicではない（静止画だけかは人が見る）"
    r["why"] = ("チャンネル「%s」に載っている。自動生成の静止画枠ではない。"
                "★公式本人かどうか・画が動くかどうかは、ここでは確かめていない。" % author)
    return r


def run_job(payload):
    vids = (payload or {}).get("videos") or []
    out = []
    for it in vids[:60]:
        out.append(_one(it))
        time.sleep(0.4)
    keep = [x for x in out if x["verdict"].startswith("Topicではない")]
    drop = [x for x in out if x["verdict"] == "外す"]
    unk = [x for x in out if x["verdict"] == "取れていない"]
    return {"ok": True, "checked": len(out), "keep": len(keep),
            "drop": len(drop), "notTaken": len(unk),
            "results": out, "totalYen": 0.0}


if __name__ == "__main__":
    import sys
    print(json.dumps(run_job({"videos": [
        {"n": i + 1, "url": u} for i, u in enumerate(sys.argv[1:])]}),
        ensure_ascii=False, indent=1))
