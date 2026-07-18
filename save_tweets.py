"""
「本日の3投稿」を保存する検証・永続化ヘルパー（LLM/API不要）。

ツイート本文の生成は Claude Code のルーチン（＝Claudeのサブスク）が行い、
考えた3件をこのスクリプトに渡して保存する。ここでは生成せず、検証と保存だけを行う:

  - 文字数（後述）・NG表現・既存との重複を検証
  - 本日分の queue.json（朝・昼・夜の3件）を書き出す
  - tweets.json（蓄積アーカイブ兼・予備プール）に追記する＝GitHub上でツイートが拡充される

使い方（どちらでも可）:
  python save_tweets.py "朝の1件" "昼の1件" "夜の1件"
  echo '["朝の1件","昼の1件","夜の1件"]' | python save_tweets.py

■ 文字数について（重要）
  Xは日本語などの全角文字を「2字」としてカウントし、標準アカウントの上限は
  X換算280字（＝全角およそ140字）。URLは実際の長さに関わらず一律23字。
  これを超える「長文」ツイートは X Premium 加入が前提（未加入だと投稿が403で弾かれる）。
  本スクリプトは各件の X換算文字数 を表示し、280字を超える件には Premium 必要の
  警告を出す（エラーにはしない＝長文運用を許可）。ハードな上限は MAX_LEN 字（Python字数）。

検証に通らない要素があれば、理由を表示して終了コード2で終わる（呼び出し側で直して再実行）。
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TWEETS_PATH = os.path.join(BASE_DIR, "tweets.json")
QUEUE_PATH = os.path.join(BASE_DIR, "queue.json")

# ハードな上限（Python字数）。post_tweet.py 側も len(text)>280 を弾くため 280 に揃える。
MAX_LEN = 280
# 標準アカウントの X換算上限。これを超える件は X Premium が必要（警告のみ）。
X_STD_LIMIT = 280
EXPECTED = 3
BANNED = ["絶対に成功", "誰でも簡単", "必ず儲か", "100%成功"]

URL_RE = re.compile(r"https?://\S+")


def x_weighted_len(text):
    """Xの重み付き文字数を概算する（全角/CJK=2、URL=23、その他=1）。

    標準アカウントの上限は 280（＝全角およそ140字）。超える場合は X Premium が必要。
    """
    urls = URL_RE.findall(text)
    body = URL_RE.sub("", text)
    total = 23 * len(urls)
    for ch in body:
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            total += 2
        else:
            total += 1
    return total


def load_pool():
    if not os.path.exists(TWEETS_PATH):
        return []
    with open(TWEETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def read_input_tweets():
    args = [a for a in sys.argv[1:] if a.strip()]
    if args:
        return args
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                print("[NG] 標準入力のJSONを解釈できませんでした。")
                sys.exit(2)
            if not isinstance(data, list):
                print("[NG] 標準入力は文字列の配列で渡してください。")
                sys.exit(2)
            return [str(t) for t in data]
    return []


def validate(tweets, pool):
    seen = set(pool)
    errors = []
    warnings = []
    cleaned = []
    for i, t in enumerate(tweets):
        t = t.strip()
        if not t:
            errors.append(f"[{i}] 空です。")
            continue
        if len(t) > MAX_LEN:
            errors.append(f"[{i}] 長すぎます（{len(t)}字 > 上限{MAX_LEN}字）: {t[:30]}…")
            continue
        hit = next((b for b in BANNED if b in t), None)
        if hit:
            errors.append(f"[{i}] NG表現「{hit}」を含む: {t[:30]}…")
            continue
        if t in seen:
            errors.append(f"[{i}] 既存の投稿と重複: {t[:30]}…")
            continue
        w = x_weighted_len(t)
        if w > X_STD_LIMIT:
            warnings.append(
                f"[{i}] X換算{w}字（標準上限{X_STD_LIMIT}超）＝長文。"
                f"X Premium 未加入だと投稿が弾かれます: {t[:24]}…"
            )
        seen.add(t)
        cleaned.append(t)
    return cleaned, errors, warnings


def main():
    tweets = read_input_tweets()
    if not tweets:
        print("使い方: python save_tweets.py \"朝の1件\" \"昼の1件\" \"夜の1件\"")
        sys.exit(2)

    pool = load_pool()
    cleaned, errors, warnings = validate(tweets, pool)

    if errors:
        print("[NG] 次の要素が検証に通りませんでした。修正して再実行してください:")
        for e in errors:
            print("  " + e)
        sys.exit(2)

    if len(cleaned) != EXPECTED:
        print(f"[NG] 3件ちょうど渡してください（受領: {len(cleaned)}件）。")
        sys.exit(2)

    if warnings:
        print("[注意] 長文（X換算280字超）が含まれます。X Premium 未加入なら該当枠は投稿されません:")
        for w in warnings:
            print("  " + w)

    now_jst = datetime.now(JST)
    queue = {
        "date": now_jst.strftime("%Y-%m-%d"),
        "generated_at": now_jst.isoformat(timespec="seconds"),
        "source": "claude-code-routine",
        "tweets": cleaned,
    }
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    pool.extend(cleaned)
    with open(TWEETS_PATH, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)

    print(f"[OK] 本日（{queue['date']}）の3投稿を保存しました:")
    for i, t in enumerate(cleaned):
        print(f"  [{i}] ({len(t)}字 / X換算{x_weighted_len(t)}字) {t}")
    print(f"[OK] queue.json を更新し、tweets.json に追記しました（総数 {len(pool)} 件）。")


if __name__ == "__main__":
    main()
