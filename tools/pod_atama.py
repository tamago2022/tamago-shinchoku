#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# kakeibo: 文字起こしは Gemini 無料枠のみ（1回1行・0円）。案件「ソロプレナー神回 日本語版」
"""日本語音源の「頭の英語」を切り落として、日本語の本題から始まる版を作る（2026-10-15）。

たまごさん：「冒頭の英語を削って、いきなり日本語の本題から始める版に差し替え」
やり方：
  1) 頭の90秒を、無音（0.25秒以上）で区切って小さな塊にする
  2) 塊ごとに Gemini（無料枠）で書き起こし、日本語が始まる最初の塊を探す
  3) その塊の直前の無音で切り、0.3秒の間を置いて m4a(AAC 64kbps) に戻す
  4) claude_nouhin.py put で納品（ファイル名の頭に日付・ドライブの同じ案件フォルダ）
使い方（Mac）：
  python3 tools/pod_atama.py --src <m4a> [--dry]     # --dry は切る位置を出すだけ
"""
import argparse, base64, io, json, os, re, shutil, subprocess, sys, time, unicodedata, urllib.error, urllib.request, wave, audioop

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kagi, kakeibo, yosan

ANKEN = "ソロプレナー神回 日本語版"
STT = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-transcribe"]
PROMPT = ("この音声を、聞こえたとおりに書き起こしてください。英語は英語のまま、日本語は日本語のまま。"
          "話し声が無ければ「（無音）」。出力は書き起こしの本文だけ。")
WORK = "/Volumes/iMac HDD/Mac標準置き場/AI作業/pod_atama"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def to_wav(src, dst):
    subprocess.run(["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@24000", "-c", "1", src, dst], check=True)


def silences(fr, rate, min_sec=0.25, thr=300):
    """(開始秒, 終わり秒) の無音区間"""
    step = int(rate * 0.02)
    out, start = [], None
    for i in range(0, len(fr) // 2, step):
        rms = audioop.rms(fr[i * 2:(i + step) * 2], 2)
        t = i / rate
        if rms < thr:
            start = t if start is None else start
        else:
            if start is not None and t - start >= min_sec:
                out.append((start, t))
            start = None
    return out


def stt(key, pcm, rate):
    b = io.BytesIO()
    fr, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(fr)
    body = {"contents": [{"parts": [{"text": PROMPT}, {"inlineData": {"mimeType": "audio/wav",
            "data": base64.b64encode(b.getvalue()).decode()}}]}], "generationConfig": {"temperature": 0}}
    for m in STT:
        ok, why = yosan.mitsumori("gemini", 0, "文字起こし %s 頭の確認" % m, anken=ANKEN)
        if not ok:
            raise SystemExit("予算の栓: %s" % why)
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (m, key)
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(
                url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=120))
            t = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]).strip()
            kakeibo.kiroku(ANKEN, "gemini", model=m, ryou="文字起こし（頭の確認）", yen=0, kakutei="推定",
                           moto="Gemini API 無料枠")
            return t
        except urllib.error.HTTPError as e:
            log("STT", m, e.code, e.read().decode("utf-8", "replace")[:150].replace("\n", " "))
        except Exception as e:
            log("STT", m, repr(e)[:150])
    return None


def has_ja(t):
    return bool(re.search(r"[぀-ヿ一-鿿]", t or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--name", default=None, help="納品するファイル名（日付は自動）")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    wav = os.path.join(WORK, "src.wav")
    to_wav(a.src, wav)
    # afconvert の WAVE は「拡張形式(65534)」で wave モジュールが読めないので、data の塊を直接読む
    raw = open(wav, "rb").read()
    i = raw.find(b"data", 12)
    n = int.from_bytes(raw[i + 4:i + 8], "little")
    rate = 24000
    pcm = raw[i + 8:i + 8 + n]
    pcm = pcm[: len(pcm) // 2 * 2]
    head = pcm[: rate * 2 * 90]
    sil = silences(head, rate)
    # 塊＝無音と無音のあいだ
    bounds, prev = [], 0.0
    for s, e in sil:
        if s - prev > 0.3:
            bounds.append((prev, s))
        prev = e
    log("頭90秒の塊:", ["%.1f-%.1f" % b for b in bounds[:15]])
    key = kagi.need("GEMINI_API_KEY")
    cut = None
    for s, e in bounds[:12]:
        t = stt(key, pcm[int(s * rate) * 2:int(e * rate) * 2], rate)
        log("塊 %.1f-%.1f秒: %s" % (s, e, (t or "")[:120].replace("\n", " ")))
        if t and has_ja(t):
            cut = s; break
        time.sleep(4)
    if cut is None:
        log("日本語の始まりが見つからない→切らない"); print("RESULT", json.dumps({"ok": False})); return 1
    log("切る位置: %.2f秒（ここから日本語）" % cut)
    if a.dry:
        print("RESULT", json.dumps({"ok": True, "cut": cut, "dry": True})); return 0
    start = max(0, int((cut - 0.05) * rate)) * 2
    out_wav = os.path.join(WORK, "out.wav")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * 0.3) + pcm[start:])
    name = a.name or os.path.basename(a.src)
    name = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", name)
    name = time.strftime("%Y-%m-%d_") + re.sub(r"\.m4a$", "", name) + ".m4a"
    out_m4a = os.path.join(WORK, name)
    subprocess.run(["/usr/bin/afconvert", "-f", "m4af", "-d", "aac", "-c", "1", "-b", "64000", out_wav, out_m4a], check=True)
    with wave.open(out_wav) as r:
        sec = r.getnframes() / rate
    import claude_nouhin
    res = claude_nouhin.put(out_m4a, anken="ポッドキャスト神回_日本語音源", move=True)
    for p in (wav, out_wav):
        try: os.remove(p)
        except OSError: pass
    print("RESULT", json.dumps({"ok": res.get("ok"), "cut": round(cut, 2), "sec": round(sec, 1), "put": res}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
