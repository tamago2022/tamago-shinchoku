#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番【本丸】頼む — 外部AIに「仕事」を投げて、**成果物がこっちに落ちてくる**ようにする。

たまごさんの言葉（2026-09-18・原文）:
  「『このネタでジェミニに世界中リサーチしといて』『YouTubeリサーチさせてレポート上げといて』
    『今1番伸びてるサイト探しといて』みたいなこともできますか？
    ジェミニだって画像が作れるわけじゃん。ジェミニにイメージ作らせたやつが、
    こっちにClaudeに上がってくるのか、もしくは俺がジェミニに覗きに行ったらもうできてるのか、
    そういうことができるんですか？」

■ kiku.py との違い
  kiku.py … 聞く（答えが画面に出る）
  このファイル … **頼む**。成果物がファイルとして残る。あとから何度でも見に行ける。

■ 成果物の置き場（★ここだけ覚えればいい）
  status/gaibu_seika/<日付>_<社名>_<件名>/
      report.txt / report.md / image.png / _meta.json（何を頼んで何円かかったか）
  たまごさんが向こうの画面に見に行く必要はない。**全部ここに落ちる。**

■ 逆向き（たまごさんが向こうの画面で作ったものを、こちらが拾う）
  ★**status/gaibu_seika/_inbox/ に入れてください。**そこに置けば工場が拾って台帳に載せます。
  （画像でもテキストでも何でも可。`python3 tools/tanomu.py --inbox` で取り込む）

■ 使い方
  python3 tools/tanomu.py research "日本のカバー曲紹介サイトで今1番伸びているのはどこか" --ai gemini
  python3 tools/tanomu.py youtube  "1人で作る映像作品のチャンネルで直近伸びているもの" --ai gemini
  python3 tools/tanomu.py image    "夜の商店街、卵の看板、昭和の湿度、16:9" --ai gemini
  python3 tools/tanomu.py --list
  python3 tools/tanomu.py --inbox
