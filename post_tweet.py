"""
株式会社モノエン 中村貴広（@monoenceo2026） 用 X自動投稿スクリプト。

tweets.json に貯めた投稿文プールから、朝/夜の枠に応じて1件を選び投稿する。
時間帯の判定・順番の割り当てロジックは、GYAKUTEN（中山蒼）アカウント運用の
daily-tweet 実装を参考にしている。

- 朝枠 / 夜枠は「JSTで14時より前か後か」で判定する
- 投稿する要素は「運用開始日からの経過日数」から一意に決まるため、
  状態ファイルを持たなくても同じ日に重複せず、順番に一周する
"""

import json
import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

import tweepy

JST = ZoneInfo("Asia/Tokyo")

# このリポジトリで自動投稿を開始した日（JST）。ここを基準に何日目かを数える。
START_DATE = date(2026, 7, 17)

# この時刻より前なら「朝枠」、以降なら「夜枠」。
MORNING_BEFORE_HOUR = 14

TWEETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tweets.json")


def load_tweets():
    with open(TWEETS_PATH, encoding="utf-8") as f:
        tweets = json.load(f)
    if not tweets:
        raise ValueError("tweets.json が空です。投稿文を追加してください。")
    return tweets


def pick_tweet(tweets, now_jst):
    day_number = (now_jst.date() - START_DATE).days
    if day_number < 0:
        day_number = 0
    slot = 0 if now_jst.hour < MORNING_BEFORE_HOUR else 1
    index = (day_number * 2 + slot) % len(tweets)
    slot_name = "朝枠" if slot == 0 else "夜枠"
    return tweets[index], index, slot_name


def get_client():
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print(f"[NG] 必要な環境変数（Secrets）が未設定です: {', '.join(missing)}")
        print("     GitHub の Settings > Secrets and variables > Actions に登録してください。")
        sys.exit(1)

    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def main():
    now_jst = datetime.now(JST)
    tweets = load_tweets()
    text, index, slot_name = pick_tweet(tweets, now_jst)

    print(f"[INFO] 現在時刻(JST): {now_jst:%Y-%m-%d %H:%M}／{slot_name}／pool index={index}")
    print(f"[INFO] 投稿予定の本文:\n{text}")

    client = get_client()

    try:
        client.create_tweet(text=text)
        print("[OK] 投稿に成功しました。")
    except tweepy.Forbidden as e:
        print(f"[NG] 403 Forbidden: {e}")
        print("     → アプリの権限が Read のまま、または権限変更後に Access Token を")
        print("       作り直していない可能性があります。Developer Portal で確認してください。")
        sys.exit(1)
    except tweepy.Unauthorized as e:
        print(f"[NG] 401 Unauthorized: {e}")
        print("     → Secrets の値が間違っている、または余計な空白が入っている可能性があります。")
        sys.exit(1)
    except tweepy.TooManyRequests as e:
        print(f"[NG] 429 Too Many Requests: {e}")
        print("     → 無料枠の投稿上限を超えています。時間を置いて再実行してください。")
        sys.exit(1)
    except tweepy.TweepyException as e:
        print(f"[NG] 投稿に失敗しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
