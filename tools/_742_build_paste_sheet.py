#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
742番：LINEスタンプ「鬼嫁ちゃん」を審査直前まで進めるための、貼るだけ申請補助シート。
tools/make_check_page.py の render() をそのまま使い、①の中に画面順(Display Information →
Sticker Images → Preview → Sales Information → 最終確認)の全項目をコピーボタン付きで並べる。

出力: share/check/742-oniyome-chan-paste-sheet.html
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import make_check_page as m  # noqa: E402

WARN_TOP = (
    '<div style="background:#c4483a;color:#fff;border-radius:10px;'
    'padding:14px 16px;font-weight:700;font-size:1.02rem;margin:0 0 18px;text-align:center;">'
    "⚠️ Requestは押さない。押すのはたまごさん本人が決めた時だけ。"
    "</div>"
)
WARN_BOTTOM = (
    '<div style="background:#c4483a;color:#fff;border-radius:10px;'
    'padding:14px 16px;font-weight:700;font-size:1.02rem;margin:30px 0 10px;text-align:center;">'
    "⚠️ ここまで貼り終えても、Requestはまだ押さない。押すのは本人が決めた時だけ。"
    "</div>"
)
NOTE_DONTTOUCH = (
    '<div class="note" style="border-color:#c4483a;">'
    "触らないもの：古い下書き「miketama」（ID 28343285）。削除・編集・上書きしない。"
    "</div>"
)

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


def row(label, value_id, text):
    return (
        '<div class="ps-row"><div class="ps-label">%s</div>'
        '<div class="ps-value" id="%s">%s</div>'
        '<button class="ps-copy" onclick="ps_copy(\'%s\',this)">コピー</button></div>'
    ) % (m.esc(label), value_id, m.esc(text), value_id)


def build_what():
    parts = [STYLE, WARN_TOP]

    parts.append(
        '<div class="ps-hint">スタンプID: 47328304／管理画面はご自身のブックマークか履歴から開いてください'
        "（アカウント固有のURLはこのページには書きません）。下から順番どおりに貼れば審査直前まで進みます。</div>"
    )

    # 画面1: Display Information
    parts.append('<div class="ps-section"><h3>① Display Information（表示情報）</h3>')
    parts.append(
        '<div class="ps-hint">タイトルは英日とも変更後の文言。元の「鬼嫁ちゃん」単体は重複エラーになるため'
        "戻さないこと。</div>"
    )
    parts.append(row("タイトル（英語）", "f-title-en", "Oniyome-chan"))
    parts.append(row("タイトル（日本語）", "f-title-ja", "鬼嫁ちゃん｜関西弁スタンプ"))
    parts.append(
        row(
            "説明文（英語）",
            "f-desc-en",
            "A kind but slightly fierce Kansai-dialect wife and her little cat, "
            "perfect for everyday chats with family and partners.",
        )
    )
    parts.append(
        row(
            "説明文（日本語）",
            "f-desc-ja",
            "やさしいけど、ちょっぴり鬼っぽい「鬼嫁ちゃん」と小さな猫。夫婦や家族の日常会話で使いやすい関西弁スタンプです。",
        )
    )
    parts.append(row("クリエイター名（英語）", "f-creator-en", "miketamawae"))
    parts.append(row("クリエイター名（日本語）", "f-creator-ja", "ミケタマワエ"))
    parts.append(row("コピーライト表記", "f-copyright", "© 2026 miketamawae"))
    parts.append(
        row(
            "補足説明欄（AI利用の申告文）",
            "f-ai-note",
            "Original characters. AI-assisted artwork. No third-party copyrighted characters, "
            "trademarks, or licensed material are used.",
        )
    )
    parts.append(
        '<div class="ps-plain"><b>選択項目（コピー不要、選ぶだけ）</b><br>'
        "AI使用：あり／オリジナルキャラクター：はい／第三者の著作物：含まない／実写・写真：含まない</div>"
    )
    parts.append(
        '<div class="ps-plain"><b>カテゴリ</b><br>'
        "Style ＝ Dialects &amp; Slang　／　Character ＝ Families &amp; Couples</div>"
    )
    parts.append("</div>")

    # 画面2: Sticker Images
    parts.append('<div class="ps-section"><h3>② Sticker Images（見るだけ・触らない）</h3>')
    parts.append(
        '<div class="ps-plain">メイン画像 240×240／タブ画像 96×74／スタンプ01〜24 各370×320。'
        "全て透過PNG・計26枚。機械検品済みで不備0件、<b>登録済みなので再アップロードしない</b>。"
        "この画面では並びとサイズを見るだけでよい。</div>"
    )
    parts.append("</div>")

    # 画面3: Preview
    parts.append('<div class="ps-section"><h3>③ Preview（見るだけ・触らない）</h3>')
    parts.append(
        '<div class="ps-plain">実際の見え方を確認する画面。貼る文字は無い。'
        "余白や並び順に違和感が無いかだけ目視する。</div>"
    )
    parts.append("</div>")

    # 画面4: Sales Information
    parts.append('<div class="ps-section"><h3>④ Sales Information（販売設定）</h3>')
    parts.append(
        '<div class="ps-plain">'
        "LINE STOREでの表示：オン／販売地域：全地域／価格：¥190〜／"
        "Premiumスタンプ：参加する／販売開始：<b>手動</b>（自分でタイミングを選ぶ）／"
        "Arranging：参加する／Trial：参加する／Collaboration：参加しない／"
        "Special Collection：全て「Not interested」"
        "</div>"
    )
    parts.append("</div>")

    parts.append(NOTE_DONTTOUCH)
    parts.append(SCRIPT)
    return "\n".join(parts)


