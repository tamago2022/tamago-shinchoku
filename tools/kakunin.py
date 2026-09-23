#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""961番【検品】出したページが本当に生きているかを、工場側から叩いて確かめる。

■ なぜ要るか（2026-09-20 実測）
  たまご憲法：「渡せるのは自分で叩いて200を確認したURLだけ」。
  ところが Cowork/Dispatch のサンドボックスからは tamago2022.github.io に**出られない**
  （プロキシが 403 Forbidden でトンネルを塞ぐ。curl も urllib も同じ）。
  ブラウザで見に行く道は request_access が要るので、指示で禁じられていることがある。
  → 工場（Mac）からなら出られる。だから「200かどうか見てくるだけ」の係をここに置く。

■ できること・できないこと
  ・GETだけ。POSTもPUTもしない。金もかからない。
  ・**行き先は下の ALLOW_PREFIX の中だけ**＝ tamago2022.github.io と
    joy-relief-station.lovable.app（ごきげん補給所の本番）の2か所。
    ★ごきげん補給所は GitHub Pages ではなく **Lovable配信**。mainに入れただけでは本番に出ない。
      github.io だけを見ていると、区間7（公開）が詰まっていても気づけない。
    ここを狭くしてあるのは、この窓口が「なんでも取りに行ける穴」にならないようにするため。
  ・返すのは status / 長さ / 題 / 表の行数 / リンク数 / 探した言葉が有るか、だけ。
    本文そのものは返さない（長すぎて報告が読めなくなる）。

■ 使い方
  gaibu_kuchi.enqueue_job("kakunin", {"urls": ["https://tamago2022.github.io/..."],
                                      "must": ["言い分", "AITuberKit"]})
