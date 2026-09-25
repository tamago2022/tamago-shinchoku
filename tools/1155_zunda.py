#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1155番【円卓会議 → ずんだもん読み上げ】

なぜ要るか:
  #円卓会議 のノートを、Obsidianの中でそのまま再生できる形にする。
  VOICEVOX(ローカル)なので0円。

動き方:
  1. VOICEVOXエンジン(50021)が死んでいたら起こして待つ
  2. Vaultから #円卓会議 のノートを全部拾う（完成→円卓会議→その他 の順）
  3. 1ノートずつ：本文を掃除 → 文で分割 → 合成 → 1本に結合 → mp3(無ければm4a)
  4. Vaultの 音声/ に置き、ノートのタグ行の下に ![[...]] を追記
  5. 1ノート終わるごとに status/zunda/progress.json を更新。
     落ちても次に走ったとき done のノートは飛ばして続きから。

使い方:
  python3 tools/1155_zunda.py            # 全部
  python3 tools/1155_zunda.py --limit 1  # 1本だけ（鳴るか確認用）
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import wave

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
VAULT = os.path.join(HOME, "Library", "Mobile Documents",
                     "iCloud~md~obsidian", "Documents", "tamago_brain")
AUDIO_DIR = os.path.join(VAULT, "AI出力", "40_プロジェクト", "円卓会議🔥", "音声")
STATE_DIR = os.path.join(REPO, "status", "zunda")
PROGRESS = os.path.join(STATE_DIR, "progress.json")
LOG = os.path.join(STATE_DIR, "worker.log")
ENGINE = "http://127.0.0.1:50021"
SPEAKER = 3          # ずんだもん ノーマル
CHUNK = 140          # 1リクエストの文字数上限
TAG = "#円卓会議"


def log(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------- エンジン ----------

def engine_alive():
    try:
        urllib.request.urlopen(ENGINE + "/version", timeout=3).read()
        return True
    except Exception:
        return False


def engine_boot():
    if engine_alive():
        return True
    run = "/Applications/VOICEVOX.app/Contents/MacOS/vv-engine/run"
    if not os.path.exists(run):
        log("VOICEVOXのエンジンが見つからない: %s" % run)
        return False
    log("エンジンを起こす")
    subprocess.Popen([sys.executable, os.path.join(REPO, "tools", "1144_hanareru.py"),
                      "/tmp/vv_engine.log", run, "--host", "127.0.0.1", "--port", "50021"])
    for _ in range(90):
        time.sleep(2)
        if engine_alive():
            log("エンジン起動OK")
            return True
    log("エンジンが3分で上がらなかった")
    return False


def synth(text):
    """1チャンクを合成して wav バイト列を返す"""
    q = urllib.parse.quote(text)
    req = urllib.request.Request(
        "%s/audio_query?text=%s&speaker=%d" % (ENGINE, q, SPEAKER), method="POST")
    query = urllib.request.urlopen(req, timeout=60).read()
    req2 = urllib.request.Request(
        "%s/synthesis?speaker=%d" % (ENGINE, SPEAKER), data=query,
        headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req2, timeout=180).read()


# ---------- 本文の掃除 ----------

def clean(md):
    t = md
    t = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)        # frontmatter
    t = re.sub(r"```.*?```", "", t, flags=re.S)               # コードブロック
    t = re.sub(r"!?\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", t)   # wikiリンク
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)          # mdリンク
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^\s*\|.*\|\s*$", lambda m: m.group(0).replace("|", "、"),
               t, flags=re.M)                                  # 表は読点で繋ぐ
    t = re.sub(r"^\s*[-=|:\s]{3,}$", "", t, flags=re.M)       # 罫線
    t = re.sub(r"[*_`>#]+", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def chunks(text):
    out, buf = [], ""
    parts = re.split(r"(?<=[。！？\n])", text)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) > CHUNK:
            if buf:
                out.append(buf)
            buf = p
        else:
            buf += p
    if buf:
        out.append(buf)
    return [c for c in out if re.search(r"[ぁ-んァ-ヶ一-龠a-zA-Z0-9]", c)]


# ---------- 書き出し ----------

def join_wavs(wavs, dest):
    params = None
    with wave.open(dest, "wb") as out:
        for w in wavs:
            with wave.open(io.BytesIO(w), "rb") as r:
                if params is None:
                    params = r.getparams()
                    out.setparams(params)
                out.writeframes(r.readframes(r.getnframes()))


def encoder():
    for c in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if os.path.exists(c):
            return ("ffmpeg", c)
    try:
        import lameenc  # noqa
        return ("lameenc", None)
    except Exception:
        pass
    return ("afconvert", "/usr/bin/afconvert")


ENC = encoder()


