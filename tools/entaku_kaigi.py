#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/entaku_kaigi.py ── 円卓会議：URL／Obsidianノートを受け取り、議事録を作って
完成/に保存し、必要ならObsidian Vaultへも格納する。

34588号【判定日赤】「URLを1つ受け取り、円卓会議の議事録を作って 完成/ に保存し、
そのパスを返す。」への対応が土台。

34813号【判定日赤】「自分の理想としてはオブシディアンに書いてあるノートだったり、
これを円卓にかけてだったり、外部ユーチューブやツイッターから拾ってきたネタをこれ
円卓にかけて作って、多角的にいろんな顧問がああだこうであって、最後オブシディアンに
格納するっていうところまで行きたい」（2026-08-07に言われて以降、1ヶ月以上未着手
だった案件）への対応で、34588の土台に次の2点を追加した：
  A) 入力をURLだけでなく「Obsidianノート」「URL＋Obsidianノートの組み合わせ」にも
     対応（--vault-note）。YouTube/Xのネタは本文がJS依存で取れないため、既存の
     tools/nagekomi.py の oEmbed経路（nk.kind_of / nk.enrich）をそのまま流用する
     （★オリジナル禁止：新しいoEmbed実装を書かない）。
  B) 議事録を 完成/ に保存するだけでなく、--to-vault を付けた時は Obsidian Vault
     （AI出力/40_プロジェクト/円卓会議🔥/）へも新規ノートとして格納する
     （既存ノートの上書き・削除は一切しない。新規作成のみ）。
     Vaultの読み取りは既存の tools/vault_yomu.py（読むだけ・安全境界あり）をそのまま
     import して使う（★オリジナル禁止：読み取りの安全チェックを再発明しない）。

やること（この1本で完結）：
  1. 渡されたURL／Obsidianノートの本文を取得する。
     - 通常のWebページ：HTMLタグを除いた地の文・タイトル
     - YouTube/X：nagekomi.enrich() のoEmbed結果（題名・投稿者・本文抜粋）
     - Obsidianノート：vault_yomu.run_job({"op":"read",...}) でそのまま読む
     URLとObsidianノートを両方渡した場合は、両方の本文を1つの議事録にまとめて扱う
     （＝「ノート＋外部ネタ」を同じ円卓にかけるという34813号の要望そのもの）。
  2. 4つの立場（楽観派／懐疑派／現場目線／まとめ役＝鬼監督）で円卓会議を1回のAI呼び出しで
     シミュレートし、議事録（Markdown）を作る。
     ★オリジナル禁止：外部AI呼び出しの経路（鍵の探し方・候補モデル・フォールバック順
     Grok→OpenAI→Gemini）は既存の tools/gaibu_kenpin.py と同じものを流用する
     （鍵探索は gaibu_kenpin._find_env_key をそのまま import して使う）。
     違いは「OK/NG判定のJSON」ではなく「自由記述の議事録テキスト」を取る点だけ。
  3. 完成/ フォルダへ <日時>-<slug>.md と同内容の .html（ブラウザで開ける版）を保存し、
     保存した .md のパスを `ENTAKU_RESULT: <path>` の形で1行返す
     （他の道具のVERDICT行と同じ、パースしやすい形）。
  4. --to-vault を付けた時は、同じ議事録をObsidian Vaultの
     AI出力/40_プロジェクト/円卓会議🔥/<日時>-<slug>.md へ新規ノートとして保存し、
     `ENTAKU_VAULT: <Vault内の相対パス>` を1行返す。

使い方：
    python3 tools/entaku_kaigi.py --url <対象URL> [--theme "円卓にかける問い"] [--slug <ファイル名用の短い英語名>]
    python3 tools/entaku_kaigi.py --vault-note "<Vault内の相対パス.md>" [--to-vault]
    python3 tools/entaku_kaigi.py --vault-note "<ノート>" --url <YouTube/X/WebのURL> --to-vault