def main():
    what_html = build_what()

    nums = [
        {"value": "26枚", "label": "登録済みの画像（メイン・タブ・スタンプ01〜24、透過PNG）"},
        {"value": "¥190〜", "label": "販売価格（Premium参加・手動販売開始）"},
        {"value": "7項目", "label": "最終チェックリスト（下の表）"},
    ]
    links = [
        {"label": "LINE Creators Market（トップ。ここから自分のブックマークで管理画面へ）", "url": "https://creator.line.me/ja/"},
    ]
    table = [
        {"item": "画像24個（スタンプ本体）", "result": "登録済み・確認済み", "ok": True},
        {"item": "メイン画像（240×240）", "result": "登録済み・確認済み", "ok": True},
        {"item": "タブ画像（96×74）", "result": "登録済み・確認済み", "ok": True},
        {"item": "タイトル・説明文（英日）", "result": "文言確定・貼るだけの状態で用意済み", "ok": True},
        {"item": "販売設定（価格・地域・Premium等）", "result": "内容確定・貼るだけの状態で用意済み", "ok": True},
        {"item": "不備チェック（透過・サイズ・線ノイズ）", "result": "機械検品で0件・確認済み", "ok": True},
        {"item": "審査リクエスト", "result": "押していません（押すのは本人のみ）", "ok": False},
    ]

    cfg = {
        "n": 742,
        "slug": "oniyome-chan-paste-sheet",
        "title": "LINEスタンプ「鬼嫁ちゃん」貼るだけ申請シート",
        "date_line": "2026-09-11 実装・main合流・本番(GitHub Pages)反映まで実測確認",
        "what": what_html,
        "nums": nums,
        "links": links,
        "table": table,
        "after_img": "img/742-oniyome-paste-sheet.png",
        "after_label": "本番ページの実際の表示（ヘッドレスChromeで撮影・機械的な証拠）",
        "shots_title": "③ 実際の画面（本番URLをヘッドレスで撮影）",
        "footer": (
            "このページはLINE Creators Marketの画面を自動操作するものではない（creator.line.meは"
            "ブラウザ自動化を安全上の理由で禁止しているため）。ここに用意した文言をたまごさんが"
            "自分の手でコピー＆貼り付けするための補助資料。"
            + WARN_BOTTOM
        ),
    }

    out_path = os.path.join(REPO, "share", "check", "%s-%s.html" % (cfg["n"], cfg["slug"]))
    html_out = m.render(cfg)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print("書きました:", out_path)
    print("想定URL: %s%s-%s.html" % (m.PAGES_BASE, cfg["n"], cfg["slug"]))


if __name__ == "__main__":
    main()
