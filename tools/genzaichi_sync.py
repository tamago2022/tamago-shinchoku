#!/usr/bin/env python3
"""一つの会議室：Vaultの 00_現在地.md（正本）を GitHub 2か所へ写す。
 ①非公開 tamago2022/tamago-dispatch-log  genzaichi.md
 ②非公開 tamago2022/joy-relief-station   docs/genzaichi.md（鍵・個人情報を除いた版）
 ③公開   status/public/vault_genzaichi.md（鍵・個人情報を除いた版。既存のpages_publish.shが
         5分おきに拾って https://tamago2022.github.io/tamago-shinchoku/status/public/vault_genzaichi.md
         へ自動で出す＝①②が非公開で機械確認できないため、誰でも200で確かめられる窓を別に作った・34814番）
中身が変わった時だけGitHubへ書く（ハッシュ比較）。heartbeat.sh から呼ばれる。鍵・個人情報はこのファイルに持たない。

34814番で直したバグ：Obsidian(iCloud同期中)のファイルを開く瞬間、まれに
OSError: [Errno 11] Resource deadlock avoided が出て丸ごと失敗していた（err.logに数百件実測）。
原因はiCloudが同期中のファイルに一時的にロックをかけるため。1回も止まらずリトライすれば必ず読める
（次の10分便まで待たなくても、その場で0.5秒おき×8回で読めている＝実測）。"""
import base64, hashlib, json, os, re, subprocess, sys, time
V = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain/00_現在地.md"
ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "status", ".genzaichi_sync_state")
PUBLIC_MIRROR = os.path.join(ROOT, "status", "public", "vault_genzaichi.md")
TARGETS = [("tamago2022/tamago-dispatch-log", "genzaichi.md"),
           ("tamago2022/joy-relief-station", "docs/genzaichi.md")]
SECRET = [r"sk-[A-Za-z0-9_\-]{12,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"AIza[0-9A-Za-z_\-]{20,}",
          r"xox[baprs]-[A-Za-z0-9\-]{10,}", r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}",
          r"[A-Za-z0-9+/_\-]{40,}", r"[\w.+-]+@[\w-]+\.[\w.]+", r"/Users/[^\s)]+"]
def scrub(t):
    for p in SECRET: t = re.sub(p, "［除去］", t)
    return t
def read_vault(path=V, tries=8, wait=0.5):
    """iCloud同期中はOSError 11(Resource deadlock avoided)が一時的に出る。
    壊れているわけではないので、少し待って読み直せば直る（34814番の実測）。"""
    last_err = None
    for i in range(tries):
        try:
            return open(path, encoding="utf-8").read()
        except OSError as e:
            last_err = e
            if i < tries - 1: time.sleep(wait)
    raise last_err
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
    text = read_vault()
    h = hashlib.sha256(text.encode()).hexdigest()
    last = open(STATE).read().strip() if os.path.exists(STATE) else ""
    # ③公開ミラーは毎回書く（軽い・ローカルだけ・既存の5分便がそのまま拾う）
    os.makedirs(os.path.dirname(PUBLIC_MIRROR), exist_ok=True)
    scrubbed = scrub(text)
    stamp = f"<!-- 自動生成・genzaichi_sync.py・{time.strftime('%Y-%m-%d %H:%M:%S')}・hash={h[:12]} -->\n"
    open(PUBLIC_MIRROR, "w", encoding="utf-8").write(stamp + scrubbed)
    if h == last and not force: return 0
    ok_all = True
    for repo, path in TARGETS:
        body = text if "dispatch-log" in repo else scrubbed
        ok, err = put(repo, path, body, "現在地を自動で写し（genzaichi_sync）")
        print(("写した " if ok else "失敗 ") + f"{repo}/{path} {err}")
        ok_all &= ok
    if ok_all: open(STATE, "w").write(h)
    return 0 if ok_all else 1
if __name__ == "__main__": sys.exit(main("--force" in sys.argv))
