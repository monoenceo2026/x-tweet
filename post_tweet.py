"""
株式会社モノエン 中村貴広（@monoenceo2026） 用 X自動投稿スクリプト。

1日3回（朝8:00 / 昼12:00 / 夜20:00・JST）に、その時間帯の枠に対応する
投稿を1件選び、Xへ投稿する。

■ トリガー（重要）
  GitHub 内蔵の schedule(cron) は混雑時に遅延・スキップが多いため使わない。
  外部スケジューラ（cron-job.org 等）が定時に workflow_dispatch を叩き、
  入力 slot（morning/noon/evening）を渡して起動する。Actions 側はその slot を
  環境変数 POST_SLOT に入れて本スクリプトを実行する。

投稿の選び方（優先順位）:
  1. queue.json … その日の朝に Claude が生成した「本日の3投稿」。
     date が本日（JST）で、該当スロットの本文があればそれを投稿する。
  2. tweets.json … 生成の予備プール（手書き＋過去の生成分の蓄積）。
     queue が無い / 古い / 該当スロットが空のときのフォールバック。
     「運用開始日からの経過日数 × 3 ＋ スロット」で開始位置を決め、
     重複・長さ超過に当たったら idx += 3 で次候補へ巡回する。

スロットの決め方（優先順位）:
  1. POST_SLOT（外部スケジューラ→Actionsが渡す。morning/noon/evening または 0/1/2）
  2. FORCE_SLOT（手動デバッグ用の明示指定。同じ表記を受け付ける）
  3. 引数 --slot N
  4. 実行時刻から判定（フォールバック。上記いずれも無いとき）:
       ~10:59      → スロット0（朝枠 / 8:00）
       11:00-15:59 → スロット1（昼枠 / 12:00）
       16:00~      → スロット2（夜枠 / 20:00）
  1〜3 の明示指定を優先することで、起動が予定時刻より遅れても本来の枠が確実に投稿される
  （＝遅延で朝枠が昼に流れて別枠が出る、といった取り違えが起きない）。

時間帯判定・順番割り当ての考え方は、GYAKUTEN（中山蒼）アカウント運用の
daily-tweet 実装を参考にしている。
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, date
from zoneinfo import ZoneInfo

import tweepy

JST = ZoneInfo("Asia/Tokyo")

# フォールバック（tweets.json 参照）時の基準日。ここからの経過日数で開始番号を決める。
START_DATE = date(2026, 7, 17)

# Python字数のハード上限（save_tweets.py の MAX_LEN と揃える）。
MAX_LEN = 280

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TWEETS_PATH = os.path.join(BASE_DIR, "tweets.json")
QUEUE_PATH = os.path.join(BASE_DIR, "queue.json")

SLOT_NAMES = {0: "朝枠", 1: "昼枠", 2: "夜枠"}

# 外部スケジューラ／手動指定で受け付けるスロット表記。
SLOT_ALIASES = {
    "morning": 0, "朝": 0, "0": 0,
    "noon": 1, "昼": 1, "1": 1,
    "evening": 2, "night": 2, "夜": 2, "2": 2,
}

URL_RE = re.compile(r"https?://\S+")


def slot_for_hour(hour):
    """JSTの時刻から投稿スロット（0=朝 / 1=昼 / 2=夜）を求める。"""
    if hour < 11:
        return 0
    if hour < 16:
        return 1
    return 2


def _slot_from_value(value):
    """morning/noon/evening や 0/1/2 等の表記を slot(0/1/2) に変換。不正なら None。"""
    return SLOT_ALIASES.get(value.strip().lower())


def current_slot(now_jst):
    """投稿スロットを決める。戻り値は (slot, source文字列)。

    優先順: POST_SLOT → FORCE_SLOT → 引数 --slot → 実行時刻から判定。
    明示指定を優先することで、起動が遅れても本来の枠が確実に投稿される。
    """
    # 1) 環境変数（外部スケジューラ→Actions が渡す POST_SLOT、手動用 FORCE_SLOT）
    for env_name in ("POST_SLOT", "FORCE_SLOT"):
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            continue
        slot = _slot_from_value(raw)
        if slot is not None:
            return slot, f"明示指定（{env_name}={raw}）"
        print(f"[警告] 不正なスロット指定 {env_name}='{raw}' は無視します。")

    # 2) 引数 --slot N / --slot=N
    for i, arg in enumerate(sys.argv):
        raw = None
        if arg == "--slot" and i + 1 < len(sys.argv):
            raw = sys.argv[i + 1]
        elif arg.startswith("--slot="):
            raw = arg.split("=", 1)[1]
        if raw is not None:
            slot = _slot_from_value(raw)
            if slot is not None:
                return slot, f"明示指定（--slot {raw}）"
            print(f"[警告] 不正なスロット指定 --slot '{raw}' は無視します。")

    # 3) 実行時刻から判定
    return slot_for_hour(now_jst.hour), "実行時刻から判定"


def x_weighted_len(text):
    """Xの重み付き文字数を概算（全角/CJK=2、URL=23、その他=1）。参考表示用。"""
    urls = URL_RE.findall(text)
    body = URL_RE.sub("", text)
    total = 23 * len(urls)
    for ch in body:
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


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


def iter_candidates(now_jst, slot):
    """投稿候補を優先順に (text, source) で列挙する。

    1. queue.json の該当スロット（本日分があれば最優先）
    2. tweets.json の予備プールを base = (経過日数×3 + slot) から idx += 3 で巡回。
    呼び出し側は重複(403)・長さ超過なら次候補へ進む。
    """
    tried = set()

    q = pick_from_queue(load_queue(), now_jst, slot)
    if q:
        tried.add(q)
        yield q, "queue.json（本日生成分）"

    pool = load_pool()
    n = len(pool)
    day_number = max(0, (now_jst.date() - START_DATE).days)
    start = (day_number * 3 + slot) % n
    idx = start
    for _ in range(n):
        text = (pool[idx] or "").strip()
        if text and text not in tried:
            tried.add(text)
            yield text, f"tweets.json（予備プール index={idx}）"
        idx = (idx + 3) % n
        if idx == start:
            break


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


def _is_duplicate_error(err):
    """403 の内容が「重複投稿」かどうかを判定する。"""
    return "duplicate" in str(err).lower()


def main():
    now_jst = datetime.now(JST)
    slot, slot_source = current_slot(now_jst)
    slot_name = SLOT_NAMES[slot]
    print(f"[INFO] 現在時刻(JST): {now_jst:%Y-%m-%d %H:%M}／{slot_name}（{slot_source}）")

    client = get_client()

    attempted = 0
    for text, source in iter_candidates(now_jst, slot):
        # 長さ超過は投稿せず次候補へ（重み付き長は参考表示）。
        if len(text) > MAX_LEN:
            print(f"[SKIP] 上限超過（{len(text)}字 > {MAX_LEN}字）。次候補へ: {text[:24]}…")
            continue

        attempted += 1
        print(f"[INFO] 取得元: {source}")
        print(f"[INFO] 投稿予定の本文（{len(text)}文字 / X換算{x_weighted_len(text)}字）:\n{text}")

        try:
            client.create_tweet(text=text)
            print("[OK] 投稿に成功しました。")
            return
        except tweepy.Forbidden as e:
            if _is_duplicate_error(e):
                print(f"[SKIP] 重複(403 duplicate)のため次候補へ: {e}")
                continue
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

    if attempted == 0:
        print("[NG] 投稿できる候補がありませんでした（長さ超過などで全滅）。")
    else:
        print("[NG] すべての候補が重複(403)で投稿できませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
