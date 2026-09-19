#!/usr/bin/env python3
"""
668番：done全件のurlsを1本ずつ実際に開いて404/403/410を洗い出す。
バックグラウンド実行はしない。このプロセス内で同期的に全部処理して結果をJSONへ保存する。
"""
import json
import concurrent.futures
import re
import urllib.request
import urllib.error
import urllib.parse
import time

REPO = "/Users/mac/Desktop/tamago-shinchoku"
QUEUE = REPO + "/status/queue.json"
OUT = REPO + "/status/_668_link_audit_result.json"

UA = "Mozilla/5.0 (tamago-668-link-audit)"

# queue.jsonのurls欄には「URL（日本語の説明）」「URL`（説明」のように
# 実URLの直後に日本語の注釈がくっついている行がある。実URLだけを切り出す。
STOP_CHARS = "（`　 \n\t"

def extract_real_url(raw):
    u = raw.strip()
    cut = len(u)
    for ch in STOP_CHARS:
        idx = u.find(ch)
        if idx != -1:
            cut = min(cut, idx)
    real = u[:cut].rstrip("`").strip()
    return real, (real != u)

def check_url(raw):
    u, had_note = extract_real_url(raw)
    # 非公開リポジトリは問答無用でNG(そもそも本人には開けない)
    if "github.com/tamago2022/joy-relief-station" in u:
        return raw, u, "PRIVATE_REPO_NG", None
    try:
        # ASCII化できない文字が残っていればパーセントエンコードする
        parsed = urllib.parse.urlsplit(u)
        path = urllib.parse.quote(parsed.path, safe="/%:@")
        query = urllib.parse.quote(parsed.query, safe="=&%:@/,")
        u2 = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))
    except Exception:
        u2 = u
    req = urllib.request.Request(u2, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return raw, u, resp.getcode(), None
    except urllib.error.HTTPError as e:
        return raw, u, e.code, None
    except Exception as e:
        return raw, u, None, str(e)

def main():
    with open(QUEUE, encoding="utf-8") as f:
        d = json.load(f)
    items = [it for it in d["items"] if it.get("status") == "done"]

    url_to_items = {}
    for it in items:
        for u in (it.get("urls") or []):
            url_to_items.setdefault(u, []).append({"n": it.get("n"), "title": it.get("title")})

    all_urls = list(url_to_items.keys())
    print("done件数=%d urls欄空=%d 総URL(重複除く)=%d" % (
        len(items), len([it for it in items if not it.get("urls")]), len(all_urls)))

    results = {}
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(check_url, u): u for u in all_urls}
        done_count = 0
        for fut in concurrent.futures.as_completed(futs):
            raw, real_u, code, err = fut.result()
            results[raw] = {"realUrl": real_u, "code": code, "err": err}
            done_count += 1
            if done_count % 40 == 0:
                print("progress %d/%d (%.1fs)" % (done_count, len(all_urls), time.time() - t0))

    print("全%d本チェック完了 (%.1fs)" % (len(all_urls), time.time() - t0))

    dead = []
    for raw, r in results.items():
        code = r["code"]
        is_dead = (code in (404, 403, 410)) or (code == "PRIVATE_REPO_NG") or (code is None)
        if is_dead:
            for it in url_to_items[raw]:
                dead.append({
                    "n": it["n"], "title": it["title"], "url": raw,
                    "realUrl": r["realUrl"], "code": code, "err": r["err"],
                })

    dead.sort(key=lambda x: (x["n"] if x["n"] is not None else -1))

    out = {
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S+0900"),
        "doneCount": len(items),
        "totalUrls": len(all_urls),
        "deadCount": len(dead),
        "dead": dead,
        "urlsMissingItems": [it["n"] for it in items if not it.get("urls")],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("\n=== 死んでいるURL: %d本 ===" % len(dead))
    for x in dead:
        print("n=%s code=%s err=%s title=%s" % (x["n"], x["code"], x["err"], x["title"]))
        print("   " + x["url"])
    print("\n結果保存: %s" % OUT)

if __name__ == "__main__":
    main()
