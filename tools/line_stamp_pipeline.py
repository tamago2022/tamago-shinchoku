#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
769番：LINEスタンプ「申請機」本体。

背景（2026-09-12）：742番で鬼嫁ちゃん1本だけの「貼るだけ申請シート」を手書きで作った。
LINE Creators Market（creator.line.me）はブラウザ自動化を安全上の理由で禁止しているため、
「審査リクエストまで完全に無人で自動操作する」ことはできない（アカウント停止リスク）。
できる自動化は「文言・画像検品・チェックリストを、コピペするだけの状態まで機械が用意する」
ところまで。742番はこれを1キャラ限りのワンショットスクリプトで書いていたが、たまごさんが
「次からはフォルダを置くだけ」を求めているため、キャラクターごとの設定をJSON化し、
汎用パイプラインへ昇格させたのが本ファイル。

やること（1日1回・launchdから呼ぶ想定）:
  1. Googleドライブ「LINEスタンプ/」配下の各キャラクターフォルダをスキャン。
  2. tools/line_stamp_configs/*.json に対応する設定があれば、画像フォルダを検品
     （枚数・サイズ・透過・開けるかどうか。Driveの同期待ちで読めないファイルは
     「未確認」として区別し、エラー扱いにしない）。
  3. tools/make_check_page.py の render() を使い、①Display Information
     ②Sticker Images ③Preview ④Sales Information の4画面ぶんを
     「コピーボタン付きで並べる」貼るだけシートを share/check/ へ生成。
  4. 前回スキャンとの差分（新規フォルダ検知・シート初回生成）だけを
     status/dispatch_outbox.jsonl へ通知する（毎回同じ内容を騒がない）。
  5. --push で git add / commit / push まで。

新しいキャラクターを追加する時にやること（たまごさんの「フォルダを置くだけ」の実態）:
  - Googleドライブの「LINEスタンプ/<キャラ名>/」にフォルダを作って素材を置く。
  - tools/line_stamp_configs/<slug>.json を1つ追加する（文言はChatGPT等で決めた後でよい。
    無い項目は null のままでよく、シート側に「★たまごさんが埋める」と出る）。
  - 次の日次実行で自動的にシートが生成される。

使い方:
  python3 tools/line_stamp_pipeline.py --push
  python3 tools/line_stamp_pipeline.py --slug oniyome-chan --push   # 1キャラだけ強制再生成
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
CHECK_DIR = os.path.join(REPO, "share", "check")
CONFIG_DIR = os.path.join(HERE, "line_stamp_configs")
STATE_PATH = os.path.join(STATUS, "line_stamp_pipeline_state.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/share/check/"

GD_ROOT = (
    "/Users/mac/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/"
    "マイドライブ/LINEスタンプ"
)

# LINE Creators Market の公式規格（742番調査時点の実測値）。
MAX_STICKER_PX = 370
MIN_STICKER_COUNT_CHOICES = (8, 16, 24, 32, 40)

sys.path.insert(0, HERE)
import make_check_page as mcp  # noqa: E402

try:
    from PIL import Image
except Exception:
    Image = None

TASK_N = 769


def now_jst_str():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def load_json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(p, obj):
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def append_jsonl(p, row):
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_configs():
    if not os.path.isdir(CONFIG_DIR):
        return []
    out = []
    for name in sorted(os.listdir(CONFIG_DIR)):
        if name.endswith(".json"):
            cfg = load_json(os.path.join(CONFIG_DIR, name), None)
            if cfg:
                out.append(cfg)
    return out


def scan_drive_folders():
    """LINEスタンプ/ 直下のキャラクターフォルダ名一覧（新規検知用）。読めなければ空。"""
    try:
        return sorted(
            n for n in os.listdir(GD_ROOT)
            if os.path.isdir(os.path.join(GD_ROOT, n)) and not n.startswith(".")
        )
    except Exception as e:
        return {"__error__": str(e)}


def find_image_dir(cfg):
    """image_dir_candidatesのうち、実際に中身(画像 or zip)が1つ以上入っている
    最初の候補を返す。空フォルダは飛ばす（「個別PNG」が空で「完成ZIP」に本体がある
    ケースが実在するため）。"""
    base = os.path.join(GD_ROOT, cfg.get("drive_folder", ""))
    fallback = None
    for cand in cfg.get("image_dir_candidates") or []:
        p = os.path.join(base, cand) if cand else base
        if not os.path.isdir(p):
            continue
        if fallback is None:
            fallback = p
        try:
            if any(True for _ in os.scandir(p)):
                return p
        except Exception:
            continue
    return fallback


def find_zip_files(cfg):
    base = os.path.join(GD_ROOT, cfg.get("drive_folder", ""))
    out = []
    for cand in cfg.get("image_dir_candidates") or []:
        p = os.path.join(base, cand) if cand else base
        if not os.path.isdir(p):
            continue
        try:
            for nm in os.listdir(p):
                if nm.lower().endswith(".zip"):
                    out.append(os.path.join(p, nm))
        except Exception:
            continue
    return out


def inspect_zip(zip_path, retries=3, wait_sec=3):
    """zip内一覧の取得を試みる。Google Driveのプレースホルダが未ダウンロードだと
    'Resource deadlock avoided' や 'File is not a zip file' になるため、数回だけ
    待ってリトライし、それでも駄目なら『Drive同期待ち』として正直に報告する。"""
    import zipfile
    info = {"path": zip_path, "readable": False}
    try:
        info["size_bytes"] = os.path.getsize(zip_path)
    except Exception:
        info["size_bytes"] = None
    for _ in range(retries):
        try:
            with zipfile.ZipFile(zip_path) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                info["readable"] = True
                info["entry_count"] = len(names)
                info["entries_sample"] = names[:6]
                return info
        except Exception as e:
            info["error"] = str(e)
            time.sleep(wait_sec)
    return info


def inspect_images(dir_path, expected_count, timeout_each=2.0):
    """画像フォルダを検品する。Driveの同期待ちで読めないファイルは
    unreadable として区別し、失敗扱いにしない（Resource deadlock avoided対策）。
    """
    report = {
        "dir": dir_path,
        "checked": 0,
        "ok": 0,
        "oversize": [],
        "no_alpha": [],
        "unreadable": [],
        "files_found": 0,
        "zip_info": None,
    }
    if not dir_path or not os.path.isdir(dir_path) or Image is None:
        report["error"] = "フォルダが見つからない、またはPillow未使用"
        return report

    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = []
    zips = []
    try:
        for root, _dirs, names in os.walk(dir_path):
            for nm in names:
                if nm.lower().endswith(exts):
                    files.append(os.path.join(root, nm))
                elif nm.lower().endswith(".zip"):
                    zips.append(os.path.join(root, nm))
    except Exception as e:
        report["error"] = "一覧取得に失敗: %s" % e
        return report

    if not files and zips:
        report["zip_info"] = inspect_zip(zips[0])

    report["files_found"] = len(files)
    for fp in files:
        report["checked"] += 1
        t0 = time.time()
        try:
            with Image.open(fp) as im:
                im.load()
                w, h = im.size
                mode = im.mode
            if time.time() - t0 > timeout_each:
                pass  # 参考値のみ、打ち切りはしない（Pillow自体に非同期タイムアウトが無いため）
            ok = True
            if w > MAX_STICKER_PX or h > MAX_STICKER_PX:
                report["oversize"].append("%s (%dx%d)" % (os.path.basename(fp), w, h))
                ok = False
            if mode not in ("RGBA", "LA", "P"):
                report["no_alpha"].append("%s (%s)" % (os.path.basename(fp), mode))
                ok = False
            if ok:
                report["ok"] += 1
        except OSError as e:
            # Google Drive の Resource deadlock avoided もここに入る。
            report["unreadable"].append("%s (%s)" % (os.path.basename(fp), e))
        except Exception as e:
            report["unreadable"].append("%s (%s)" % (os.path.basename(fp), e))

    report["expected_count"] = expected_count
    return report


def row(label, value_id, text):
    if text is None:
        text = "★たまごさんが埋める（未確定）"
    return (
        '<div class="ps-row"><div class="ps-label">%s</div>'
        '<div class="ps-value" id="%s">%s</div>'
        '<button class="ps-copy" onclick="ps_copy(\'%s\',this)">コピー</button></div>'
    ) % (mcp.esc(label), value_id, mcp.esc(text), value_id)


STYLE = """
<style>
  .ps-section{background:#fff;border:1px solid #e2dccd;border-radius:12px;padding:16px 16px 6px;margin:0 0 18px;}
  .ps-section h3{margin:0 0 12px;font-size:0.95rem;color:#3a5f7a;border-bottom:1px solid #e2dccd;padding-bottom:8px;}
  .ps-row{display:flex;align-items:flex-start;gap:10px;margin:0 0 12px;flex-wrap:wrap;}
  .ps-label{flex:0 0 100%;font-size:0.78rem;color:#7a7568;margin-bottom:2px;}
  .ps-value{flex:1 1 auto;background:#f4efe4;border:1px solid #e2dccd;border-radius:8px;
    padding:9px 11px;font-size:0.92rem;word-break:break-word;user-select:all;-webkit-user-select:all;min-width:0;}
  .ps-copy{flex:0 0 auto;background:#3a5f7a;color:#fff;border:none;border-radius:8px;
    padding:9px 14px;font-size:0.82rem;font-weight:700;cursor:pointer;white-space:nowrap;}
  .ps-copy.copied{background:#3a7a52;}
  .ps-plain{font-size:0.88rem;color:#2a2a2a;background:#f4efe4;border:1px solid #e2dccd;
    border-radius:8px;padding:9px 11px;margin:0 0 10px;}
  .ps-hint{font-size:0.78rem;color:#7a7568;margin:0 0 10px;}
  .ps-warn{background:#c4483a;color:#fff;border-radius:10px;padding:14px 16px;font-weight:700;
    font-size:1.02rem;margin:0 0 18px;text-align:center;}
</style>
"""

SCRIPT = """
<script>
function ps_copy(id, btn){
  var el = document.getElementById(id);
  if(!el) return;
  var text = el.innerText || el.textContent || "";
  function done(){
    var orig = btn.textContent;
    btn.textContent = "コピーしました";
    btn.classList.add("copied");
    setTimeout(function(){ btn.textContent = orig; btn.classList.remove("copied"); }, 1600);
  }
  function fallback(){
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand("copy"); } catch(e) {}
    document.body.removeChild(ta);
    done();
  }
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done).catch(fallback);
  } else {
    fallback();
  }
}
</script>
"""


def build_sheet_html(cfg, img_report):
    slug = cfg["slug"]
    parts = [STYLE]
    parts.append('<div class="ps-warn">⚠️ Requestは押さない。押すのはたまごさん本人が決めた時だけ。</div>')
    stamp_id = cfg.get("stamp_id") or "未取得（LINE Creators Marketで新規作成した時に決まる）"
    parts.append(
        '<div class="ps-hint">スタンプID: %s／管理画面はご自身のブックマークか履歴から開いてください'
        '（アカウント固有のURLはこのページには書きません）。下から順番どおりに貼れば審査直前まで進みます。</div>'
        % mcp.esc(stamp_id)
    )

    parts.append('<div class="ps-section"><h3>① Display Information（表示情報）</h3>')
    parts.append(row("タイトル（英語）", "f-title-en", cfg.get("title_en")))
    parts.append(row("タイトル（日本語）", "f-title-ja", cfg.get("title_ja")))
    parts.append(row("説明文（英語）", "f-desc-en", cfg.get("desc_en")))
    parts.append(row("説明文（日本語）", "f-desc-ja", cfg.get("desc_ja")))
    parts.append(row("クリエイター名（英語）", "f-creator-en", cfg.get("creator_en")))
    parts.append(row("クリエイター名（日本語）", "f-creator-ja", cfg.get("creator_ja")))
    parts.append(row("コピーライト表記", "f-copyright", cfg.get("copyright")))
    parts.append(row("補足説明欄（AI利用の申告文）", "f-ai-note", cfg.get("ai_note")))
    parts.append(
        '<div class="ps-plain"><b>選択項目（コピー不要、選ぶだけ）</b><br>'
        "AI使用：あり／オリジナルキャラクター：はい／第三者の著作物：含まない／実写・写真：含まない</div>"
    )
    cat_s = cfg.get("category_style") or "★未確定"
    cat_c = cfg.get("category_character") or "★未確定"
    parts.append(
        '<div class="ps-plain"><b>カテゴリ</b><br>Style ＝ %s　／　Character ＝ %s</div>'
        % (mcp.esc(cat_s), mcp.esc(cat_c))
    )
    parts.append("</div>")

    parts.append('<div class="ps-section"><h3>② Sticker Images（画像検品結果）</h3>')
    if img_report.get("error"):
        parts.append('<div class="ps-plain">%s</div>' % mcp.esc(img_report["error"]))
    else:
        found = img_report.get("files_found", 0)
        ok = img_report.get("ok", 0)
        unreadable = img_report.get("unreadable") or []
        oversize = img_report.get("oversize") or []
        no_alpha = img_report.get("no_alpha") or []
        zi = img_report.get("zip_info")
        lines = ["検出%d枚／規格OK %d枚" % (found, ok)]
        if zi:
            if zi.get("readable"):
                lines.append("ZIP内%d件を検出（%s…）" % (
                    zi.get("entry_count", 0), "、".join(zi.get("entries_sample") or [])))
            else:
                lines.append(
                    "ZIPファイルはDrive上に存在する（%sバイト）が、まだクラウドから"
                    "ダウンロードされておらず中身を読めなかった（%s）。"
                    "時間を置いて再実行すれば読める見込み"
                    % (zi.get("size_bytes") or "?", zi.get("error") or "不明なエラー")
                )
        if unreadable:
            lines.append(
                "未確認%d枚（Googleドライブが未ダウンロードのため読めなかった。"
                "時間を置いて再実行すれば読める見込み）" % len(unreadable)
            )
        if oversize:
            lines.append("サイズ超過%d枚: %s" % (len(oversize), ", ".join(oversize[:5])))
        if no_alpha:
            lines.append("透過なし%d枚: %s" % (len(no_alpha), ", ".join(no_alpha[:5])))
        parts.append('<div class="ps-plain">%s</div>' % "<br>".join(mcp.esc(x) for x in lines))
    parts.append("</div>")

    parts.append('<div class="ps-section"><h3>③ Preview（見るだけ・触らない）</h3>')
    parts.append(
        '<div class="ps-plain">実際の見え方を確認する画面。貼る文字は無い。'
        "余白や並び順に違和感が無いかだけ目視する。</div>"
    )
    parts.append("</div>")

    parts.append('<div class="ps-section"><h3>④ Sales Information（販売設定）</h3>')
    parts.append('<div class="ps-plain">%s</div>' % mcp.esc(cfg.get("sales_settings") or "★未確定"))
    parts.append("</div>")

    parts.append(
        '<div class="note" style="border-color:#c4483a;">'
        "触らないもの：古い下書き「miketama」（ID %s）。削除・編集・上書きしない。"
        "</div>" % mcp.esc(cfg.get("old_draft_id_do_not_touch") or "28343285")
    )
    parts.append(
        '<div class="ps-warn" style="margin-top:24px;">⚠️ ここまで貼り終えても、Requestはまだ押さない。'
        "押すのは本人が決めた時だけ。</div>"
    )
    parts.append(SCRIPT)
    return "\n".join(parts)


def process_one(cfg, force=False, state=None):
    slug = cfg["slug"]
    img_dir = find_image_dir(cfg)
    img_report = inspect_images(img_dir, cfg.get("expected_image_count"))

    what_html = build_sheet_html(cfg, img_report)

    nums = [
        {"value": "%d枚" % img_report.get("files_found", 0), "label": "検出した画像ファイル数"},
        {"value": "%d枚" % img_report.get("ok", 0), "label": "規格OK（370px以内・透過あり）"},
        {"value": cfg.get("price") or "未確定", "label": "販売価格"},
    ]
    links = [
        {"label": "LINE Creators Market（トップ。ここから自分のブックマークで管理画面へ）",
         "url": "https://creator.line.me/ja/"},
    ]
    missing_text = []
    for key, label in (
        ("title_ja", "タイトル(日本語)"), ("desc_ja", "説明文(日本語)"),
        ("title_en", "タイトル(英語)"), ("desc_en", "説明文(英語)"),
    ):
        if not cfg.get(key):
            missing_text.append(label)
    table = [
        {"item": "文言(タイトル・説明文)",
         "result": ("未確定: " + "、".join(missing_text)) if missing_text else "確定済み・貼るだけの状態",
         "ok": not missing_text},
        {"item": "画像フォルダ", "result": img_dir or "見つからない（Drive上に該当フォルダなし）",
         "ok": bool(img_dir)},
        {"item": "画像検品", "result": (
            "検出%d枚・規格OK%d枚・未確認%d枚" % (
                img_report.get("files_found", 0), img_report.get("ok", 0),
                len(img_report.get("unreadable") or []))
            if img_report.get("files_found", 0) > 0
            else (
                "ZIP内%d件を確認" % img_report["zip_info"].get("entry_count", 0)
                if img_report.get("zip_info") and img_report["zip_info"].get("readable")
                else "ZIPはDrive上に存在するが未ダウンロードで中身未確認（時間を置いて再実行）"
                if img_report.get("zip_info")
                else "画像・ZIPともに検出できず"
            )
        ), "ok": (
            img_report.get("files_found", 0) > 0
            or bool(img_report.get("zip_info") and img_report["zip_info"].get("readable"))
        )},
        {"item": "審査リクエスト", "result": "押していません（押すのは本人のみ）", "ok": False},
    ]

    cfg_cfg = {
        "n": TASK_N,
        "slug": "%s-paste-sheet" % slug,
        "title": "LINEスタンプ「%s」貼るだけ申請シート（申請機・自動生成）" % (cfg.get("title_ja") or slug),
        "date_line": time.strftime("%Y-%m-%d") + " tools/line_stamp_pipeline.py が自動生成・機械検品済み",
        "what": what_html,
        "nums": nums,
        "links": links,
        "table": table,
        "allow_no_screenshot": (
            "LINE Creators Marketの画面を自動操作するものではなく(ToS上の自動化禁止のため)、"
            "コピペ用の文言シートそのものが成果物。管理画面はアカウント固有のためスクショに個人情報が写る"
        ),
        "footer": (
            "このページはLINE Creators Marketの画面を自動操作するものではない（creator.line.meは"
            "ブラウザ自動化を安全上の理由で禁止しているため）。ここに用意した文言と検品結果を"
            "たまごさんが自分の手でコピー＆貼り付けするための補助資料。"
            "tools/line_stamp_configs/%s.json を書き換えるだけで内容が更新される。"
        ) % slug,
    }

    out_path = os.path.join(CHECK_DIR, "%s-%s.html" % (cfg_cfg["n"], cfg_cfg["slug"]))
    html_out = mcp.render(cfg_cfg)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    url = "%s%s-%s.html" % (PAGES_BASE, cfg_cfg["n"], cfg_cfg["slug"])
    return {"slug": slug, "out_path": out_path, "url": url, "img_report": img_report,
            "missing_text": missing_text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--slug", help="このキャラだけ処理する（省略時は全キャラ）")
    args = ap.parse_args()

    configs = list_configs()
    if args.slug:
        configs = [c for c in configs if c.get("slug") == args.slug]

    state = load_json(STATE_PATH, {"folders_seen": [], "sheets": {}})
    drive_folders = scan_drive_folders()
    new_folders = []
    if isinstance(drive_folders, list):
        prev = set(state.get("folders_seen", []))
        new_folders = [f for f in drive_folders if f not in prev]
        state["folders_seen"] = drive_folders
    else:
        state["drive_scan_error"] = drive_folders.get("__error__")

    results = []
    for cfg in configs:
        r = process_one(cfg, state=state)
        results.append(r)
        state.setdefault("sheets", {})[r["slug"]] = {
            "url": r["url"],
            "updatedAt": now_jst_str(),
            "filesFound": r["img_report"].get("files_found", 0),
            "missingText": r["missing_text"],
        }

    save_json(STATE_PATH, state)

    print(json.dumps({"newFolders": new_folders, "results": [
        {"slug": r["slug"], "url": r["url"], "filesFound": r["img_report"].get("files_found", 0),
         "missingText": r["missing_text"]} for r in results
    ]}, ensure_ascii=False, indent=1))

    # 新規フォルダ検知 or 未確定文言があるキャラは、進捗表へ1行通知。
    notes = []
    for f in new_folders:
        notes.append("Driveに新しいスタンプフォルダ「%s」が増えました" % f)
    for r in results:
        if r["missing_text"]:
            notes.append(
                "%s：文言が未確定（%s）。tools/line_stamp_configs/%s.jsonを埋めれば次回自動反映"
                % (r["slug"], "、".join(r["missing_text"]), r["slug"])
            )
    if notes:
        append_jsonl(OUTBOX, {
            "ts": now_jst_str(), "n": TASK_N,
            "title": "LINEスタンプ申請機（769番）の日次見回り",
            "ok": True, "elapsedMin": 0,
            "urls": [r["url"] for r in results],
            "result": " / ".join(notes),
        })

    if args.push:
        _push()
    return 0


def _push(paths=(
    "share/check", "status/line_stamp_pipeline_state.json",
    "status/dispatch_outbox.jsonl", "tools/line_stamp_configs",
    "tools/line_stamp_pipeline.py",
), retries=5, wait_sec=6):
    import subprocess
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(["git", "add"] + list(paths), cwd=REPO, check=False,
                            capture_output=True, text=True, timeout=30)
            diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO)
            if diff.returncode == 0:
                print("変更なし・pushスキップ")
                return
            subprocess.run(
                ["git", "commit", "-m", "769番: LINEスタンプ申請機の自動更新"],
                cwd=REPO, check=False, capture_output=True, text=True, timeout=30,
            )
            p = subprocess.run(["git", "push", "origin", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, timeout=60)
            if p.returncode == 0:
                print("push成功")
                return
            print("push失敗(試行%d): %s" % (attempt, (p.stderr or "")[:200]))
        except Exception as e:
            print("push例外(試行%d): %s" % (attempt, e))
        time.sleep(wait_sec)
    print("push最終的に失敗")


if __name__ == "__main__":
    sys.exit(main())
