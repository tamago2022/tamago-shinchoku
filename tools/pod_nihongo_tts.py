#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# kakeibo: Gemini TTS 無料枠のみ（1回1行・0円）。案件「ソロプレナー神回 日本語版」
"""海外ポッドキャストの日本語要約原稿 → Gemini TTS（Aoede）→ たまごさん個人用のGoogleドライブへ（2026-10-14）

円卓会議の朗読（status/roudoku_enraku/tts.py・tts_loop.py）と同じ作り方：
  ・Aoede／落ち着いた女性ナレーター指示／約900字ずつ区切る（長く読ませるほど英語化・途切れが出るため）
  ・途中切れ（finishReason≠STOP か、長さが期待の8割未満）はその区切りを半分ずつ作り直す
  ・無料枠（1モデル1日10回）が切れたら次のモデルへ。全部切れたら、できた所まで残して止める（翌日つづきから）
置き場：
  ・作業ファイル … 外付けHDD（無ければ ~/.tamago_work）。終わったら消す
  ・できた音源 … ~/Library/CloudStorage/GoogleDrive-*/マイドライブ/朗読/ソロプレナー神回/（非公開＝たまごさんだけ）
  ・公開リポジトリ・サイトには音声を置かない
使い方（Mac）：
  python3 tools/pod_nihongo_tts.py --text 原稿.txt --name 題名 --src 元URL --guest 出演者 --show 番組名 --out 結果.json
"""
import sys as _sk_sys, os as _sk_os; _sk_sys.path.insert(0, _sk_os.path.dirname(_sk_os.path.abspath(__file__))); import saifu_kanmon as _sk; _sk.mon(__name__)  # ★2026-10-15 財布の関所：停止札があれば何も叩かず終わる
import argparse, base64, glob, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.request, wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kagi, kakeibo, yosan

ANKEN = "ソロプレナー神回 日本語版"
VOICE = "Aoede"
MODELS = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
STYLE = ("Read only the TRANSCRIPT section aloud, in natural Japanese.\n"
         "### DIRECTOR'S NOTES\n"
         "Style: a calm, warm, easy-to-listen-to female podcast narrator. Neutral, even delivery like an Audible narration. "
         "No dramatic or theatrical intonation.\n"
         "Pace: steady and unhurried, consistent throughout.\n"
         "Rules: read the transcript word for word in Japanese, from the first sentence to the last. "
         "Never switch to English, never add, skip, or invent any sentence. Stop right after the last sentence.\n"
         "#### TRANSCRIPT\n")
HDD = "/Volumes/iMac HDD/Mac標準置き場/AI作業"
MIN_FREE_GB = 30


def log(*a):
    print(time.strftime("%m-%d %H:%M:%S"), *a, flush=True)


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return st.f_bavail * st.f_frsize / 1e9


def chunks_of(text, size=900):
    sents = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if para[-1] not in "。？！」』?!":
            para += "。"
        parts = re.findall(r"[^。？！?!]+[。？！?!」』]*", para) or [para]
        for i, p in enumerate(parts):
            sents.append(p + ("\n" if i == len(parts) - 1 else ""))
    out, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > size and cur:
            out.append(cur.strip()); cur = ""
        cur += s
    if cur.strip():
        out.append(cur.strip())
    return out


BLOCK = {}


