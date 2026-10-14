#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""制作依頼の素材（音源など）を工場が自分で拾いに行く（2026-10-14・地球観察日記 第2作／Issue #975）

なぜ要るか（実測 2026-10-14）：
  Issue #975 には「`Montage de Voyage.mp3` は ChatGPT 会話添付のみで受領」と書かれていて、
  Claude には届いていなかった。実物はたまごさんが Suno/ChatGPT から落とした ~/Desktop にあった（17:39）。
  「どこにあるか」を人が伝える＝水くみ。だから工場が Issue を読んで、自分で探して、受け取ったと Issue に書く。

流れ（たまごさんの手は「ChatGPT/Suno の画面でダウンロードを1回押す」だけ）：
  ① ChatGPT が制作依頼 Issue（題名が【制作依頼】で始まる）の本文に素材のファイル名を `バッククォート` で書く。
     GitHub の Release 資産／Issue 添付（github.com/user-attachments/…）のURLを書いてもよい。
  ② この見張りが5分おきに、開いている【制作依頼】Issue を読み、
       ファイル名 → ~/Downloads・~/Desktop・ドライブ「AI生成物/受け取り」から同じ名前を探す
       URL     → そのまま取ってくる（トークン付き・読むだけ）
  ③ 見つけたら iMac HDD「Mac標準置き場/作業中/issue<番号>/」へ写し（元は消さない）、
     sha256・長さを status/public/sozai_hiroi.json に残し、Issue に「受け取りました」を1回だけ書く。

使い方（Mac）：
  python3 tools/sozai_hiroi.py            # 1回見回る（心臓から5分おき）
  python3 tools/sozai_hiroi.py --self-test
守ること：元ファイルは消さない／空き20GB未満なら写さない／ブラウザ・許可ポップアップを使わない。
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, time, unicodedata, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GH_REPO = "tamago2022/joy-relief-station"
HOME = os.path.expanduser("~")
HDD = "/Volumes/iMac HDD/Mac標準置き場/作業中"
OUT = os.path.join(REPO, "status", "public", "sozai_hiroi.json")
EXT = ("mp3", "wav", "m4a", "aac", "flac", "ogg", "zip", "mp4", "mov", "png", "jpg", "txt", "md")
MIN_FREE_GB = 20
FF = [p for p in ("/Users/mac/.local/bin/ffprobe", "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe") if os.path.exists(p)]


def n(s):
    return unicodedata.normalize("NFC", s).strip().lower()


def wanted(body):
    """本文から素材の名前とURLを抜く。"""
    body = body or ""
    names = []
    for m in re.findall(r"`([^`\n]{1,120})`", body):
        m = m.strip()
        if re.search(r"\.(%s)$" % "|".join(EXT), m, re.I) and "/" not in m:
            names.append(m)
    urls = re.findall(r"(https://(?:github\.com/user-attachments/(?:assets|files)/[\w./%-]+|"
                      r"github\.com/[\w.-]+/[\w.-]+/releases/download/[^\s)\]>\"'`]+))", body)
    return sorted(set(names)), sorted(set(urls))


def search_dirs():
    ds = [os.path.join(HOME, "Downloads"), os.path.join(HOME, "Desktop")]
    ds += glob.glob(os.path.join(HOME, "Library/CloudStorage/GoogleDrive-*/マイドライブ/AI生成物/受け取り"))
    return ds


def find_local(name):
    want = n(name)
    for d in search_dirs():
        try:
            for f in os.listdir(d):
                if n(f) == want and os.path.isfile(os.path.join(d, f)):
                    return os.path.join(d, f)
        except Exception:
            continue  # ドライブが Resource deadlock avoided の間は飛ばす
    return None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dur(p):
    if not FF:  # ffprobe が無いMac（実測）→ ffmpeg -i の Duration を読む
        try:
            r = subprocess.run(["/Users/mac/.local/bin/ffmpeg", "-hide_banner", "-i", p],
                               capture_output=True, text=True, timeout=30)
            m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
            return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2) if m else None
        except Exception:
            return None
    try:
        r = subprocess.run([FF[0], "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                           capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 2)
    except Exception:
        return None


def free_gb(p):
    st = os.statvfs(p)
    return st.f_bavail * st.f_frsize / 1e9


def api(url, tok, data=None):
    h = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}
    if data is not None:
        data = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read() or b"null")


