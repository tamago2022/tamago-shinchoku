#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Xの投稿を Obsidian（Vault tamago_brain）にメモする道具（x_memo）— 2026-10-29 たまごさん指示

たまごさんが手でやっていた ①タイトル ②本文コピペ ③リンク ④発信者のハッシュタグ を、URL 1本で済ませる。
手本（たまごさんの実物・Vault直下）：
    #ダリオアモデイ
    #チャエン

    【注目】AnthropicのダリオCEO「…こなす」 GPT-2の時点で、… ・GPT-2を見て…

    https://x.com/masahirochaen/status/2115563790972637191?…
  ・ファイル名＝タイトル（本文1行目から【注目】などの札を外したもの）・置き場＝Vault直下
  ・タグ＝話題の人物 → 発信者の順。表記は tools/x_memo_tags.json（Vaultの既存タグから取った表）。新しい表記は作らない
  ・本文＝投稿の全文（改行は空白1つにつなぐ＝たまごさんのコピペと同じ形）・最後に元の投稿のURL（渡されたまま）
  ・同じ投稿（ステータスID）のノートが既にあれば作らない。同じ名前の別ノートがあれば「 2」を付ける。上書きはしない

使い方：
  python3 tools/x_memo.py <XのURL> [--tag 話題タグ ...]   # ノートを作る（Vaultの既存表記があればそれに合わせ、無ければ空白→_）
  python3 tools/x_memo.py <URL> --dry                      # 作らずに中身だけ見る
  python3 tools/x_memo.py --self-test
サンドボックスから呼ぶと status/mac_jobs/pending/ に札を置き、Mac で走らせた結果を読む（ブラウザ・許可ポップアップなし）。
読むのは tools/link_yomu.py（oEmbed＋FxTwitter）。一時ファイルは作らない。最後の行に JSON 1行（path・link・drive）。
リンクは2本（2026-10-29 たまごさん「obsidian:// のリンクがスマホでは開けない」）：
  link  ＝ https の中継ページ share/o.html?file=…（開くと obsidian:// へ飛ぶ。Dispatch のスマホでも押せる）
  drive ＝ Googleドライブの写し（gdrive_md_mirror・5分おき）。写しのIDが取れればファイルの直リンク、まだならドライブの名前検索。
  中継ページにも d=<ID> を渡すので、ページ内の「Obsidianで開けないときはこちら」も同じ写しへ行く。
