# わえ（@cosmicwae）自動投稿 — 鍵の取り方（1回だけ・約5分・0円）

配管はもう全部できている。動かないのは **鍵（アクセストークン）が無い1点だけ**。
鍵だけは、アカウントの持ち主にしか作れない（パスワードを打つ必要があるため、こちらでは代行不可）。

やることは5つ。全部Metaの公式画面。**お金は一切かからない。**

---

## 1. Meta開発者登録（無料・既存のFacebookでログインするだけ）
https://developers.facebook.com/ → 右上「スタート」→ 規約に同意 →「その他」を選んで完了。
※新しいアカウントは作らない。今使っているFacebookでそのまま。

## 2. アプリを作る
https://developers.facebook.com/apps/create/
- ユースケース: **「Instagramアカウントの管理」**（無ければ「その他」→「ビジネス」）
- アプリ名: `wae-autopost`
- ビジネスポートフォリオ: **TeamTadanowae** を選ぶ

## 3. Instagramを追加して権限を付ける
左メニュー「Instagram」→「設定」→ **Facebookログインを利用したInstagram API** 側を使う。
必要な権限は4つ：
```
instagram_basic
instagram_content_publish
pages_read_engagement
pages_manage_posts
```
（審査は不要。自分のアカウントなら「スタンダードアクセス」のまま通る）

## 4. トークンを1本もらう
https://developers.facebook.com/tools/explorer/
- 右上のアプリで `wae-autopost` を選ぶ
- 「ユーザーまたはページ」→ **ページアクセストークン → TeamTadanowae**
- 上の4権限にチェック →「アクセストークンを生成」→ 出てきた文字列をコピー
- **長持ちさせる**: https://developers.facebook.com/tools/debug/accesstoken/ に貼って「アクセストークンを延長」
  （ページトークンは延長すると無期限になる）

## 5. 貼る（ダブルクリックするだけ）
このフォルダの **`1_鍵を貼る.command`** をダブルクリック。
4でコピーした文字列を貼って Enter を押すだけ。
アカウントの番号もページの番号も、こちらで自動で調べて保存します。打ち込むものは他に何もありません。

---

## 貼り終わったら（全部ダブルクリック）

| 押すもの | 何が起きるか |
|---|---|
| `2_いま1本出す.command` | 11本の文面が全部出る → 見て y を押すと、その1本が実際にInstagramに出る |
| `3_毎日9時と19時に出す_ON.command` | 今日から毎日9:00と19:00に自動で出るようになる |
| `4_とめる.command` | すぐ止まる |
| `5_ちゃんと出たか見る.command` | 出たか・時刻通りか・在庫残りが出る。おかしければ赤で出る |

---

## なぜブラウザ操作ではダメなのか（今日もう一度実測した）
Meta Business Suiteの投稿画面には `<input type="file">` が**1個も存在しない**（今日2026-09-18に再確認。
チェックボックス3・ラジオ2・その他1、file入力はゼロ）。写真ボタンはOSのファイル選択窓を直接呼ぶ実装で、
ブラウザ自動化からは触れない。instagram.com本体はページが読み込み完了しないため操作自体が不能。
→ **画像つきInstagram投稿を自動化する道は、公式APIしかない。** 2026年8月に6手段を試して同じ結論に到達済み。

## お金
Instagram Platform のコンテンツ公開API＝**無料**。上限は24時間あたり100投稿。
（公式: developers.facebook.com/docs/instagram-platform/content-publishing / 2026-06-30更新）

---

## 追記 2026-09-22｜Collabs（共同投稿）が通ることが分かった

8/19に「Meta Business Suiteの編集画面にCollabsが無い」で止まっていた件。
**探す場所が違っていた。Business Suiteの画面ではなく、APIのパラメータとして公式に存在する。**

> **collaborators** — For Feed image, Reels and Carousels only.
> A list of up to 3 instagram usernames as collaborators on an ig media. Not supported for Stories.
> — https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/

わえの投稿はフィード画像なので対象。`queue.json` の全11本に `collaborators: ["wae0815"]` を設定済み。
**鍵を貼れば、1本目から本人との共同投稿として出る。**

鍵を貼ったら、投稿の前にCollabsの疎通を1回確かめる（こちらで走らせる）：
`post.py --collabtest` → 公開せずにコンテナを1個作るだけで、Collabsが通るかを実際に叩いて確かめる。
24時間で勝手に消える。たまごさんが打つものではない。

※ 万一Collabsが拒否されても、投稿自体は止まらない。Collabs抜きで出して理由をログに残す作りにしてある。

## なぜCollabsが前より重要になったか（2026-04-30の方針転換）

Adam Mosseri（Instagram責任者）の発表：
**投稿の大半が他人のコンテンツのアカウントは、フォロワー以外にレコメンドされなくなった。**
過去30日のローリング判定。従来リールのみだったのが写真・カルーセルにも拡大。
**クレジット表記や軽微な編集では「オリジナル」扱いにならないと明言された。**

そのうえでリーチを保つ正規ルートとして名指しされたのは3つだけ：
**①リミックス ②公式Repostボタン ③Collab投稿**

出典: https://petapixel.com/2026/04/30/new-instagram-policies-target-reposted-content/