def fetch_url(url, tok, dest):
    r = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(r, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def run():
    sys.path.insert(0, HERE)
    from github_watch import gh_token
    tok = gh_token()
    st = {}
    if os.path.exists(OUT):
        try:
            st = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            st = {}
    st.setdefault("issues", {})
    st["checked_at"] = time.strftime("%F %T")
    if not os.path.isdir(os.path.dirname(HDD)):
        st["note"] = "iMac HDD が見えない"
        return save(st)
    if free_gb(os.path.dirname(HDD)) < MIN_FREE_GB:
        st["note"] = "空きが%dGB未満なので写さない" % MIN_FREE_GB
        return save(st)
    issues = api("https://api.github.com/repos/%s/issues?state=open&per_page=50" % GH_REPO, tok) or []
    for it in issues:
        if "pull_request" in it or not (it.get("title") or "").startswith("【制作依頼】"):
            continue
        num = str(it["number"])
        rec = st["issues"].setdefault(num, {"title": it["title"], "files": {}})
        names, urls = wanted(it.get("body"))
        # コメントに書かれた名前・URLも拾う（後から素材を足す場合）
        comments = []
        try:
            comments = api(it["comments_url"] + "?per_page=100", tok) or []
            for c in comments:
                a, b = wanted(c.get("body"))
                names += a; urls += b
        except Exception:
            pass
        # 文字の素材（詩・原稿）：本文の先頭が【短縮版の詩】／【原稿】のコメントを原稿として受け取る（2026-10-15・#975）
        for c in comments:
            body = c.get("body") or ""
            if not GENKOU.match(body) or str(c["id"]) in rec.setdefault("genkou", {}):
                continue
            os.makedirs(os.path.join(HDD, "issue" + num), exist_ok=True)
            dest = os.path.join(HDD, "issue" + num, "genkou_%s.md" % c["id"])
            open(dest, "w", encoding="utf-8").write(body)
            rec["genkou"][str(c["id"])] = {"to": dest, "url": c.get("html_url"), "chars": len(body),
                                           "at": time.strftime("%F %T")}
            kaeshi(num, "Issue #%s に原稿が届いた（%d字・%s）。工場が受け取り済み：%s" % (num, len(body), c.get("html_url"), dest))
            try:
                api(it["comments_url"], tok, {"body": "工場が原稿を受け取りました（sozai_hiroi.py・自動）：%s（%d字）" % (c.get("html_url"), len(body))})
            except Exception as e:
                rec.setdefault("errors", {})["genkou_comment"] = type(e).__name__
        rec["wanted"] = sorted(set(names)) + sorted(set(urls))
        work = os.path.join(HDD, "issue" + num)
        newly = []
        for key in sorted(set(names)) + sorted(set(urls)):
            if key in rec["files"]:
                continue
            os.makedirs(work, exist_ok=True)
            try:
                if key.startswith("https://"):
                    dest = os.path.join(work, os.path.basename(key.split("?")[0]) or "sozai")
                    fetch_url(key, tok, dest)
                    src = key
                else:
                    src = find_local(key)
                    if not src:
                        continue
                    dest = os.path.join(work, key)
                    shutil.copy2(src, dest)
                info = {"from": src.replace(HOME, "~"), "to": dest, "sha256": sha(dest),
                        "bytes": os.path.getsize(dest), "sec": dur(dest), "at": time.strftime("%F %T")}
                rec["files"][key] = info
                newly.append((key, info))
            except Exception as e:
                rec.setdefault("errors", {})[key] = "%s %s" % (type(e).__name__, str(e)[:120])
        if newly:
            lines = ["工場が素材を受け取りました（sozai_hiroi.py・自動）："]
            for k, i in newly:
                lines.append("- `%s` ← %s／%s秒・%dB・sha256 %s…" % (k, i["from"], i["sec"], i["bytes"], i["sha256"][:12]))
            lines.append("置き場：iMac HDD 作業中/issue%s/（元ファイルは消していません）" % num)
            try:
                api(it["comments_url"], tok, {"body": "\n".join(lines)})
                for k, _ in newly:
                    rec["files"][k]["commented"] = True
            except Exception as e:
                rec.setdefault("errors", {})["comment"] = type(e).__name__
        rec["missing"] = [k for k in rec["wanted"] if k not in rec["files"]]
    return save(st)


GENKOU = re.compile(r"^\s*【(短縮版の詩|原稿)】")


def kaeshi(num, text):
    """Dispatch へ1行（status/dispatch_outbox.jsonl）。"""
    try:
        line = {"at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "from": "sozai_hiroi", "issue": num, "text": text}
        with open(os.path.join(REPO, "status", "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


def save(st):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    return st


def self_test():
    body = ("Suno曲 `Montage de Voyage.mp3`（ChatGPT会話で受領）と `poem.txt`。"
            "`tools/x.py` は対象外。https://github.com/tamago2022/joy-relief-station/releases/download/v1/a.mp3 "
            "https://github.com/user-attachments/files/123/b.zip")
    names, urls = wanted(body)
    assert names == ["Montage de Voyage.mp3", "poem.txt"], names
    assert urls == ["https://github.com/tamago2022/joy-relief-station/releases/download/v1/a.mp3",
                    "https://github.com/user-attachments/files/123/b.zip"], urls
    assert n("Ｍontage") != n("montage") and n("Montage de Voyage.MP3") == n("montage de voyage.mp3")
    assert GENKOU.match("【短縮版の詩】\n僕は見た") and GENKOU.match("  【原稿】x")
    assert not GENKOU.match("催促です。先頭を【短縮版の詩】にしてください")
    print("self-test OK", names, urls)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        run()