def tts_one(key, model, text, dest):
    ok, why = yosan.mitsumori("gemini", 0, "TTS %s %s %d字" % (model, VOICE, len(text)), anken=ANKEN)
    if not ok:
        raise SystemExit("予算の栓で停止: %s" % why)
    body = {"contents": [{"parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
    for attempt in range(6):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=900))
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            log("HTTP", e.code, model, msg[:300].replace("\n", " "))
            if e.code == 429 and ("PerDay" in msg or "free_tier_requests" in msg):
                return "DAY"
            if e.code in (400, 404):
                return "FAIL"
            m = re.search(r'"retryDelay":\s*"(\d+)', msg)
            time.sleep(int(m.group(1)) + 5 if m else 40)
        except Exception as e:
            log("ERR", repr(e)); time.sleep(30)
    else:
        return "FAIL"
    cand = d["candidates"][0]
    fr = cand.get("finishReason")
    pcm = b"".join(base64.b64decode(p["inlineData"]["data"]) for p in cand["content"]["parts"] if "inlineData" in p)
    with wave.open(dest, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    sec = len(pcm) / 48000.0
    u = d.get("usageMetadata", {})
    kakeibo.kiroku(ANKEN, "gemini", model=model,
                   ryou="入力%s/出力%sトークン・音声%.0f秒" % (u.get("promptTokenCount"), u.get("candidatesTokenCount"), sec),
                   yen=0, kakutei="推定", moto="Gemini API 無料枠（%s %s）" % (VOICE, os.path.basename(dest)))
    json.dump({"sec": sec, "finish": fr, "chars": len(text), "model": model}, open(dest + ".json", "w"))
    log("OK", os.path.basename(dest), model, "%.0f秒" % sec, "%d字" % len(text), fr)
    return "OK"


def gen(key, text, dest):
    for m in MODELS:
        if BLOCK.get(m, 0) > time.time():
            continue
        r = tts_one(key, m, text, dest)
        if r == "OK":
            meta = json.load(open(dest + ".json"))
            expect = len(text) / 274.0 * 60
            # 2026-10-14実測：lite は1分約340〜370字で読む（円卓の274字/分より速い）→ 0.8 だと完走でも落ちる。0.6 にする
            if meta["finish"] == "STOP" and meta["sec"] >= expect * 0.6:
                return True
            log("途中切れの疑い", meta, "期待%.0f秒" % expect)
            os.remove(dest)
            return "SHORT"
        BLOCK[m] = time.time() + (86400 if r == "DAY" else 900)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--src", required=True); ap.add_argument("--guest", required=True)
    ap.add_argument("--show", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"name": a.name, "src": a.src, "guest": a.guest, "show": a.show, "voice": "Aoede（Gemini TTS 無料枠）", "yen": 0}

    def done(**kw):
        res.update(kw); res["at"] = time.strftime("%F %T")
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log("RESULT", json.dumps(res, ensure_ascii=False))

    if free_gb() < MIN_FREE_GB:
        return done(status="stop_disk", free_gb=round(free_gb(), 1))
    base = HDD if os.path.isdir(HDD) else os.path.expanduser("~/.tamago_work")
    work = os.path.join(base, "pod_tts_" + re.sub(r"\W+", "_", a.name)[:40])
    os.makedirs(work, exist_ok=True)
    res["work"] = work
    key = kagi.need("GEMINI_API_KEY")
    text = open(a.text, encoding="utf-8").read()
    parts = chunks_of(text)
    res["chunks"] = len(parts)
    wavs = []
    for i, c in enumerate(parts):
        dest = os.path.join(work, "c%02d.wav" % i)
        if os.path.exists(dest):
            wavs.append(dest); continue
        ha, hb = dest[:-4] + "a.wav", dest[:-4] + "b.wav"
        if os.path.exists(ha) and os.path.exists(hb):  # 前回、半分ずつ作り直し済み
            wavs += [ha, hb]; continue
        r = "SHORT" if os.path.exists(ha) else None  # 前回、前半だけできて止まった→後半から
        if r is None:
            r = gen(key, c, dest)
        if r == "SHORT":
            sents = re.findall(r"[^。？！]+[。？！」』]*", c)
            h = max(1, len(sents) // 2)
            for suf, sub in (("a", "".join(sents[:h])), ("b", "".join(sents[h:]))):
                d2 = os.path.join(work, "c%02d%s.wav" % (i, suf))
                if not os.path.exists(d2):
                    time.sleep(20)
                    r2 = gen(key, sub, d2)
                    if r2 is False:
                        return done(status="quota_or_fail", made=len(wavs), at_chunk=i)
                    if r2 == "SHORT":  # 半分でも短い＝2回目も短ければ、短いまま採用はせず止める
                        return done(status="short_twice", made=len(wavs), at_chunk=i)
                wavs.append(d2)
        elif r is True:
            wavs.append(dest)
        else:
            return done(status="quota_or_fail", made=len(wavs), at_chunk=i)
        time.sleep(20)
    # つなぐ（区切りの間に0.6秒の間）
    full = os.path.join(work, "full.wav")
    gap = b"\x00\x00" * int(24000 * 0.6)
    with wave.open(full, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        for p in wavs:
            with wave.open(p) as r:
                w.writeframes(r.readframes(r.getnframes()))
            w.writeframes(gap)
    with wave.open(full) as r:
        minutes = r.getnframes() / 24000 / 60
    m4a_tmp = os.path.join(work, "out.m4a")
    subprocess.run(["/usr/bin/afconvert", "-f", "m4af", "-d", "aac", "-c", "1", "-b", "64000", full, m4a_tmp], check=True)
    # 2026-10-14実測：「GoogleDrive-<メール> (2026-10-13 14:58)」という同期していない古い控えが並んでいて、
    #   sorted()[0] がそちらを選び、ドライブのIDが付かなかった。名前に空白・括弧が無い本物だけを使う。
    roots = sorted(p for p in glob.glob(os.path.expanduser("~/Library/CloudStorage/GoogleDrive-*/マイドライブ"))
                   if " " not in os.path.basename(os.path.dirname(p)))
    if not roots:
        return done(status="no_drive", minutes=round(minutes, 1))
    dest_dir = os.path.join(roots[0], "朗読", "ソロプレナー神回")
    os.makedirs(dest_dir, exist_ok=True)
    fname = "%s.m4a" % a.name
    final = os.path.join(dest_dir, fname)
    shutil.copy(m4a_tmp, final)
    with open(os.path.join(dest_dir, "%s_出典.txt" % a.name), "w", encoding="utf-8") as f:
        f.write("番組：%s\n出演者：%s\n元エピソード：%s\n日本語要約・朗読：Aoede（Gemini TTS）／%s\n" % (a.show, a.guest, a.src, time.strftime("%F")))
    shutil.copy(a.text, os.path.join(dest_dir, "%s_原稿.txt" % a.name))
    fid = None
    for _ in range(40):
        p = subprocess.run(["/usr/bin/xattr", "-p", "com.google.drivefs.item-id#S", final], capture_output=True)
        v = p.stdout.decode("utf-8", "replace").strip()
        if p.returncode == 0 and v and not v.startswith("local"):
            fid = v; break
        time.sleep(15)
    url = "https://drive.google.com/file/d/%s/view" % fid if fid else None
    shutil.rmtree(work, ignore_errors=True)  # 作業ファイルは消す
    done(status="ok" if fid else "uploaded_no_id_yet", minutes=round(minutes, 1), bytes=os.path.getsize(final),
         drive_path=final, url=url, work_removed=not os.path.exists(work))


if __name__ == "__main__":
    main()