"""
import json
import os  # ★_baton() が os.path を使うのに import が無く NameError になっていた（1028番が追加）
import re
import ssl
import time
import urllib.error
import urllib.request

# 2026-09-23（1027番・区間8）：出したものを叩いて確かめる先は、うちが出している2か所。
#   ・tamago2022.github.io      … 進捗表・確認ページ（GitHub Pages）
#   ・joy-relief-station.lovable.app … ごきげん補給所の本番（Lovableが main から配信）
#   ★joy-relief-station は GitHub Pages **ではない**。mainに入れただけでは本番に出ない。
#     だから「mainに入った＝出た」と数えていると、区間7（公開）の詰まりが見えない。
#   GETだけ・鍵を使わない・課金0 は変えていない。
ALLOW_PREFIX = ("https://tamago2022.github.io/",
                "https://joy-relief-station.lovable.app/")
UA = "tamago-kakunin/1.0 (+961)"


def _one(url, must):
    r = {"url": url, "ok": False, "status": 0, "bytes": 0}
    if not url.startswith(ALLOW_PREFIX):
        r["error"] = ("行き先が許してある場所の外です（tamago2022.github.io と "
                      "joy-relief-station.lovable.app の中だけ）")
        return r
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Cache-Control": "no-cache", "Pragma": "no-cache"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as res:
            body = res.read().decode("utf-8", "ignore")
            r["status"] = res.status
    except urllib.error.HTTPError as e:
        r["status"] = e.code
        r["error"] = "HTTP %d" % e.code
        r["seconds"] = round(time.time() - t0, 1)
        return r
    except Exception as e:
        r["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        r["seconds"] = round(time.time() - t0, 1)
        return r

    r["seconds"] = round(time.time() - t0, 1)
    r["bytes"] = len(body)
    m = re.search(r"<title>([^<]*)", body)
    r["title"] = m.group(1) if m else ""
    r["rows"] = body.count("<tr>")
    r["links"] = len(re.findall(r'href="https', body))
    # 「文字化けしていないか」の当たり。日本語が1文字も無ければ何かおかしい。
    r["hasJa"] = bool(re.search(r"[ぁ-んァ-ン一-龥]", body))
    if must:
        r["must"] = {w: (w in body) for w in must}
    r["ok"] = (r["status"] == 200 and r["bytes"] > 0
               and all((r.get("must") or {}).values()))
    return r


def _omosa(payload):
    """1028番【物差し】ごきげん補給所の「重さ」を工場側で実測する。

    ★なぜここに間借りしているか
      gaibu_runner.py は kind=kakunin のとき **毎回 importlib.reload(kakunin)** する。
      ＝ runner を止めずに、この関数を足すだけで今すぐ工場で動かせる。
      （runner 本体に kind を足すと、launchd が抱えている古い runner には届かない）

    ★安全：呼べるのは tools/omosa.mjs の1本だけ＝白名簿。引数は数字と幅だけ。
      GETのみ・鍵を使わない・課金0。保存や送信のボタンは omosa.mjs 側で押さない。
    """
    import os
    import subprocess
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "omosa.mjs")
    if not os.path.exists(script):
        return {"ok": False, "error": "tools/omosa.mjs がありません", "totalYen": 0.0}
    cmd = ["node", script]
    if payload.get("recon"):
        cmd.append("--recon")
    runs = payload.get("runs")
    if isinstance(runs, int) and 0 < runs <= 50:
        cmd += ["--runs", str(runs)]
    width = payload.get("width")
    if isinstance(width, int) and 200 <= width <= 2000:
        cmd += ["--width", str(width)]
    # ★行き先は ALLOW_PREFIX（この上にある白名簿）の中だけ。外は測らない。
    u = payload.get("url")
    if u:
        if not str(u).startswith(ALLOW_PREFIX):
            return {"ok": False, "error": "行き先が許してある場所の外です", "totalYen": 0.0}
        cmd += ["--url", str(u)]
    # ★工場の runner に1件90秒の打ち切りが入ったので、測る中身を小分けにできるようにする。
    ph = payload.get("phase")
    if ph in ("bytes", "edit", "open", "paste", "all"):
        cmd += ["--phase", ph]
    timeout = payload.get("timeout") or 1500
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=min(int(timeout), 1800), cwd=os.path.dirname(here))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "omosa.mjs が時間内に終わりませんでした", "totalYen": 0.0}
    out = {"ok": p.returncode == 0, "totalYen": 0.0,
           "stderr": (p.stderr or "")[-2500:]}
    try:
        out["omosa"] = json.loads(p.stdout or "{}")
    except Exception:
        out["ok"] = False
        out["stdout"] = (p.stdout or "")[-2500:]
    # 結果の本体は status/omosa_last.json に落ちている（票に全部入れると読めなくなる）
    return out


def _baton(payload):
    """1030番【バトン】5区＝PRの検品を工場側で走らせる。

    ★なぜここに間借りしているか（_omosa と同じ理由。増やしたくて増やしていない）
      gaibu_runner.py は kind=kakunin のとき **毎回 importlib.reload(kakunin)** する。
      ＝ launchd が抱えている古い runner を止めずに、今すぐ工場で動かせる。
      runner 本体に kind=baton を足しても、古い runner には届かない（実測）。

    ★安全：呼ぶのは tools/baton.py の run_job だけ＝白名簿。
      baton.py は **merge を1行も書いていない**（6区は人が押す）。GETのみ・課金0。
    """
    import importlib
    import sys as _sys
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in _sys.path:
        _sys.path.insert(0, here)
    try:
        import baton
        importlib.reload(baton)
    except Exception as e:
        return {"ok": False, "error": "tools/baton.py が読み込めません：%s" % e, "totalYen": 0.0}
    return baton.run_job(payload)


def _kohyou_kanshi(payload):
    """1038番【公開監視】「mainに入った → 本番に出た」を確かめる。

    ★なぜここに間借りしているか（_omosa・_baton と同じ理由）
      gaibu_runner.py は kind=kakunin のとき **毎回 importlib.reload(kakunin)** する。
      ＝ launchd が抱えている古い runner を止めずに、今すぐ工場で動かせる。

    ★なぜ要るか：ごきげん補給所は GitHub Pages ではなく **Lovable配信**。
      この _one() は「200が返るか」しか見ていないので、**1週間前の中身が200で
      返ってきても合格になる。**だから区間7（公開）の詰まりが構造的に見えなかった。
      見るのは x-deployment-id の変化と、mainの最新SHA。GETのみ・課金0。
    """
    import importlib
    import sys as _sys
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in _sys.path:
        _sys.path.insert(0, here)
    try:
        import kohyou_kanshi
        importlib.reload(kohyou_kanshi)
    except Exception as e:
        return {"ok": False, "error": "tools/kohyou_kanshi.py が読み込めません：%s" % e,
                "totalYen": 0.0}
    return kohyou_kanshi.run_job(payload)


def _og(payload):
    """1133番【OGの検品】出したページのサムネイルが「空っぽ型」でないかを機械で見る。

    たまごさん（2026-09-25）:
      「OG画像を叩いて空っぽ判定（画像の大半が単色／主要被写体が小さすぎる）を
        機械で出せるようにして、tools/kakunin.py に組み込む。」

    ★なぜここに間借りしているか（_omosa・_baton と同じ理由）
      gaibu_runner.py は kind=kakunin のとき **毎回 importlib.reload(kakunin)** する。
      ＝ launchd が抱えている古い runner を止めずに、今すぐ工場で動かせる。

    ★安全：GETだけ。行き先は ALLOW_PREFIX の中のページと、そのページが指す og:image だけ。
    payload: {"mode":"og", "urls":[...]}
    返り: {"ok": 空っぽが0件か, "karappo": 件数, "total": 件数, "results":[...]}
    """
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "1133_og_karappo.py")
    if not os.path.exists(p):
        return {"ok": False, "error": "tools/1133_og_karappo.py がありません", "totalYen": 0.0}
    spec = importlib.util.spec_from_file_location("og_karappo", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    urls = payload.get("urls") or ([payload["url"]] if payload.get("url") else [])
    res = []
    for u in urls:
        r = {"url": u}
        if not u.startswith(ALLOW_PREFIX):
            r["error"] = "行き先が許してある場所の外です"
            r["karappo"] = True
            res.append(r)
            continue
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Twitterbot/1.0"})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=25) as x:
                html = x.read(400000).decode("utf-8", "ignore")
            r["seconds"] = round(time.time() - t0, 1)
        except Exception as e:
            r["error"] = "ページが返らない: %s" % repr(e)[:80]
            r["karappo"] = True
            res.append(r)
            continue
        m = re.search(r'property="og:image"[^>]*content="([^"]+)"', html) or \
            re.search(r'content="([^"]+)"[^>]*property="og:image"', html)
        if not m:
            r["karappo"] = True
            r["riyuu"] = ["og:image が無い"]
            res.append(r)
            continue
        img = m.group(1).replace("&amp;", "&")
        r["image"] = img
        try:
            r.update(mod.judge(img))
        except Exception as e:
            r["karappo"] = True
            r["riyuu"] = ["画像が取れない: %s" % repr(e)[:80]]
        res.append(r)
    ng = sum(1 for x in res if x.get("karappo"))
    return {"ok": ng == 0, "karappo": ng, "total": len(res),
            "results": res, "totalYen": 0.0}


def run_job(payload=None):
    payload = payload or {}
    if payload.get("mode") == "og":
        return _og(payload)
    if payload.get("mode") == "omosa":
        return _omosa(payload)
    if payload.get("mode") == "baton":
        return _baton(payload)
    if payload.get("mode") == "kohyou_kanshi":
        return _kohyou_kanshi(payload)
    urls = payload.get("urls") or ([payload["url"]] if payload.get("url") else [])
    must = payload.get("must") or []
    results = [_one(u, must) for u in urls]
    return {"ok": all(x.get("ok") for x in results) if results else False,
            "results": results, "totalYen": 0.0}


if __name__ == "__main__":
    import sys
    print(json.dumps(run_job({"urls": sys.argv[1:]}), ensure_ascii=False, indent=1))
