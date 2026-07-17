"""
株式会社モノエン 中村貴広（@monoenceo2026） 用 X自動投稿スクリプト。

1日3回（朝8:00 / 昼12:00 / 夜20:00・JST）に、その時間帯の枠に対応する
投稿を1件選び、Xへ投稿する。

投稿の選び方（優先順位）:
  1. queue.json … その日の朝6:00に Claude が生成した「本日の3投稿」。
     date が本日（JST）で、該当スロットの本文があればそれを投稿する。
  2. tweets.json … 生成の予備プール（手書き90件＋過去の生成分の蓄積）。
     queue が無い / 古い / 該当スロットが空のときのフォールバック。
     「運用開始日からの経過日数 × 3 ＋ スロット」で決めるため、
     フォールバック時も同じ日にスロット間で重複しない。

時間帯 → スロットの対応（JST）:
  ~10:59  → スロット0（朝枠 / 8:00）
  11:00-15:59 → スロット1（昼枠 / 12:00）
  16:00~  → スロット2（夜枠 / 20:00）

時間帯判定・順番割り当ての考え方は、GYAKUTEN（中山蒼）アカウント運用の
daily-tweet 実装を参考にしている。
"""

import json
import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

import tweepy

JST = ZoneInfo("Asia/Tokyo")

# フォールボール（tweets.json 参照）時の基準日。ここからの経過日数で番号を決める。
START_DATE = date(2026, 7, 17)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TWEETS_PATH = os.path.join(BASE_DIR, "tweets.json")
QUEUE_PATH = os.path.join(BASE_DIR, "queue.json")


def slot_for_hour(hour):
    """JSTの時刻から投稿スロット（0=朝 / 1=昼 / 2=夜）を求める。"""
    if hour < 11:
        return 0
    if hour < 16:
        return 1
    return 2


SLOT_NAMES = {0: "朝枠", 1: "昼枠", 2: "夜枠"}


def load_pool():
    with open(TWEETS_PATH, encoding="utf-8") as f:
        tweets = json.load(f)
    if not tweets:
        raise ValueError("tweets.json が空です。投稿文を追加してください。")
    return tweets


def load_queue():
    """本日分の生成キューを読む。無ければ None。"""
    if not os.path.exists(QUEUE_PATH):
        return None
    try:
        with open(QUEUE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def pick_from_queue(queue, now_jst, slot):
    """本日のキューから該当スロットの本文を返す。無ければ None。"""
    if not queue:
        return None
    if queue.get("date") != now_jst.strftime("%Y-%m-%d"):
        return None
    tweets = queue.get("tweets") or []
    if slot < len(tweets):
        text = (tweets[slot] or "").strip()
        if text:
            return text
    return None


def pick_from_pool(pool, now_jst, slot):
    """予備プールから決定論的に1件選ぶ（フォールバック用）。"""
    day_number = (now_jst.date() - START_DATE).days
    if day_number < 0:
        day_number = 0
    index = (day_number * 3 + slot) % len(pool)
    return pool[index], index


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
    slot = slot_for_hour(now_jst.hour)
    slot_name = SLOT_NAMES[slot]

    text = pick_from_queue(load_queue(), now_jst, slot)
    source = "queue.json（本日生成分）"
    if text is None:
        pool = load_pool()
        text, index = pick_from_pool(pool, now_jst, slot)
        source = f"tweets.json（予備プール index={index}）"

    if len(text) > 280:
        print(f"[NG] 投稿本文が長すぎます（{len(text)}文字）。中断します。")
        sys.exit(1)

    print(f"[INFO] 現在時刻(JST): {now_jst:%Y-%m-%d %H:%M}／{slot_name}")
    print(f"[INFO] 取得元: {source}")
    print(f"[INFO] 投稿予定の本文（{len(text)}文字）:\n{text}")

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