def to_compressed(wav_path, stem):
    kind, binpath = ENC
    if kind == "ffmpeg":
        dest = stem + ".mp3"
        subprocess.run([binpath, "-y", "-loglevel", "error", "-i", wav_path,
                        "-codec:a", "libmp3lame", "-b:a", "96k", dest], check=True)
        return dest
    if kind == "lameenc":
        import lameenc
        dest = stem + ".mp3"
        with wave.open(wav_path, "rb") as r:
            ch, sw, sr, n = r.getnchannels(), r.getsampwidth(), r.getframerate(), r.getnframes()
            pcm = r.readframes(n)
        e = lameenc.Encoder()
        e.set_bit_rate(96)
        e.set_in_sample_rate(sr)
        e.set_channels(ch)
        e.set_quality(5)
        data = e.encode(pcm) + e.flush()
        with open(dest, "wb") as f:
            f.write(data)
        return dest
    dest = stem + ".m4a"
    subprocess.run([binpath, "-f", "m4af", "-d", "aac", "-b", "96000",
                    wav_path, dest], check=True)
    return dest


def slug(rel):
    s = os.path.basename(rel)[:-3]
    s = re.sub(r"[\\/:*?\"<>|#\[\]]", "", s)
    return s[:60].strip()


def embed(note_path, fname):
    with io.open(note_path, "r", encoding="utf-8") as f:
        body = f.read()
    mark = "![[%s]]" % fname
    if mark in body:
        return False
    lines = body.split("\n")
    idx = None
    for i, ln in enumerate(lines):
        if TAG in ln:
            idx = i
            break
    block = ["", "🔊 ずんだもんの読み上げ", mark, ""]
    if idx is None:
        lines = block + lines
    else:
        lines[idx + 1:idx + 1] = block
    with io.open(note_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return True


# ---------- 進捗 ----------

def load_progress():
    try:
        with io.open(PROGRESS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"done": {}, "failed": {}, "started": time.strftime("%Y-%m-%d %H:%M")}


def save_progress(p):
    os.makedirs(STATE_DIR, exist_ok=True)
    p["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = PROGRESS + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PROGRESS)


def collect():
    hits = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for n in files:
            if not n.endswith(".md"):
                continue
            p = os.path.join(root, n)
            try:
                with io.open(p, "r", encoding="utf-8", errors="ignore") as f:
                    if TAG in f.read():
                        hits.append(os.path.relpath(p, VAULT))
            except Exception:
                pass

    def rank(r):
        if r.startswith("円卓会議/完成/"):
            return 0
        if r.startswith("円卓会議/"):
            return 1
        if "円卓会議🔥" in r:
            return 2
        if r.startswith("00 inbox/"):
            return 4
        return 3
    return sorted(hits, key=lambda r: (rank(r), r))


def do_note(rel, prog):
    src = os.path.join(VAULT, rel)
    with io.open(src, "r", encoding="utf-8", errors="ignore") as f:
        text = clean(f.read())
    cs = chunks(text)
    if not cs:
        prog["failed"][rel] = "読む文が無い"
        return None
    st = slug(rel)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    stem = os.path.join(AUDIO_DIR, "円卓音声_" + st)
    wavpath = "/tmp/zunda_%d.wav" % os.getpid()
    log("  %d チャンク / %d 文字" % (len(cs), len(text)))
    wavs = []
    for i, c in enumerate(cs):
        for attempt in range(3):
            try:
                wavs.append(synth(c))
                break
            except Exception as e:
                if attempt == 2:
                    raise
                log("  再試行 %d/%d: %s" % (i, len(cs), e))
                time.sleep(3)
        if (i + 1) % 25 == 0:
            log("  %d/%d" % (i + 1, len(cs)))
    join_wavs(wavs, wavpath)
    out = to_compressed(wavpath, stem)
    os.remove(wavpath)
    fname = os.path.basename(out)
    added = embed(src, fname)
    prog["done"][rel] = {"file": fname,
                         "bytes": os.path.getsize(out),
                         "chunks": len(cs),
                         "embed": bool(added)}
    prog["failed"].pop(rel, None)
    return out


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    log("=== 1155 開始 encoder=%s limit=%s ===" % (ENC[0], limit))
    if not engine_boot():
        return 1
    prog = load_progress()
    notes = collect()
    prog["total"] = len(notes)
    save_progress(prog)
    log("対象 %d 本 / 済 %d 本" % (len(notes), len(prog["done"])))
    n = 0
    for rel in notes:
        if rel in prog["done"]:
            continue
        if limit is not None and n >= limit:
            break
        n += 1
        log("[%d] %s" % (n, rel))
        t0 = time.time()
        try:
            out = do_note(rel, prog)
            if out:
                log("  → %s (%.1fMB, %.0f秒)" %
                    (os.path.basename(out), os.path.getsize(out) / 1e6, time.time() - t0))
        except Exception as e:
            prog["failed"][rel] = str(e)[:200]
            log("  失敗: %s" % e)
        save_progress(prog)
    log("=== 終わり 済%d 失敗%d ===" % (len(prog["done"]), len(prog["failed"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
