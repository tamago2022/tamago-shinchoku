#!/usr/bin/env python3
"""一つの会議室：Vaultの 00_現在地.md（正本）を GitHub 2か所へ写す。
 ①非公開 tamago2022/tamago-dispatch-log  genzaichi.md
 ②非公開 tamago2022/joy-relief-station   docs/genzaichi.md（鍵・個人情報を除いた版）
中身が変わった時だけ動く（ハッシュ比較）。heartbeat.sh から呼ばれる。鍵・個人情報はこのファイルに持たない。"""
import base64, hashlib, json, os, re, subprocess, sys
V = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain/00_現在地.md"
STATE = os.path.join(os.path.dirname(__file__), "..", "status", ".genzaichi_sync_state")
TARGETS = [("tamago2022/tamago-dispatch-log", "genzaichi.md"),
           ("tamago2022/joy-relief-station", "docs/genzaichi.md")]
SECRET = [r"sk-[A-Za-z0-9_\-]{12,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"AIza[0-9A-Za-z_\-]{20,}",
          r"xox[baprs]-[A-Za-z0-9\-]{10,}", r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}",
          r"[A-Za-z0-9+/_\-]{40,}", r"[\w.+-]+@[\w-]+\.[\w.]+", r"/Users/[^\s)]+"]
def scrub(t):
    for p in SECRET: t = re.sub(p, "［除去］", t)
    return t
GH = next((x for x in ("/Users/mac/.local/bin/gh","/opt/homebrew/bin/gh","/usr/local/bin/gh","/usr/bin/gh") if os.path.exists(x)), "gh")
def gh(*a, inp=None):
    return subprocess.run([GH, *a], input=inp, capture_output=True, text=True, timeout=40)
def put(repo, path, text, msg):
    r = gh("api", f"repos/{repo}/contents/{path}")
    sha = json.loads(r.stdout).get("sha") if r.returncode == 0 else None
    body = {"message": msg, "content": base64.b64encode(text.encode()).decode()}
    if sha: body["sha"] = sha
    r = gh("api", "-X", "PUT", f"repos/{repo}/contents/{path}", "--input", "-", inp=json.dumps(body))
    return r.returncode == 0, (r.stderr or "")[:200]
def main(force=False):
    text = open(V, encoding="utf-8").read()
    h = hashlib.sha256(text.encode()).hexdigest()
    last = open(STATE).read().strip() if os.path.exists(STATE) else ""
    if h == last and not force: return 0
    ok_all = True
    for repo, path in TARGETS:
        body = text if "dispatch-log" in repo else scrub(text)
        ok, err = put(repo, path, body, "現在地を自動で写し（genzaichi_sync）")
        print(("写した " if ok else "失敗 ") + f"{repo}/{path} {err}")
        ok_all &= ok
    if ok_all: open(STATE, "w").write(h)
    return 0 if ok_all else 1
if __name__ == "__main__": sys.exit(main("--force" in sys.argv))
