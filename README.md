# @monoenceo2026 毎日AI自動ツイート

株式会社モノエン 代表取締役社長 CEO 中村貴広さんの X（旧Twitter）アカウント
[@monoenceo2026](https://x.com/monoenceo2026) 用の自動運用一式です。**画像は使用しません**（テキストのみ）。

- **ツイート作成**：**Claude Code のルーチン機能（Claudeのサブスク）** が毎朝、本日の3投稿を作成します。
  → **API利用料はかかりません**（サブスクの範囲内）。
- **自動投稿**：GitHub Actions が **1日3回（朝8:00 / 昼12:00 / 夜20:00・日本時間）** に投稿します。

投稿文は、本人へのヒアリングシートと会社資料（BEGINNING LEGACY／MONOENブランド資料）をもとに作成した
「声プロファイル」（`voice_profile.md`）に沿って生成します。作成時に **Web検索で日本の製造業・ライブコマース・
地方産業・スタートアップ採用まわりのトレンドを軽く確認**し、無理なく投稿に活かします（トレンド分析）。
作成できなかった日でも、あらかじめ用意した **90件の予備プールから自動で投稿**されるので、止まりません。

自動投稿ロジックの土台は、GYAKUTEN（中山蒼さん）アカウントの daily-tweet 運用を参考にしています。

---

## 全体の流れ（1日）

```
 6:00  Claude Code ルーチン（サブスク）が起動
        └ voice_profile.md と直近の投稿を読み、Web検索でトレンド確認
          → 本日の3投稿を作成 → save_tweets.py で検証・保存
          → queue.json（本日分）を更新＋ tweets.json（蓄積）に追記 → main にコミット
 8:00  Daily Tweet（朝枠）→ queue.json の1件目を投稿   ┐
12:00  Daily Tweet（昼枠）→ queue.json の2件目を投稿   ├ GitHub Actions（X APIのみ）
20:00  Daily Tweet（夜枠）→ queue.json の3件目を投稿   ┘
```

※ 6:00の作成が失敗した日は、各投稿が `tweets.json`（90件の予備プール）から自動で選ばれます。

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `voice_profile.md` | **声・発信方針の定義書**（人が編集できる）。ルーチンが生成に使う。声を変えたいときはここを編集 |
| `save_tweets.py` | ルーチンが作った3投稿を検証（140字/NG表現/重複）して queue.json・tweets.json に保存するヘルパー（API不要） |
| `queue.json` | その日に作成された「本日の3投稿」（朝・昼・夜）。※初回作成後に自動生成 |
| `tweets.json` | 蓄積アーカイブ兼・予備プール（手書き90件＋過去の作成分）。作成失敗時のフォールバック元 |
| `post_tweet.py` | 時間帯（朝/昼/夜）に応じて1件を選び、Xに投稿 |
| `.github/workflows/daily-tweet.yml` | 毎日8:00・12:00・20:00に投稿（GitHub Actions） |

### 投稿の選び方（post_tweet.py）
1. `queue.json` に本日（JST）の投稿があれば、その時間帯の枠を投稿。
2. 無い／古い場合は `tweets.json` から「経過日数×3＋枠」で決定論的に選択（同じ日に枠間で重複しない）。

時間帯 → 枠：`〜10:59＝朝枠`／`11:00〜15:59＝昼枠`／`16:00〜＝夜枠`。

---

## 必要な認証情報（GitHub Secrets）

投稿に必要なのは **Xの4つだけ** です（作成はClaudeのサブスクで行うため、AnthropicのAPIキーは不要）。

| Name | 値 |
|---|---|
| `X_API_KEY` | API Key（Consumer Key） |
| `X_API_SECRET` | API Key Secret（Consumer Secret） |
| `X_ACCESS_TOKEN` | Access Token（Read and Write権限） |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |

> Bearer Token だけでは投稿できません。権限を「Read and Write」にしてから Access Token を作り直してください（投稿時403の対策）。

---

## セットアップ手順

### 手順1：Xの Access Token を取得（未取得の場合）
X Developer Portal（ https://developer.x.com/en/portal/dashboard ）で対象アプリを開き、
1. 「User authentication settings」で **App permissions を「Read and Write」** に設定して保存。
2. 「Keys and tokens」タブ →「Access Token and Secret」で **Generate / Regenerate**。
3. 表示された Access Token / Access Token Secret を控える（一度しか表示されません）。

### 手順2：GitHub Secrets を登録
リポジトリの **Settings → Secrets and variables → Actions** で、上の表の4つを登録。

### 手順3：ツイート作成ルーチンを用意（Claude Code）
毎朝6:00に本日の3投稿を作成する **Claude Code のルーチン**を設定します（このリポジトリのセットアップ時に作成済み）。
ルーチンは次を行います：`voice_profile.md` と直近の投稿を読む → Web検索でトレンド確認 → 3投稿を作成 →
`save_tweets.py` で保存 → `queue.json`／`tweets.json` を **main にコミット**。
※ 定期投稿（GitHub Actions の cron）はデフォルトブランチ（main）で動くため、このリポジトリを main に反映してから運用開始します。

### 手順4：投稿のテスト（手動実行）
1. **Actions タブ →「Daily Tweet」→「Run workflow」**。
2. 実行した時間帯（朝/昼/夜）に対応する投稿が実際に流れます（テストでも本物が投稿されます）。
3. X（@monoenceo2026）で確認。ログに `[OK] 投稿に成功しました。` が出れば成功。

### 手順5：あとは自動
以降は毎日 6:00に作成 → 8:00/12:00/20:00に投稿、が自動で回ります。
GitHub Actions の混雑で数分〜十数分ほど遅れることがあります（仕様）。

---

## 時刻を変えたいとき
- 作成：Claude Code ルーチンのスケジュール（現状 JST 6:00）。
- 投稿：`.github/workflows/daily-tweet.yml` の cron（UTC基準。`0 23`＝8:00、`0 3`＝12:00、`0 11`＝20:00）。
- 投稿の枠判定は `post_tweet.py` の `slot_for_hour`（11時／16時が境界）。時刻を大きく変える場合はここも合わせて調整。

## 声・方針を調整したいとき
- **`voice_profile.md` を編集**するだけで、翌日以降の作成に反映されます（コード変更不要）。
  テーマ比率、トーン、決めフレーズ、使ってよい事実、NG表現などをまとめています。
- 作成された投稿を手直ししたい場合は、投稿前（当日8:00より前）に `queue.json` の該当要素を書き換えてください。
- 予備プールを増やしたい／気に入らない投稿を差し替えたい場合は `tweets.json`（文字列の配列・140文字以内）を編集。

## 手動で本日分を作りたいとき（Claude Codeを使わずに）
`save_tweets.py` に3件渡せば queue.json に保存できます（そのままコミットすれば当日投稿されます）。
```
python save_tweets.py "朝の1件" "昼の1件" "夜の1件"
```

---

## コストの目安
- **ツイート作成**：Claude Code のルーチン＝**Claudeのサブスクの範囲内**。追加のAPI利用料なし。
- **GitHub Actions**：1回あたり1分未満。無料枠（パブリック実質無制限／プライベート月2,000分）で十分。
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
| 作成されない日がある | ルーチンの失敗 → その日は予備プール（tweets.json）から自動投稿されるので投稿自体は継続 |
