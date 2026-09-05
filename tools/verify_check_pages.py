#!/usr/bin/env python3
"""
確認ページ(share/check/*.html)の機械検品（恒久版・汎用）。

背景：444番バッチで「確認ページにスクショが無いのに status:done にした」誤りが
2件(n=20, n=13)発生した。原因は「本番URLが200を返す」「本文がそれらしい」だけで
自動OKにしていたこと。この恒久スクリプトは、次の3条件をすべてAND判定し、
1つでも欠けたら自動OKにしない（言い訳文言があってもPASSにしない）。

  ① 本番URL（queue.jsonのurls欄。無ければ確認ページ自体）へHTTPアクセスし200が返るか
  ② 確認ページ本文に、依頼内容を裏付ける具体的な記述（数字・件数・Before/After・
     実測/確認済み等）があるか（簡易ヒューリスティック。空・「未着手」的な文言ならFAIL）
  ③ 確認ページのHTML内に実際の <img ...> タグ（スクリーンショット埋め込み）が
     存在するか（これが無い時点で問答無用でFAIL。「スクショはありません」という
     言い訳文言があってもPASSにしない）

次回以降の分割バッチ(444/445/446/...)からも使い回せるよう、使い捨てスクリプト
(_oni_kantoku_44*.py)を量産しない代わりにこれを恒久ツールとして置く。

使い方:
  # 判定だけ見る（書き込みなし）
  python3 tools/verify_check_pages.py --n 23 22 19 18 10 20 2 7 11 13

  # 判定してqueue.jsonへ反映する（ロック取得・最新読み直し・監査ログ追記まで行う）
  python3 tools/verify_check_pages.py --n 23 22 19 18 10 20 2 7 11 13 \
      --apply --task 444-2of9
"""
import argparse
import datetime
import fcntl
import glob
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

REPO = "/Users/mac/Desktop/tamago-shinchoku"
QUEUE = os.path.join(REPO, "status", "queue.json")
QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")
AUDIT_LOG = os.path.join(REPO, "status", "oni_kantoku_log.jsonl")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/"

UA = "Mozilla/5.0 (tamago-oni-kantoku verify_check_pages.py)"

EVIDENCE_PATTERNS = [
    r"\d+\s*件", r"\d+\s*本", r"\d+\s*曲", r"\d+\s*人", r"\d+\s*%",
    r"[Bb]efore", r"[Aa]fter", r"ビフォー", r"アフター", r"前\s*[→\-].{0,3}後",
    r"実測", r"確認済み", r"本番で確認", r"コミット\s*[0-9a-f]{6,}", r"commit\s*[0-9a-f]{6,}",
]
NEGATIVE_PATTERNS = [
    r"未着手", r"まだ手を付けていません", r"これから対応", r"準備中です",
    r"スクショはありません", r"画像はありません", r"キャプチャは撮れませんでした",
]