"""
import argparse
import base64
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402
import kyoyu_brief  # noqa: E402

SEIKA = os.path.join(REPO, "status", "gaibu_seika")
INBOX = os.path.join(SEIKA, "_inbox")
LEDGER = os.path.join(REPO, "status", "gaibu_seika_ledger.jsonl")

GEMINI_IMAGE_MODELS = ["gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"]
XAI_IMAGE_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_MODELS = ["grok-2-image-1212", "grok-2-image"]

SHIGOTO = {
    "research": (
        "あなたはリサーチ担当です。下の依頼について、**実在する情報源を検索して**調べ、報告書を書いてください。\n"
        "必ずこの形で書いてください：\n"
        "# 結論（3行）\n"
        "# 分かったこと（箇条書き・それぞれに出典URL）\n"
        "# 数字（分かる範囲で。推測には『推測』と明記）\n"
        "# たまごさんが次にやるといいこと（3つ・すぐ着手できる粒度で）\n"
        "# 調べきれなかったこと（正直に）\n"
        "URLは実在するものだけ。作らないでください。見つからなければ『見つからなかった』と書いてください。"
    ),
    "youtube": (
        "あなたはYouTubeリサーチ担当です。下のテーマについて、**実際にYouTube上で検索して**調べ、報告書を書いてください。\n"
        "必ずこの形で書いてください：\n"
        "# 結論（3行）\n"
        "# 伸びているチャンネル／動画（5〜10件。チャンネル名・URL・登録者数や再生数・なぜ伸びているか）\n"
        "# 共通している型（サムネ・尺・冒頭10秒・タイトルの付け方）\n"
        "# たまごさんの『ごきげん補給所』に移せる点（3つ）\n"
        "# 調べきれなかったこと（正直に）\n"
        "URLは実在するものだけ。数字が取れないものは『不明』と書いてください。作らないでください。"
    ),
    "site": (
        "あなたは競合調査担当です。下のテーマについて、**実際に検索して**いま伸びているサイトを調べ、報告書を書いてください。\n"
        "# 結論（3行）／# 伸びているサイト（5件・URL・何が強いか・分かれば規模）／"
        "# 共通点／# たまごさんが真似できる点（3つ）／# 調べきれなかったこと"
    ),
}


def _slug(s, limit=28):
    s = re.sub(r"[\s/\\:*?\"<>|]+", "_", (s or "").strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:limit] or "muhyoudai"


def _outdir(vendor, title):
    d = os.path.join(SEIKA, "%s_%s_%s" % (time.strftime("%Y%m%d-%H%M"), vendor, _slug(title)))
    os.makedirs(d, exist_ok=True)
    return d


def _ledger(row):
    """★台帳の追記でコケても、作らせた成果物そのものを捨てない（kiku._append_line と同じ理由）。"""
    line = json.dumps(row, ensure_ascii=False) + "\n"
    for i in range(3):
        try:
            os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
            with io.open(LEDGER, "a", encoding="utf-8") as f:
                f.write(line)
            return True
        except Exception:
            time.sleep(0.3 * (i + 1))
    return False


# ---------------------------------------------------------------------------
# リサーチ系（文章の成果物）
# ---------------------------------------------------------------------------

def do_text(kind, order, vendor, n=None):
    brief = kyoyu_brief.build(max_cases=10, focus_n=n)
    msgs = [
        {"role": "system", "content": brief + "\n\n" + SHIGOTO.get(kind, SHIGOTO["research"])},
        {"role": "user", "content": "【依頼】\n" + order},
    ]
    res = gkuchi.ask(vendor, msgs, search=True, timeout=180)
    gkuchi.record(n or 0, "tanomu:%s:%s" % (kind, order[:30]), res, note="944番 頼む(tanomu.py)")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error"), "vendor": vendor,
                "label": res.get("label"), "seconds": res.get("seconds"), "costYen": 0.0}

    d = _outdir(vendor, order)
    body = res["text"] or ""
    head = ("【依頼】%s\n【種類】%s\n【相手】%s / %s\n【検索した】%s\n"
            "【かかった時間】%s秒\n【費用】%.3f円\n【作った日時】%s\n%s\n\n"
            % (order, kind, res["label"], res["model"], "はい" if res.get("searched") else "いいえ",
               res["seconds"], res["costYen"], time.strftime("%Y-%m-%d %H:%M:%S"), "-" * 60))
    md = os.path.join(d, "report.md")
    txt = os.path.join(d, "report.txt")
    with io.open(md, "w", encoding="utf-8") as f:
        f.write(body)
    with io.open(txt, "w", encoding="utf-8") as f:
        f.write(head + body + "\n")
    with io.open(os.path.join(d, "_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"kind": kind, "order": order, "n": n, "vendor": vendor,
                   "model": res["model"], "searched": res.get("searched"),
                   "seconds": res["seconds"], "costYen": res["costYen"],
                   "at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=1)
    row = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "vendor": vendor,
           "order": order[:160], "dir": d, "costYen": res["costYen"], "n": n}
    _ledger(row)
    return {"ok": True, "vendor": vendor, "label": res["label"], "model": res["model"],
            "dir": d, "files": [md, txt], "costYen": res["costYen"],
            "seconds": res["seconds"], "searched": res.get("searched"),
            "preview": body[:600]}


# ---------------------------------------------------------------------------
# 画像（Geminiに作らせて、こちらに .png で落とす）
# ---------------------------------------------------------------------------

def do_image(order, vendor="gemini", n=None):
    if vendor == "gemini":
        return _image_gemini(order, n)
    if vendor == "grok":
        return _image_grok(order, n)
    return {"ok": False, "error": "画像は gemini か grok のみ対応です（OpenAIは別料金のため未接続）",
            "vendor": vendor, "costYen": 0.0}


def _image_gemini(order, n):
    key = gkuchi.find_key("gemini")
    if not key:
        return {"ok": False, "vendor": "gemini", "label": gkuchi.LABEL["gemini"], "costYen": 0.0,
                "error": "Geminiの鍵がありません（GEMINI_API_KEY）。Google AI Studioで発行して "
                         "~/.tamago/keys/api_keys.env に追記してください。"}
    t0 = time.time()
    errs = []
    for model in GEMINI_IMAGE_MODELS:
        url = gkuchi.GEMINI_URL % (model, key)
        body = {"contents": [{"role": "user", "parts": [{"text": order}]}],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
        try:
            j = gkuchi._post_json(url, body, {"Content-Type": "application/json"}, 180)
        except Exception as e:
            errs.append("%s → %s" % (model, gkuchi._err_text(e)))
            continue
        parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        img_b64, mime, note = None, "image/png", ""
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                img_b64 = inline["data"]
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            elif p.get("text"):
                note += p["text"]
        if not img_b64:
            errs.append("%s → 画像が返りませんでした（本文のみ）" % model)
            continue
        d = _outdir("gemini", order)
        ext = ".png" if "png" in mime else (".jpg" if "jpe" in mime else ".png")
        path = os.path.join(d, "image" + ext)
        with open(path, "wb") as f:
            f.write(base64.b64decode(img_b64))
        secs = round(time.time() - t0, 1)
        # 画像1枚の単価は公式ページの値が必要。トークン課金として台帳に載せ、概算と明記する。
        usage = j.get("usageMetadata") or {}
        yen = gkuchi._cost_yen("gemini", model, usage)
        with io.open(os.path.join(d, "_meta.json"), "w", encoding="utf-8") as f:
            json.dump({"kind": "image", "order": order, "n": n, "vendor": "gemini",
                       "model": model, "seconds": secs, "costYen": yen,
                       "costNote": "画像の単価は https://ai.google.dev/gemini-api/docs/pricing を参照。ここはトークン換算の概算。",
                       "modelNote": note[:500], "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                      f, ensure_ascii=False, indent=1)
        _ledger({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "image", "vendor": "gemini",
                 "order": order[:160], "dir": d, "costYen": yen, "n": n})
        return {"ok": True, "vendor": "gemini", "label": gkuchi.LABEL["gemini"], "model": model,
                "dir": d, "files": [path], "costYen": yen, "seconds": secs, "preview": note[:300]}
    return {"ok": False, "vendor": "gemini", "label": gkuchi.LABEL["gemini"], "costYen": 0.0,
            "seconds": round(time.time() - t0, 1), "error": "画像生成に失敗： " + " ／ ".join(errs)}


def _image_grok(order, n):
    key = gkuchi.find_key("grok")
    if not key:
        return {"ok": False, "vendor": "grok", "label": gkuchi.LABEL["grok"], "costYen": 0.0,
                "error": "Grokの鍵がありません（XAI_API_KEY）"}
    t0 = time.time()
    errs = []
    for model in XAI_IMAGE_MODELS:
        try:
            j = gkuchi._post_json(XAI_IMAGE_URL,
                                  {"model": model, "prompt": order, "n": 1, "response_format": "b64_json"},
                                  {"Content-Type": "application/json",
                                   "Authorization": "Bearer %s" % key}, 180)
        except Exception as e:
            errs.append("%s → %s" % (model, gkuchi._err_text(e)))
            continue
        data = (j.get("data") or [{}])[0]
        b64 = data.get("b64_json")
        if not b64:
            errs.append("%s → 画像データが返りませんでした" % model)
            continue
        d = _outdir("grok", order)
        path = os.path.join(d, "image.png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        secs = round(time.time() - t0, 1)
        yen = round(0.07 * gkuchi.gk.USD_TO_YEN, 3)  # xAI画像は1枚$0.07（公式: docs.x.ai/developers/pricing）
        _ledger({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "image", "vendor": "grok",
                 "order": order[:160], "dir": d, "costYen": yen, "n": n})
        with io.open(os.path.join(d, "_meta.json"), "w", encoding="utf-8") as f:
            json.dump({"kind": "image", "order": order, "vendor": "grok", "model": model,
                       "seconds": secs, "costYen": yen,
                       "costNote": "xAI画像は1枚$0.07（https://docs.x.ai/developers/pricing）",
                       "revisedPrompt": data.get("revised_prompt", "")[:400]},
                      f, ensure_ascii=False, indent=1)
        return {"ok": True, "vendor": "grok", "label": gkuchi.LABEL["grok"], "model": model,
                "dir": d, "files": [path], "costYen": yen, "seconds": secs,
                "preview": (data.get("revised_prompt") or "")[:300]}
    return {"ok": False, "vendor": "grok", "label": gkuchi.LABEL["grok"], "costYen": 0.0,
            "seconds": round(time.time() - t0, 1), "error": "画像生成に失敗： " + " ／ ".join(errs)}


# ---------------------------------------------------------------------------
# 工場側の本体（gaibu_runner.py から呼ばれる）
# ---------------------------------------------------------------------------

def run_job(payload):
    kind = payload.get("kind") or "research"
    order = payload["order"]
    vendor = payload.get("vendor") or "gemini"
    n = payload.get("n")
    ok, why = gkuchi.cost_cap_ok()
    if not ok:
        return {"ok": False, "error": "コスト上限：" + why}
    # ★1034番【予算の栓】画像は1枚が高い（xAI画像 1枚 約$0.07＝約11円／fal動画は1本30円）。
    #   叩く前に必ず通す。止めたら理由をそのまま返す（黙って空で帰らない）。
    try:
        import yosan
        _saifu = {"grok": "xai", "openai": "openai", "gemini": "gemini", "fal": "fal"}.get(vendor)
        if _saifu:
            _mitsu = 11.0 if kind == "image" else 3.0   # 多めに見る側。実額はあとで記録する
            _ok, _why = yosan.mitsumori(_saifu, _mitsu, "tanomu %s（%s）" % (kind, vendor))
            if not _ok:
                return {"ok": False, "error": _why, "stoppedByYosan": True, "totalYen": 0.0}
    except Exception as e:
        return {"ok": False, "totalYen": 0.0,
                "error": "予算の栓（tools/yosan.py）が読めませんでした: %s。お金の話なので止めます。" % e}
    if kind == "image":
        r = do_image(order, vendor, n)
    else:
        r = do_text(kind, order, vendor, n)
    # ★1034番【予算の栓】叩いた後に実額を記録する。
    try:
        import yosan
        _saifu = {"grok": "xai", "openai": "openai", "gemini": "gemini", "fal": "fal"}.get(vendor)
        if _saifu:
            yosan.tsukatta(_saifu, float(r.get("costYen") or 0.0),
                           "tanomu %s（%s）" % (kind, vendor), src="tanomu.run_job の costYen")
    except Exception:
        pass
    return {"ok": bool(r.get("ok")), "result": r, "kind": kind, "order": order,
            "totalYen": r.get("costYen") or 0.0, "error": r.get("error")}


def render(out):
    r = (out or {}).get("result") or {}
    L = []
    A = L.append
    A("=" * 68)
    A("【頼んだこと】%s" % out.get("order"))
    A("【種類】%s" % out.get("kind"))
    A("=" * 68)
    if not out.get("ok"):
        A("✗ %s" % (out.get("error") or r.get("error")))
        return "\n".join(L)
    A("相手：%s / %s" % (r.get("label"), r.get("model")))
    A("検索した：%s" % ("はい" if r.get("searched") else "―"))
    A("所要：%s秒 / %.3f円" % (r.get("seconds"), r.get("costYen") or 0))
    A("")
    A("★成果物はここに落ちました（向こうの画面に見に行かなくていい）：")
    A("　%s" % r.get("dir"))
    for f in r.get("files") or []:
        A("　　%s" % os.path.basename(f))
    if r.get("preview"):
        A("")
        A("──中身の頭だけ──")
        for line in (r["preview"] or "").splitlines()[:18]:
            A("　" + line)
    return "\n".join(L)


def cmd_list():
    if not os.path.isdir(SEIKA):
        print("まだ成果物はありません。")
        return 0
    rows = sorted([d for d in os.listdir(SEIKA) if not d.startswith("_")], reverse=True)
    if not rows:
        print("まだ成果物はありません。")
        return 0
    print("外部AIに作らせたもの（新しい順）：")
    for d in rows[:40]:
        p = os.path.join(SEIKA, d)
        meta = {}
        try:
            meta = json.load(io.open(os.path.join(p, "_meta.json"), encoding="utf-8"))
        except Exception:
            pass
        print("  %s  %s  %.3f円" % (d, meta.get("kind") or "?", meta.get("costYen") or 0))
        print("      %s" % (meta.get("order") or "")[:90])
    return 0


def cmd_inbox():
    """★逆向き：たまごさんが向こうの画面で作ったものを拾う。
    status/gaibu_seika/_inbox/ に置いてあるものを、日付つきのフォルダへ取り込んで台帳に載せる。"""
    os.makedirs(INBOX, exist_ok=True)
    files = [f for f in os.listdir(INBOX) if not f.startswith(".")]
    if not files:
        print("_inbox は空です。")
        print("★向こうの画面（Gemini/Grok/ChatGPT）で作ったものは、ここに入れてください：")
        print("   %s" % INBOX)
        return 0
    d = _outdir("inbox", "たまごさんが向こうで作ったもの")
    moved = []
    for f in files:
        src = os.path.join(INBOX, f)
        dst = os.path.join(d, f)
        try:
            shutil.move(src, dst)
            moved.append(dst)
        except Exception as e:
            print("  ✗ %s: %s" % (f, e))
    with io.open(os.path.join(d, "_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"kind": "inbox", "order": "たまごさんが外部AIの画面で作ったものを取り込み",
                   "vendor": "inbox", "costYen": 0.0, "files": [os.path.basename(x) for x in moved],
                   "at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=1)
    _ledger({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "inbox", "vendor": "inbox",
             "order": "外部画面からの取り込み", "dir": d, "costYen": 0.0})
    print("取り込みました（%d件）：%s" % (len(moved), d))
    for m in moved:
        print("  " + os.path.basename(m))
    return 0


def main():
    ap = argparse.ArgumentParser(description="外部AIに仕事を頼んで、成果物をこちらに落とす")
    ap.add_argument("kind", nargs="?", choices=list(SHIGOTO.keys()) + ["image"], default=None)
    ap.add_argument("order", nargs="?", default=None)
    ap.add_argument("--ai", dest="vendor", default="gemini", choices=["gemini", "grok", "openai"])
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--wait", type=int, default=420)
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--inbox", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.list:
        return cmd_list()
    if a.inbox:
        return cmd_inbox()
    if not a.kind or not a.order:
        ap.print_help()
        return 2

    payload = {"kind": a.kind, "order": a.order, "vendor": a.vendor, "n": a.n}
    if a.local or gkuchi.net_ok():
        out = run_job(payload)
    else:
        jid = gkuchi.enqueue_job("tanomu", payload)
        print("この環境からは外部AIに回線が出ないので、工場（Mac側）に代行を頼みました。")
        print("  job: %s / 最大%d秒待ちます…" % (jid, a.wait))
        sys.stdout.flush()
        out = gkuchi.wait_job(jid, wait_sec=a.wait)
        if out is None:
            print("⚠️ 時間内に結果が返りませんでした： status/gaibu_jobs/done/%s.json" % jid)
            return 1

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(render(out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