費用：外部AI呼び出し1回のみ（gpt-4o-mini／gemini-3.8-flash系の安価モデル。
入力2000〜3000トークン・出力800〜1200トークン程度なら1回あたり1円未満。
既存の検品ゲート(gaibu_kenpin)の日次上限・台帳とは別に、本ツール専用の
status/entaku_kaigi_ledger.json へ実測トークン数で記録する。1日20回を超えたら
新規呼び出しを止める（お金を無限に使わない安全弁）。
"""
from __future__ import annotations

import argparse
import datetime
import html as html_mod
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kenpin as gk  # ★鍵探索・モデル候補・フォールバック順を流用（オリジナル禁止への対応）
import nagekomi as nk      # ★YouTube/XのoEmbed取得を流用（オリジナル禁止への対応）
import vault_yomu as vy    # ★Obsidian Vaultの安全な読み取りを流用（オリジナル禁止への対応）

KANSEI_DIR = os.path.join(REPO, "完成")
LEDGER_PATH = os.path.join(REPO, "status", "entaku_kaigi_ledger.json")
DAILY_CALL_CAP = 20

# 34813号：Vaultへ格納する時の置き場所（既存ノートには一切触れない・新規作成のみ）
VAULT_ROOT = vy.VAULT
VAULT_OUTPUT_DIR_REL = os.path.join("AI出力", "40_プロジェクト", "円卓会議🔥")

JST = datetime.timezone(datetime.timedelta(hours=9))

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG_ANY = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)

SYSTEM_PROMPT = (
    "あなたは『ごきげん補給所』の運営チームの円卓会議を演じる書記です。"
    "与えられたURLの本文について、4つの立場（楽観派・懐疑派・現場目線・まとめ役=鬼監督）で"
    "議論させ、議事録をMarkdownだけで出力してください。説明文やコードブロックの囲みは付けず、"
    "本文（Markdown）だけを返してください。事実として確認できていないことは「裏取りできず」と"
    "明記し、断定しないでください。"
)


def now():
    return datetime.datetime.now(JST)


# ───────────────────────────────────────── ① URLの本文取得

def fetch_text(url, limit=5000, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "entaku-kaigi/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(800000).decode("utf-8", "replace")
    tm = _TITLE.search(raw)
    title = re.sub(r"\s+", " ", html_mod.unescape(tm.group(1))).strip() if tm else url
    body = _TAG.sub(" ", raw)
    body = _TAG_ANY.sub(" ", body)
    body = html_mod.unescape(body)
    body = re.sub(r"\s+", " ", body).strip()
    return title, body[:limit]


# ───────────────────────────────────────── ② 円卓会議（外部AI・自由記述）

def _build_prompt(source_lines, title, body, theme):
    q = theme or "この内容を踏まえて、ごきげん補給所が採るべき次の一手は何か"
    src_block = "\n".join("- %s" % s for s in source_lines) or "- (出典なし)"
    return (
        "【出典】\n%s\n【タイトル】%s\n【本文抜粋】\n%s\n\n"
        "【円卓にかける問い】%s\n\n"
        "この形式のMarkdownで出力してください：\n"
        "# 円卓会議議事録\n\n"
        "## 出典\n%s\n- 取得日時: %s\n\n"
        "## 論点（3〜5点）\n- ...\n\n"
        "## 各立場の発言\n### 楽観派\n...\n### 懐疑派\n...\n### 現場目線\n...\n\n"
        "## まとめ役（鬼監督）の結論\n（対立する意見を踏まえた1つの決定。弱点も明記する）\n\n"
        "## 次の一手\n（具体的に1つだけ）\n"
    ) % (src_block, title, body, q, src_block, now().strftime("%Y-%m-%d %H:%M JST"))


def _load_ledger():
    try:
        with io.open(LEDGER_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"records": []}


def _save_ledger(ledger):
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with io.open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


def _today_count(ledger):
    today = now().strftime("%Y-%m-%d")
    return sum(1 for r in ledger.get("records", []) if (r.get("at") or "").startswith(today))


def _record(provider, model, usage, note=""):
    ledger = _load_ledger()
    ledger.setdefault("records", []).append({
        "at": now().strftime("%Y-%m-%d %H:%M:%S"),
        "provider": provider, "model": model, "usage": usage, "note": note,
    })
    _save_ledger(ledger)


def _call_openai_compatible_text(provider, api_url, model_candidates, key_names, prompt, api_key=None):
    """gaibu_kenpin._call_openai_compatible_judge と同じ経路だが、JSON検証ではなく
    自由記述テキストをそのまま受け取る（戻り値: (text, model_used, usage, err)）。"""
    api_key = api_key or gk._find_env_key(key_names)
    if not api_key:
        return None, "", None, "%sの鍵(%s)が見つかりません" % (provider, "/".join(key_names))
    body_base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    err_list = []
    for model in model_candidates:
        body = dict(body_base)
        body["model"] = model
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = j.get("usage") or {}
            if content.strip():
                return content, model, usage, ""
            err_list.append("%s: 空の応答" % model)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append("%s: HTTP %s %s" % (model, e.code, err_body[:150]))
            continue
        except Exception as e:
            err_list.append("%s: %s" % (model, e))
            continue
    return None, "", None, "%s：全モデル候補で失敗（%s）" % (provider, " / ".join(err_list))


def _call_gemini_text(prompt, api_key=None):
    api_key = api_key or gk._find_env_key(("GEMINI_API_KEY",))
    if not api_key:
        return None, "", None, "Geminiの鍵(GEMINI_API_KEY)が見つかりません"
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    err_list = []
    for model in gk.GEMINI_MODEL_CANDIDATES:
        api_url = gk.GEMINI_URL_TMPL % (model, api_key)
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            cand = (j.get("candidates") or [{}])[0]
            content = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            usage = j.get("usageMetadata") or {}
            if content.strip():
                return content, model, usage, ""
            err_list.append("%s: 空の応答" % model)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append("%s: HTTP %s %s" % (model, e.code, err_body[:150]))
            continue
        except Exception as e:
            err_list.append("%s: %s" % (model, e))
            continue
    return None, "", None, "Gemini：全モデル候補で失敗（%s）" % " / ".join(err_list)


PROVIDER_CHAIN_TEXT = [
    ("Grok", lambda prompt: _call_openai_compatible_text(
        "Grok", gk.XAI_URL, gk.GROK_MODEL_CANDIDATES, ("XAI_API_KEY",), prompt)),
    ("OpenAI", lambda prompt: _call_openai_compatible_text(
        "OpenAI", gk.OPENAI_URL, gk.OPENAI_MODEL_CANDIDATES, ("OPENAI_API_KEY",), prompt)),
    ("Gemini", lambda prompt: _call_gemini_text(prompt)),
]


def run_roundtable(source_lines, title, body, theme):
    """戻り値: (markdown_text, provider_used, err)"""
    ledger = _load_ledger()
    if _today_count(ledger) >= DAILY_CALL_CAP:
        return None, "", "本日の呼び出し上限(%d回)に到達。安全のため停止" % DAILY_CALL_CAP
    prompt = _build_prompt(source_lines, title, body, theme)
    tried = []
    for provider, fn in PROVIDER_CHAIN_TEXT:
        content, model, usage, err = fn(prompt)
        if content:
            _record(provider, model, usage, note="34588号・entaku_kaigi")
            return content, provider, ""
        tried.append("%s(%s)" % (provider, err))
    return None, "", "全プロバイダ失敗：%s" % " / ".join(tried)


# ───────────────────────────────────────── ③ 保存

def _slug_from(theme, url):
    base = re.sub(r"[^0-9A-Za-z]+", "-", (theme or url or "entaku")).strip("-").lower()
    return (base[:40] or "entaku")


def _source_line_html(s):
    if s.startswith("http://") or s.startswith("https://"):
        return "<p>出典: <a href=\"%s\">%s</a></p>" % (html_mod.escape(s), html_mod.escape(s))
    return "<p>出典: %s</p>" % html_mod.escape(s)


def to_html(markdown_text, title, source_lines):
    # ★markdownパーサは使わず（新規依存を増やさない＝オリジナル禁止）、
    #   <pre>でそのまま見せる最小のビュワー。中身の地の文は oni_modoshi の
    #   「中身が空でない」チェック（タグを剥いた地の文の文字数）にそのまま通る。
    esc = html_mod.escape(markdown_text)
    src_html = "".join(_source_line_html(s) for s in source_lines) or "<p>出典: (なし)</p>"
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>円卓会議議事録 - %s</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",sans-serif;"
        "max-width:760px;margin:24px auto;padding:0 16px;line-height:1.8;color:#222}"
        "pre{white-space:pre-wrap;word-break:break-word;background:#fafafa;"
        "border:1px solid #eee;border-radius:8px;padding:16px}"
        "a{color:#0a6}</style></head><body>"
        "%s<pre>%s</pre></body></html>"
    ) % (html_mod.escape(title), src_html, esc)


def save(markdown_text, title, slug, source_lines):
    os.makedirs(KANSEI_DIR, exist_ok=True)
    stamp = now().strftime("%Y%m%d-%H%M%S")
    base = "%s-%s" % (stamp, slug)
    md_path = os.path.join(KANSEI_DIR, base + ".md")
    html_path = os.path.join(KANSEI_DIR, base + ".html")
    with io.open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text if markdown_text.endswith("\n") else markdown_text + "\n")
    with io.open(html_path, "w", encoding="utf-8") as f:
        f.write(to_html(markdown_text, title, source_lines))
    return md_path, html_path


# ───────────────────────────────────────── ④ Obsidian Vaultとのやり取り（34813号）

def read_vault_note(rel_path):
    """既存の vault_yomu.py（読むだけ・安全境界あり）を流用して読む。
    戻り値: (title, body, err)"""
    res = vy.run_job({"op": "read", "path": rel_path})
    if not res.get("ok"):
        return "", "", res.get("error") or "Vaultノートの読み取りに失敗"
    text = res.get("text") or ""
    title = os.path.splitext(os.path.basename(rel_path))[0]
    return title, text, ""


def fetch_text_smart(url):
    """YouTube/Xは本文がJS依存のため nagekomi.enrich() のoEmbed結果を使う。
    それ以外の通常のWebページは既存の fetch_text() を使う。
    戻り値: (title, body)"""
    kind = nk.kind_of(url)
    if kind in ("youtube", "x"):
        meta, why = nk.enrich(url)
        title = meta.get("title") or url
        parts = []
        if meta.get("channel"):
            parts.append("投稿者/チャンネル: %s" % meta["channel"])
        if meta.get("duration"):
            parts.append("長さ: %s" % meta["duration"])
        if meta.get("publishedAt"):
            parts.append("公開日: %s" % meta["publishedAt"])
        if meta.get("title"):
            parts.append("題名/本文: %s" % meta["title"])
        if why:
            parts.append("(取得できなかった分: %s)" % why)
        body = "\n".join(parts) or ("取得できず: %s" % why)
        return title, body
    return fetch_text(url)


def write_to_vault(slug, markdown_text, source_lines):
    """議事録をObsidian Vaultへ新規ノートとして格納する。既存ノートには一切触れない。
    戻り値: (Vault内の相対パス, err)"""
    if not os.path.isdir(VAULT_ROOT):
        return "", "Vaultが見つかりません: %s" % VAULT_ROOT
    out_dir = os.path.join(VAULT_ROOT, VAULT_OUTPUT_DIR_REL)
    os.makedirs(out_dir, exist_ok=True)
    stamp = now().strftime("%Y%m%d-%H%M%S")
    fname = "%s-%s-円卓会議.md" % (stamp, slug)
    path = os.path.join(out_dir, fname)
    if os.path.exists(path):
        return "", "同名ファイルが既に存在（上書きしない）: %s" % fname
    front = (
        "---\n生成元: tools/entaku_kaigi.py（34813号）\n生成日時: %s\n出典:\n%s\n---\n\n"
        % (now().strftime("%Y-%m-%d %H:%M JST"),
           "\n".join("  - %s" % s for s in source_lines) or "  - (なし)")
    )
    body = markdown_text if markdown_text.endswith("\n") else markdown_text + "\n"
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(front + body)
    return os.path.join(VAULT_OUTPUT_DIR_REL, fname), ""


# ───────────────────────────────────────── 本体

def main():
    ap = argparse.ArgumentParser(
        description="URL／Obsidianノートを受け取り、円卓会議の議事録を作って完成/（・任意でVault）へ保存する")
    ap.add_argument("--url", default=None, help="対象URL（Web／YouTube／X）。--vault-noteと併用可")
    ap.add_argument("--vault-note", default=None,
                     help="Obsidian Vault内のノート相対パス（例: 'AI出力/仕入れ/xxx.md'）。--urlと併用可")
    ap.add_argument("--theme", default=None, help="円卓にかける問い（省略時は既定の問いを使う）")
    ap.add_argument("--slug", default=None, help="ファイル名用の短い英語名（省略時は自動生成）")
    ap.add_argument("--to-vault", action="store_true",
                     help="34813号：生成した議事録をObsidian VaultのAI出力/40_プロジェクト/円卓会議🔥/へ"
                          "新規ノートとして格納する（既存ノートは一切上書きしない）")
    ap.add_argument("--content-file", default=None,
                     help="外部AIを呼ばず、このファイルの中身（Markdown）をそのまま議事録として使う。"
                          "外部AI（Grok/OpenAI/Gemini）が全社とも残高切れ・上限超過の時の退避口。"
                          "呼び出し側（Claude Codeセッション等）が実際に取得した本文を基に自分で"
                          "議事録を書いた場合に使う（＝生成の手段が変わるだけで、保存・公開の形は同じ）")
    args = ap.parse_args()

    if not (args.url or args.vault_note or args.content_file):
        print("ENTAKU_ERROR: --url / --vault-note / --content-file のいずれか1つ以上が必要です")
        return 1

    source_lines = []
    title_parts = []
    body_parts = []

    if args.vault_note:
        t, b, err = read_vault_note(args.vault_note)
        if err:
            print("ENTAKU_ERROR: Obsidianノートの取得に失敗：%s" % err)
            return 1
        title_parts.append(t)
        body_parts.append(b[:4000])
        source_lines.append("Obsidianノート: %s" % args.vault_note)

    if args.url:
        try:
            t, b = fetch_text_smart(args.url)
        except Exception as e:
            print("ENTAKU_ERROR: URL取得に失敗：%s" % e)
            return 1
        title_parts.append(t)
        body_parts.append(b)
        source_lines.append(args.url)

    title = " / ".join(p for p in title_parts if p) or (args.theme or "円卓会議")
    body = "\n\n---\n\n".join(p for p in body_parts if p)

    provider = "content-file"
    if args.content_file:
        try:
            with io.open(args.content_file, encoding="utf-8") as f:
                markdown_text = f.read()
        except Exception as e:
            print("ENTAKU_ERROR: --content-fileの読み込みに失敗：%s" % e)
            return 1
        if len(markdown_text.strip()) < 200:
            print("ENTAKU_ERROR: --content-fileの中身が短すぎる（%d文字）" % len(markdown_text.strip()))
            return 1
        if not source_lines:
            source_lines.append("content-file: %s" % args.content_file)
    else:
        if len(body) < 50:
            print("ENTAKU_ERROR: 本文が短すぎる取得結果（%d文字）。URL/ノートを確認してください" % len(body))
            return 1
        markdown_text, provider, err = run_roundtable(source_lines, title, body, args.theme)
        if not markdown_text:
            print("ENTAKU_ERROR: 円卓会議の生成に失敗：%s" % err)
            return 1

    slug = args.slug or _slug_from(args.theme, args.vault_note or args.url)
    md_path, html_path = save(markdown_text, title, slug, source_lines)
    rel_md = os.path.relpath(md_path, REPO)
    rel_html = os.path.relpath(html_path, REPO)
    print("ENTAKU_RESULT: %s" % rel_md)
    print("ENTAKU_HTML: %s" % rel_html)
    print("ENTAKU_PROVIDER: %s" % provider)

    if args.to_vault:
        vault_rel, err = write_to_vault(slug, markdown_text, source_lines)
        if err:
            print("ENTAKU_VAULT_ERROR: %s" % err)
        else:
            print("ENTAKU_VAULT: %s" % vault_rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