@contextmanager
def queue_lock(timeout=180.0):
    """status/.queue.lock を flock で排他する（auto_launcher.py と同じ方式）。"""
    f = io.open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                f.close()
                raise RuntimeError("queue_lock timeout（他セッションがqueue.jsonを触っている）")
            time.sleep(0.2)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def http_get(url, timeout=15):
    """(status_code_or_None, body_text) を返す。例外は握りつぶさずNoneで表現する。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return code, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, f"__ERROR__:{e}"


def classify_urls(urls):
    check_pages, prod = [], []
    for u in (urls or []):
        if "share/check/" in u:
            check_pages.append(u)
        else:
            prod.append(u)
    return check_pages, prod


def find_check_page_local(n):
    return sorted(glob.glob(os.path.join(REPO, "share", "check", f"{n}-*.html")))


def verify_one(item):
    n = item.get("n")
    title = item.get("title", "")
    urls = item.get("urls") or []
    check_page_urls, prod_urls = classify_urls(urls)

    local_pages = find_check_page_local(n)
    if not check_page_urls:
        for p in local_pages:
            rel = os.path.relpath(p, REPO)
            check_page_urls.append(PAGES_BASE + rel)

    reasons = []

    # ---- ① 本番URL（無ければ確認ページ自体）へアクセスし200か ----
    urls_to_check = prod_urls if prod_urls else check_page_urls
    if not urls_to_check:
        cond1 = False
        reasons.append("①FAIL: urls欄が空で確認ページも見つからない（urls欠落）")
    else:
        cond1 = True
        codes = []
        for u in urls_to_check:
            code, _ = http_get(u)
            codes.append("%s => %s" % (u, code))
            if code != 200:
                cond1 = False
        reasons.append(("①PASS" if cond1 else "①FAIL") + ": " + " / ".join(codes))

    # ---- 確認ページ本文の取得（②③判定用） ----
    page_html = ""
    page_source = ""
    if check_page_urls:
        code, body = http_get(check_page_urls[0])
        if code == 200 and body and not body.startswith("__ERROR__:"):
            page_html = body
            page_source = check_page_urls[0]
    if not page_html and local_pages:
        try:
            with open(local_pages[0], encoding="utf-8") as f:
                page_html = f.read()
            page_source = local_pages[0] + "（ローカル代替）"
        except Exception:
            pass

    text_only = re.sub(r"<[^>]+>", " ", page_html) if page_html else ""

    # ---- ② 具体的な記述の有無 ----
    if not page_html:
        cond2 = False
        reasons.append("②FAIL: 確認ページ本文を取得できない")
    else:
        has_evidence = any(re.search(p, text_only) for p in EVIDENCE_PATTERNS)
        has_negative = any(re.search(p, text_only) for p in NEGATIVE_PATTERNS)
        cond2 = has_evidence and not has_negative
        reasons.append(
            ("②PASS" if cond2 else "②FAIL")
            + ": evidence=%s negative_hit=%s source=%s" % (has_evidence, has_negative, page_source)
        )

    # ---- ③ <img> タグの実在（欠けたら問答無用でFAIL） ----
    img_tags = re.findall(r"<img\b[^>]*>", page_html or "", flags=re.I)
    cond3 = len(img_tags) > 0
    reasons.append(("③PASS" if cond3 else "③FAIL") + ": img_count=%d" % len(img_tags))

    passed = cond1 and cond2 and cond3
    return {
        "n": n,
        "title": title,
        "passed": passed,
        "reasons": reasons,
        "checkPageUrls": check_page_urls,
        "prodUrls": prod_urls,
    }


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")


def now_disp():
    return datetime.datetime.now().strftime("%m-%d %H:%M")


def apply_results(results, task_tag):
    """queue.jsonをロックして最新を読み直し、判定結果だけを反映する。"""
    with queue_lock():
        with open(QUEUE, encoding="utf-8") as f:
            d = json.load(f)

        audit_lines = []
        by_n = {r["n"]: r for r in results}
        for item in d["items"]:
            n = item.get("n")
            if n not in by_n:
                continue
            r = by_n[n]
            summary = " / ".join(r["reasons"])
            if r["passed"]:
                item["status"] = "done"
                item["okBy"] = "oni-kantoku-verify_check_pages-%s" % task_tag
                item["okNote"] = "機械検品PASS(①②③すべて満たす): " + summary
                item["checkedAt"] = now_iso()
                decision = "pass"
            else:
                was_done = item.get("status") == "done"
                item["verifyNote"] = "機械検品FAIL: " + summary
                item["checkedAt"] = now_iso()
                if was_done:
                    note = (
                        "\n\n【鬼監督(verify_check_pages.py)差し戻し・%s】"
                        "必須条件①②③をAND判定した結果FAIL。%s"
                    ) % (now_disp(), summary)
                    item["what"] = item.get("what", "") + note
                    item["status"] = "awaiting_check"
                    item["redoCount"] = item.get("redoCount", 0) + 1
                    item.pop("okBy", None)
                    item.pop("okNote", None)
                    decision = "redo(done->awaiting_check)"
                else:
                    decision = "fail(status unchanged: %s)" % item.get("status")
            audit_lines.append({
                "n": n,
                "title": item.get("title"),
                "decision": decision,
                "reason": summary,
                "checkedAt": now_iso(),
                "task": task_tag,
            })

        d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(QUEUE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write("\n")

        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            for line in audit_lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    return audit_lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, nargs="+", required=True, help="検品するqueue.jsonのn番号（複数可）")
    ap.add_argument("--apply", action="store_true", help="判定をqueue.jsonへ反映する（未指定なら判定表示のみ）")
    ap.add_argument("--task", default="manual", help="監査ログ・okByに残すタスク識別タグ（例: 444-2of9）")
    args = ap.parse_args()

    with open(QUEUE, encoding="utf-8") as f:
        d = json.load(f)
    items_by_n = {it.get("n"): it for it in d["items"]}

    results = []
    for n in args.n:
        item = items_by_n.get(n)
        if item is None:
            print("n=%d: queue.jsonに見つからない（スキップ）" % n)
            continue
        r = verify_one(item)
        results.append(r)
        mark = "PASS" if r["passed"] else "FAIL"
        print("n=%d [%s] %s" % (n, mark, r["title"]))
        for line in r["reasons"]:
            print("   " + line)

    passed_n = [r["n"] for r in results if r["passed"]]
    failed_n = [r["n"] for r in results if not r["passed"]]
    print("\n---")
    print("PASS(%d): %s" % (len(passed_n), passed_n))
    print("FAIL(%d): %s" % (len(failed_n), failed_n))

    if args.apply:
        audit = apply_results(results, args.task)
        print("\nqueue.json反映済み・監査ログ%d行追記: %s" % (len(audit), AUDIT_LOG))
    else:
        print("\n(--apply が無いので queue.json への書き込みはしていません)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