"""
from __future__ import print_function

import io
import json
import os
import re
import shlex
import sys
import time
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
VAULT_NAME = "tamago_brain"
VAULT = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/" + VAULT_NAME)
TABLE = os.path.join(REPO, "tools", "x_memo_tags.json")
JOBS = os.path.join(REPO, "status", "mac_jobs")
DRIVE_ROOT = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/" + VAULT_NAME)
RELAY = "https://tamago2022.github.io/tamago-shinchoku/share/o.html"
NG = '\\/:*?"<>|#^[]'


def load_table():
    return json.load(io.open(TABLE, encoding="utf-8"))


def x_ids(url):
    m = re.search(r"(?:x|twitter|fxtwitter|vxtwitter|fixupx)\.com/([^/?#]+)/status(?:es)?/(\d+)", url)
    return (m.group(1), m.group(2)) if m else (None, None)


def make_title(text):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    t = lines[0] if lines else ""
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^(?:【[^】]{1,12}】\s*)+", "", t).strip()
    t = re.sub(r"\s#\S+", "", t).strip()
    if len(t) > 100:  # 長すぎる1行目は文の切れ目で切る
        m = re.search(r"^.{20,100}?[。！？!?」]", t)
        t = m.group(0) if m else t[:100]
    for ch in NG:
        t = t.replace(ch, {"/": "／", ":": "：", "?": "？", "|": "｜", "#": "＃", "*": "＊", '"': "”", "<": "＜", ">": "＞"}.get(ch, ""))
    return t.strip().rstrip(".") or "Xメモ"


def flat(text):
    return re.sub(r"[ \t　]*\n+[ \t　]*", " ", (text or "").strip()).strip()


def norm(t):
    return re.sub(r"[\s_・･\-]", "", t).lower()


TAG_RE = re.compile(r"(?:^|[\s　])#([^\s#　,、。「」()（）\[\]]+)")


def scan_vault(sid):
    """Vault を1回だけ歩く：既存タグの数・同じ投稿のノート"""
    tags, dups = {}, []
    for dp, dns, fns in os.walk(VAULT):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for fn in fns:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            try:
                s = io.open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if sid and re.search(r"/status/%s(?!\d)" % sid, s):
                dups.append(os.path.relpath(p, VAULT))
            for t in TAG_RE.findall(re.sub(r"https?://\S+", "", s)):
                tags[t] = tags.get(t, 0) + 1
    return tags, dups


def fit_tag(want, vault_tags):
    """Vault に同じ表記（空白・_・大文字小文字の違いだけ）があれば、一番使われている表記に合わせる"""
    w = want.lstrip("#").strip()
    same = sorted([t for t in vault_tags if norm(t) == norm(w)], key=lambda t: -vault_tags[t])
    return same[0] if same else re.sub(r"\s+", "_", w)


def pick_tags(text, user, extra, table, vault_tags):
    out = []
    for tag, keys in table.get("wadai", {}).items():
        if any(k.lower() in (text or "").lower() for k in keys):
            out.append(tag)
    for e in extra:
        out.append(fit_tag(e, vault_tags))
    s = (table.get("hasshinsha", {}).get((user or "").lower()) or {}).get("tag")
    if s:
        out = [t for t in out if t != s] + [s]
    seen, res = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            res.append(t)
    return res


def clean(text):
    """本文の末尾に付く画像・動画の短縮リンク（pic.twitter.com／t.co）を外す"""
    t = re.sub(r"(?:\s*(?:https?://)?(?:pic\.twitter\.com|t\.co)/\w+)+\s*$", "", (text or "").strip())
    return t.strip()


def full_text(link_yomu, user, sid, otext):
    """oEmbed は長い投稿を「…」で切るので、FxTwitter の全文があればそちらを使う"""
    try:
        fx = json.loads(link_yomu.get("https://api.fxtwitter.com/%s/status/%s" % (user, sid)))
        ft = ((fx.get("tweet") or {}).get("text") or "").strip()
    except Exception:
        ft = ""
    o, f = clean(otext), clean(ft)
    return f if len(f) > len(o.rstrip("…")) else o


def build(text, url, tags):
    return "\n".join(["#" + t for t in tags]) + "\n\n" + flat(clean(text)) + "\n\n" + url


def obsidian_url(rel):
    f = rel[:-3] if rel.endswith(".md") else rel
    return "obsidian://open?vault=%s&file=%s" % (urllib.parse.quote(VAULT_NAME, safe=""), urllib.parse.quote(f, safe=""))


def drive_id(rel):
    """Drive for desktop がファイルに付ける ID（写しがまだ無い・上がっていなければ None）"""
    import subprocess
    p = os.path.join(DRIVE_ROOT, rel)
    if not os.path.exists(p):
        return None
    try:
        r = subprocess.run(["/usr/bin/xattr", "-p", "com.google.drivefs.item-id#S", p], capture_output=True, timeout=10)
    except Exception:
        return None
    v = r.stdout.decode("utf-8", "replace").strip()
    return v if r.returncode == 0 and re.match(r"^[A-Za-z0-9_-]{10,}$", v) and not v.startswith("local") else None


def drive_url(rel, did=None):
    if did:
        return "https://drive.google.com/file/d/%s/view" % did
    name = os.path.splitext(os.path.basename(rel))[0]
    return "https://drive.google.com/drive/search?q=" + urllib.parse.quote('"%s"' % name, safe="")


def relay_url(rel, did=None):
    f = rel[:-3] if rel.endswith(".md") else rel
    u = RELAY + "?file=" + urllib.parse.quote(f, safe="")
    return u + ("&d=" + did if did else "")


def links(rel, did=None):
    return {"link": relay_url(rel, did), "drive": drive_url(rel, did), "obsidian": obsidian_url(rel)}


def free_name(title, suffix=""):
    base = title + suffix
    n = 1
    while True:
        rel = (base if n == 1 else "%s %d" % (base, n)) + ".md"
        if not os.path.exists(os.path.join(VAULT, rel)):
            return rel
        n += 1


def run(url, extra, dry=False, test_suffix=""):
    import link_yomu
    user, sid = x_ids(url)
    if not sid:
        return {"ok": False, "why": "X の投稿URLではない", "url": url}
    r = link_yomu.read_x(url)
    r["text"] = full_text(link_yomu, user, sid, r.get("text") or "")
    if not r.get("ok") or not r.get("text"):
        return {"ok": False, "why": "読めなかった：" + " ／ ".join(r.get("errors") or []), "url": url}
    vault_tags, dups = scan_vault(sid)
    res = {"ok": True, "url": url, "author": r.get("author"), "date": r.get("date"),
           "videos": r.get("videos", 0), "photos": r.get("photos", 0)}
    if dups and not test_suffix:
        res.update(ok=True, made=False, why="同じ投稿のノートが既にある", path=dups[0], **links(dups[0], drive_id(dups[0])))
        return res
    title = make_title(r["text"])
    tags = pick_tags(r["text"], user, extra, load_table(), vault_tags)
    body = build(r["text"], url, tags)
    rel = free_name(title, test_suffix)
    res.update(title=title, tags=tags, path=rel, body=body, **links(rel))
    if dry:
        res["made"] = False
        return res
    p = os.path.join(VAULT, rel)
    with io.open(p, "x", encoding="utf-8") as f:  # "x"＝既にあれば失敗＝上書きしない
        f.write(body)
    res["made"] = True
    return res


def via_mac(args, wait=200):
    name = "xmemo_%s_%d" % (time.strftime("%H%M%S"), os.getpid())
    os.makedirs(os.path.join(JOBS, "pending"), exist_ok=True)
    sh = "#!/bin/bash\n# x_memo.py が置いた1回きりの札\ncd \"$HOME/tamago/tamago-shinchoku\"\n/usr/bin/python3 tools/x_memo.py %s\n" % " ".join(shlex.quote(a) for a in args)
    tmp = os.path.join(JOBS, "pending", name + ".sh.tmp")
    io.open(tmp, "w", encoding="utf-8").write(sh)
    os.replace(tmp, tmp[:-4])
    done = os.path.join(JOBS, "done", name + ".out")
    end = time.time() + wait
    while time.time() < end:
        if os.path.exists(done):
            time.sleep(2)
            s = io.open(done, encoding="utf-8", errors="ignore").read()
            sys.stdout.write(s)
            return 0 if '"ok": true' in s else 2
        time.sleep(3)
    print("Macが%d秒で拾わなかった（後で %s を見る）" % (wait, os.path.relpath(done, REPO)))
    return 3


def self_test():
    ok = True
    ok &= make_title("【注目】AnthropicのダリオCEO「6か月後には難しかったことが簡単に」\nGPT-2の時点で") == "AnthropicのダリオCEO「6か月後には難しかったことが簡単に」"
    ok &= make_title("a/b: c?\n2") == "a／b： c？"
    ok &= flat("一\n\n・二\n・三 ") == "一 ・二 ・三"
    t = {"hasshinsha": {"masahirochaen": {"tag": "チャエン"}}, "wadai": {"ダリオアモデイ": ["ダリオ"]}}
    ok &= pick_tags("ダリオCEO", "MasahiroChaen", [], t, {}) == ["ダリオアモデイ", "チャエン"]
    ok &= pick_tags("x", "nobody", ["Gemini for Google Workspace"], t, {}) == ["Gemini_for_Google_Workspace"]
    ok &= pick_tags("x", "nobody", ["Gemini for Google Workspace"], t, {"gemini_for_google_workspace": 3}) == ["gemini_for_google_workspace"]
    ok &= build("A\nB pic.twitter.com/3sJxAmpT0N", "https://x.com/a/status/1", ["t1", "t2"]) == "#t1\n#t2\n\nA B\n\nhttps://x.com/a/status/1"
    ok &= clean("本文 https://t.co/abc") == "本文" and clean("本文") == "本文"
    ok &= obsidian_url("あ い.md") == "obsidian://open?vault=tamago_brain&file=%E3%81%82%20%E3%81%84"
    ok &= relay_url("あ い.md") == RELAY + "?file=%E3%81%82%20%E3%81%84"
    ok &= relay_url("a/b.md", "17GQwsPv9nqUunFgcc5zG4VG4-AQkLU2R").endswith("?file=a%2Fb&d=17GQwsPv9nqUunFgcc5zG4VG4-AQkLU2R")
    ok &= drive_url("x.md", "ABCDEFGHIJK") == "https://drive.google.com/file/d/ABCDEFGHIJK/view"
    ok &= drive_url("あ.md") == "https://drive.google.com/drive/search?q=%22%E3%81%82%22"
    ok &= drive_id("存在しないノート_selftest.md") is None
    tb = load_table()
    ok &= tb["hasshinsha"]["masahirochaen"]["tag"] == "チャエン"
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    if sys.platform != "darwin":
        return via_mac(a)
    extra, urls, dry, suffix, i = [], [], "--dry" in a, "", 0
    while i < len(a):
        if a[i] == "--tag" and i + 1 < len(a):
            extra.append(a[i + 1]); i += 2; continue
        if a[i] == "--test-suffix" and i + 1 < len(a):  # 手本と比べる試し用（重複チェックを飛ばし、別名で作る）
            suffix = a[i + 1]; i += 2; continue
        if not a[i].startswith("--"):
            urls.append(a[i])
        i += 1
    if not urls:
        print(__doc__)
        return 1
    rc = 0
    for u in urls:
        try:
            r = run(u, extra, dry, suffix)
        except Exception as e:
            r = {"ok": False, "url": u, "why": str(e)[:200]}
        if r.get("body"):
            print("---- %s%s" % (r["path"], "" if r.get("made") else "（作っていない）"))
            print(r["body"])
            print("----")
        if r.get("link"):
            print("スマホで開く：" + r["link"])
            print("ドライブの写し：" + r["drive"])
        print(json.dumps({k: v for k, v in r.items() if k not in ("body", "obsidian")}, ensure_ascii=False))
        rc = rc or (0 if r.get("ok") else 2)
    return rc


if __name__ == "__main__":
    sys.exit(main())
