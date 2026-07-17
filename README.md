# @monoenceo2026 毎日AI自動ツイート

株式会社モノエン 代表取締役社長 CEO 中村貴広さんの X（旧Twitter）アカウント
[@monoenceo2026](https://x.com/monoenceo2026) 用に、GitHub Actions で
**毎朝 Claude が本日の投稿を3件生成 → 1日3回（朝8:00 / 昼12:00 / 夜20:00・日本時間）自動投稿**
する仕組みです。**画像は使用しません**（テキストのみ）。

投稿文は、本人へのヒアリングシートと会社資料（BEGINNING LEGACY／MONOENブランド資料）をもとに
作成した「声プロファイル」に沿って、Claude が毎日生成します。生成時に **Claude のWeb検索で
日本の製造業・ライブコマース・地方産業・スタートアップ採用まわりのトレンドを軽く確認**し、
無理なく投稿に活かします（トレンド分析）。生成に失敗した日でも、あらかじめ用意した
**90件の予備プールから自動で投稿**されるので、アカウントが止まることはありません。

自動投稿ロジックの土台は、GYAKUTEN（中山蒼さん）アカウントの daily-tweet 運用を参考にしています。

---

## 全体の流れ（1日）

```
 6:00  Generate Tweets ワークフロー
        └ Claude が「本日の3投稿」を生成（Web検索でトレンド確認）
          → queue.json（本日分）に保存＋ tweets.json（蓄積アーカイブ）に追記
          → GitHubへ自動コミット（＝ツイートがGitHub上で拡充される）
 8:00  Daily Tweet（朝枠）→ queue.json の1件目を投稿
12:00  Daily Tweet（昼枠）→ queue.json の2件目を投稿
20:00  Daily Tweet（夜枠）→ queue.json の3件目を投稿
```

※ 6:00の生成が失敗した日は、各投稿が `tweets.json`（90件の予備プール）から自動で選ばれます。

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `voice_profile.md` | **声・発信方針の定義書**（人が編集できる）。Claudeの生成プロンプトの中核。声を変えたいときはここを編集 |
| `generate_tweets.py` | 毎朝6:00に Claude で本日の3投稿を生成し、queue.json／tweets.json を更新 |
| `queue.json` | その日に生成された「本日の3投稿」（朝・昼・夜）。※初回生成後に自動作成 |
| `tweets.json` | 蓄積アーカイブ兼・予備プール（手書き90件＋過去の生成分）。生成失敗時のフォールバック元 |
| `post_tweet.py` | 時間帯（朝/昼/夜）に応じて1件を選び、Xに投稿 |
| `.github/workflows/generate-tweets.yml` | 毎日6:00に生成 |
| `.github/workflows/daily-tweet.yml` | 毎日8:00・12:00・20:00に投稿 |

### 投稿の選び方（post_tweet.py）
1. `queue.json` に本日（JST）の投稿があれば、その時間帯の枠を投稿。
2. 無い／古い場合は `tweets.json` から「経過日数×3＋枠」で決定論的に選択（同じ日に枠間で重複しない）。

時間帯 → 枠：`〜10:59＝朝枠`／`11:00〜15:59＝昼枠`／`16:00〜＝夜枠`。

---

## 必要な認証情報

### 1. Xの認証情報4つ（投稿に必須）
- API Key（Consumer Key） … `X_API_KEY`
- API Key Secret（Consumer Secret） … `X_API_SECRET`
- Access Token（Read and Write権限） … `X_ACCESS_TOKEN`
- Access Token Secret … `X_ACCESS_TOKEN_SECRET`

> Bearer Token だけでは投稿できません。投稿には上の4つ（特に Access Token / Access Token Secret）が必要です。

### 2. Anthropic APIキー（ツイート生成に必須）
- `ANTHROPIC_API_KEY` … https://console.anthropic.com/ で発行

---

## セットアップ手順

### 手順1：Xの Access Token を取得（未取得の場合）
X Developer Portal（ https://developer.x.com/en/portal/dashboard ）で対象アプリを開き、
1. 「User authentication settings」で **App permissions を「Read and Write」** に設定して保存。
2. 「Keys and tokens」タブ →「Access Token and Secret」で **Generate / Regenerate**。
3. 表示された Access Token / Access Token Secret を控える（一度しか表示されません）。

> 権限を「Read and Write」にする前に作った Access Token は読み取り専用です。権限変更後は必ず作り直してください（投稿時403の原因）。

### 手順2：GitHub Secrets を登録
リポジトリの **Settings → Secrets and variables → Actions →「New repository secret」** で登録：

| Name | 値 |
|---|---|
| `X_API_KEY` | API Key（Consumer Key） |
| `X_API_SECRET` | API Key Secret（Consumer Secret） |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |
| `ANTHROPIC_API_KEY` | Anthropic の APIキー |

（任意）モデルを変えたい場合は **Variables** タブで `ANTHROPIC_MODEL` を設定（未設定なら `claude-opus-4-8`）。
コストを抑えたいときは `claude-haiku-4-5` などに変更できます。

### 手順3：生成のテスト（手動実行）
1. **Actions タブ →「Generate Tweets」→「Run workflow」**。
2. 成功すると `queue.json` が作られ、`tweets.json` に3件追記されてコミットされます。
3. リポジトリで `queue.json` を開き、本日の3投稿の中身を確認できます。

### 手順4：投稿のテスト（手動実行）
1. **Actions タブ →「Daily Tweet」→「Run workflow」**。
2. 実行した時間帯（朝/昼/夜）に対応する投稿が実際に流れます（テストでも本物が投稿されます）。
3. X（@monoenceo2026）で投稿を確認。ログに `[OK] 投稿に成功しました。` が出れば成功。

### 手順5：あとは自動
以降は毎日 6:00に生成 → 8:00/12:00/20:00に投稿、が自動で回ります（設定不要）。
GitHub Actions の混雑で数分〜十数分ほど遅れることがあります（仕様）。

---

## 時刻を変えたいとき
- 生成：`.github/workflows/generate-tweets.yml` の cron（UTC基準。現状 `0 21 * * *`＝JST 6:00）。
- 投稿：`.github/workflows/daily-tweet.yml` の cron（`0 23`＝8:00、`0 3`＝12:00、`0 11`＝20:00）。
- 投稿の枠判定は `post_tweet.py` の `slot_for_hour`（11時／16時が境界）。時刻を大きく変える場合はここも合わせて調整。

## 声・方針を調整したいとき
- **`voice_profile.md` を編集**するだけで、翌日以降の生成に反映されます（コード変更不要）。
  テーマ比率、トーン、決めフレーズ、使ってよい事実、NG表現などをまとめています。
- 生成された投稿を手直ししたい場合は、投稿前（当日8:00より前）に `queue.json` の該当要素を書き換えてください。
- 予備プールを増やしたい／気に入らない投稿を差し替えたい場合は `tweets.json`（文字列の配列・140文字以内）を編集。

## 過去ツイートの口調学習について
`generate_tweets.py` は生成時に、X API で @monoenceo2026 の直近ツイートの読み取りを試み、
取得できれば口調・語彙の参考＆重複回避に使います。X無料APIの制限で読み取れない場合は、
自動的に `voice_profile.md`（本人ヒアリング由来の声プロファイル）にフォールバックします。

---

## コストの目安
- **GitHub Actions**：1回あたり1分未満。無料枠（パブリック実質無制限／プライベート月2,000分）で十分。
- **Anthropic API**：1日1回の生成（3投稿＋Web検索）で、モデルにより 1回あたり概ね数円〜十数円程度。
  月あたり数百円規模が目安です。低コストにしたい場合は `ANTHROPIC_MODEL` を `claude-haiku-4-5` に。
- **X API**：1日3投稿（月約90件）。書き込みが有効かは Developer Portal で確認してください。

## セキュリティ
- 認証情報は必ず **GitHub Secrets** で管理（コード・ファイルに直接書かない。`.gitignore` 済み）。
- チャット等に貼った Key / Token は、念のため各Portalで再生成し、Secretsの値も更新すると安全です。

## うまくいかないとき（よくあるエラー）
| 症状 | 原因と対処 |
|---|---|
| 投稿 `403 Forbidden` | アプリ権限がReadのまま／権限変更後にAccess Token未再生成 → 手順1をやり直す |
| 投稿 `401 Unauthorized` | キーの値が違う／余計な空白 → Secretsを入れ直す |
| 投稿 `429 Too Many Requests` | 無料枠の上限超過 → 時間を置く |
| 生成が失敗する | `ANTHROPIC_API_KEY` 未設定／残高不足 → Secretsと残高を確認（失敗日は予備プールから投稿されます） |
| 生成の commit が失敗 | ワークフローの権限 → `generate-tweets.yml` の `permissions: contents: write` を確認 |

> ⏰ 定期実行（cron）はデフォルトブランチのワークフローだけが動きます。自動運用を始めるには、
> このブランチをデフォルトブランチ（main）にマージしてください。手動実行（Run workflow）は各ブランチで可能です。
