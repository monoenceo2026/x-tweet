# @monoenceo2026 毎日自動ツイート

株式会社モノエン 代表取締役社長 CEO 中村貴広さんの X（旧Twitter）アカウント
[@monoenceo2026](https://x.com/monoenceo2026) 用に、GitHub Actions で
**1日2回（朝8:00 / 夜20:00・日本時間）** 自動投稿する仕組みです。

投稿文は本人へのヒアリングシートと会社資料をもとに作成した **90件のプール**
（`tweets.json`）から、毎日2つずつ順番に投稿します（**約45日で一周**）。
テーマは「①ビジョン・覚悟 ②職人・工場・商品の物語 ③事業の裏側・進捗
④採用（ライブコマーサー募集など） ⑤ブランディング／ライブコマースのノウハウ
⑥日常・人間味」の6本柱です（比率イメージ：20:20:20:20:10:10）。

**画像は使用しません。**（ヒアリング内容に沿い、テキストのみの投稿です）
**サーバー代・LLM利用料は一切かかりません**（GitHubの無料枠＋Xの無料API枠のみ）。

このリポジトリの構成・自動投稿ロジックは、GYAKUTEN（中山蒼さん）アカウントの
daily-tweet 運用を参考にしています。

---

## 仕組み（ざっくり）

- `tweets.json` … 投稿文のストック（90件・6テーマを朝夜に配分）
- `post_tweet.py` … 時間帯（朝/夜）に応じて1件を選び、Xに投稿するプログラム
  - 「運用開始日からの経過日数 × 2 ＋ 朝/夜」で投稿する要素の番号を決めるため、
    状態ファイルを持たなくても同じ日に重複せず、順番に一周します
  - JSTで **14時より前＝朝枠／以降＝夜枠** として判定します
- `.github/workflows/daily-tweet.yml` … 毎日 朝8:00・夜20:00 に自動実行する設定

---

## 必要なもの

1. **GitHubアカウント**（無料）
2. **Xの認証情報4つ**
   - API Key（Consumer Key）
   - API Key Secret（Consumer Secret）
   - **Access Token** ← ★今回まだ未取得
   - **Access Token Secret** ← ★今回まだ未取得

すでに Consumer Key / Consumer Secret / Bearer Token はいただいていますが、
**Bearer Token だけでは投稿できません。** 投稿には Access Token と
Access Token Secret（読み書き権限つき）が別途必要です。

> 🔴 チャットに貼っていただいた Consumer Key・Secret・Bearer Token は、
> 念のため X Developer Portal で **再生成（Regenerate）** しておくことを
> 強くおすすめします。再生成後は、下記 Secrets の値も新しいものに
> 差し替えてください（コード・リポジトリには一切書き込んでいません）。

---

## 手順1：Xの Access Token を取得する（最重要）

X Developer Portal（ https://developer.x.com/en/portal/dashboard ）で、
対象アプリを開いて操作します。

1. **「User authentication settings」→「Set up / Edit」** を開く
2. **App permissions を「Read and Write」** に設定（Readのままだと投稿できません）
3. Type of App は「Web App, Automated App or Bot」など、Callback URL と
   Website URL は仮で可（例：`https://monoen.co.jp` や `https://example.com`）→ 保存
4. **「Keys and tokens」タブ** を開く
5. **「Access Token and Secret」** の欄で **Generate（または Regenerate）** を押す
6. 表示された **Access Token** と **Access Token Secret** を控える（一度しか表示されません）

> 🔴 **よくある失敗：** 権限を「Read and Write」にする前に作った Access Token は
> 読み取り専用のままです。権限を変えたら、**必ず Access Token を作り直して
> （Regenerate）** ください。これをしないと投稿時に「403」エラーになります。

---

## 手順2：GitHubにこのリポジトリをアップロード（済みの場合はスキップ）

このリポジトリには、`post_tweet.py` / `tweets.json` / `requirements.txt` /
`.github/workflows/daily-tweet.yml` が含まれています。
`.github/workflows/daily-tweet.yml` の階層（フォルダ構造）を保ったまま
GitHub 上に置いてください（このセッションで作成済みの場合は対応不要です）。

---

## 手順3：認証情報を Secrets に登録（コードには絶対書かない）

リポジトリの **Settings → Secrets and variables → Actions →
「New repository secret」** から、以下の **4つ** を **名前を完全一致** で登録します。

| Name（この通りに入力） | Value（入れる値） |
|---|---|
| `X_API_KEY` | API Key（Consumer Key） |
| `X_API_SECRET` | API Key Secret（Consumer Secret） |
| `X_ACCESS_TOKEN` | 手順1で取得した Access Token |
| `X_ACCESS_TOKEN_SECRET` | 手順1で取得した Access Token Secret |

---

## 手順4：テスト投稿（手動実行）

1. リポジトリの **「Actions」タブ** を開く
2. 左側の **「Daily Tweet」** を選択
3. 右側の **「Run workflow」** ボタンを押す
4. 1〜2分後、実行ログが緑（成功）になり、`[OK] 投稿に成功しました。` と出れば完了
5. X（@monoenceo2026）を見て、投稿されているか確認

> ※ 手動実行でも「実行時点の枠（朝/夜）に対応する本物のツイート」が実際に
> 投稿されます。テストのつもりでも投稿されるのでご注意ください。

---

## 手順5：毎日自動投稿の確認

手順4が成功していれば、あとは **毎日 朝8:00・夜20:00（日本時間）に自動で投稿**
されます。設定は不要です。朝と夜で別々の投稿が選ばれ、同じ日に重複しません。

- ⏰ GitHub Actions の混雑により、**数分〜十数分ほど遅れる**ことがあります（仕様）。
- 時刻を変えたい場合は `.github/workflows/daily-tweet.yml` の cron を編集
  （UTC基準。日本時間 − 9時間。現状は `0 23 * * *`＝朝8:00、`0 11 * * *`＝夜20:00）。
  ※ `post_tweet.py` は「JSTで14時より前＝朝枠／以降＝夜枠」で判定するため、
  時刻を大きく変える場合は `post_tweet.py` 内の `MORNING_BEFORE_HOUR` も
  合わせて調整してください。

---

## 投稿文を補充・編集したいとき

- `tweets.json` は文字列の配列です。1要素＝1投稿。改行は `\n` で表現します。
  **日本語は140文字以内**にしてください。
- 90件を使い切る頃（1日2件なので**約45日後**）に、また Cowork（このClaude）で
  「投稿文を追加して」と頼めば、**無料で**新しい投稿文を作成します。
- 自分で追記・削除・書き換えもOKです。気に入らない投稿はその要素だけ差し替えてください。
- 投稿の追加・削除で配列の長さが変わっても、`post_tweet.py` は自動で新しい
  件数に合わせて周期を計算し直すので、コード側の変更は不要です。

---

## 発信の基本方針（ヒアリングシートより）

- 一人称は基本「私」。覚悟・本音を語る投稿のみ「俺」も可。
- 絵文字はほぼ使わない。ハッシュタグは告知・シリーズ名がある時のみ。
- 政治・宗教への支持表明、根拠のない誇張、特定個人・競合への攻撃、
  未公開の契約・数値・人事情報は投稿しない。
- 本人が言っていないこと、体験していないことを、実体験として投稿しない
  （このプールの投稿文はすべて一般論・所感として書いており、日付が
  特定される事実は会社資料等ですでに公開されている内容のみを使用しています）。
- 炎上・誹謗中傷コメントへの自動返信は行いません（本アカウントは投稿のみ）。
  リプライ・DM対応は中村さん本人が行う想定です。

---

## セキュリティの注意

- 🔑 認証情報は **必ず GitHub Secrets** で管理し、コードやファイルに直接書かない
  （`.gitignore` 済み）。
- 💬 **チャットに貼った Key / Bearer Token は、念のため Developer Portal で
  再生成（Regenerate）** しておくと安全です。再生成したら GitHub Secrets の
  値も更新してください。

---

## うまくいかないとき（よくあるエラー）

| 症状 | 原因と対処 |
|---|---|
| `403 Forbidden` | アプリ権限が Read のまま／権限変更後にAccess Tokenを作り直していない → 手順1をやり直す |
| `401 Unauthorized` | キーの値が間違っている／余計な空白 → Secrets を入れ直す |
| `429 Too Many Requests` | 無料枠の上限超過 → 時間を置く（1日2投稿なら通常問題なし） |
| 投稿が重複した | 同じ枠（朝/夜）で手動実行を複数回した → 各枠1回でOK |

---

## 無料枠について

- Xの無料APIは仕様変更が続いています。1日2投稿（月約60件）程度であれば
  従来の無料上限内に収まることが多いですが、お使いのアプリで書き込みが
  有効かは Developer Portal で確認してください。
- GitHub Actions の無料枠（パブリックリポジトリは実質無制限、プライベートでも
  月2,000分）に対し、この処理は1回あたり1分未満なので、無料枠で十分まかなえます。
