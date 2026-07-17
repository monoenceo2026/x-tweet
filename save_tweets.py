"""
「本日の3投稿」を保存する検証・永続化ヘルパー（LLM/API不要）。

ツイート本文の生成は Claude Code のルーチン（＝Claudeのサブスク）が行い、
考えた3件をこのスクリプトに渡して保存する。ここでは生成せず、検証と保存だけを行う:

  - 140文字以内か、NG表現を含まないか、既存と重複しないかを検証
  - 本日分の queue.json（朝・昼・夜の3件）を書き出す
  - tweets.json（蓄積アーカイブ兼・予備プール）に追記する＝GitHub上でツイートが拡充される

使い方（どちらでも可）:
  python save_tweets.py "朝の1件" "昼の1件" "夜の1件"
  echo '["朝の1件","昼の1件","夜の1件"]' | python save_tweets.py

検証に通らない要素があれば、理由を表示して終了コード2で終わる（呼び出し側で直して再実行）。
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TWEETS_PATH = os.path.join(BASE_DIR, "tweets.json")
QUEUE_PATH = os.path.join(BASE_DIR, "queue.json")

MAX_LEN = 140
EXPECTED = 3
BANNED = ["絶対に成功", "誰でも簡単", "必ず儲か", "100%成功"]


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
    cleaned = []
    for i, t in enumerate(tweets):
        t = t.strip()
        if not t:
            errors.append(f"[{i}] 空です。")
            continue
        if len(t) > MAX_LEN:
            errors.append(f"[{i}] 140文字超（{len(t)}文字）: {t[:30]}…")
            continue
        hit = next((b for b in BANNED if b in t), None)
        if hit:
            errors.append(f"[{i}] NG表現「{hit}」を含む: {t[:30]}…")
            continue
        if t in seen:
            errors.append(f"[{i}] 既存の投稿と重複: {t[:30]}…")
            continue
        seen.add(t)
        cleaned.append(t)
    return cleaned, errors


def main():
    tweets = read_input_tweets()
    if not tweets:
        print("使い方: python save_tweets.py \"朝の1件\" \"昼の1件\" \"夜の1件\"")
        sys.exit(2)

    pool = load_pool()
    cleaned, errors = validate(tweets, pool)

    if errors:
        print("[NG] 次の要素が検証に通りませんでした。修正して再実行してください:")
        for e in errors:
            print("  " + e)
        sys.exit(2)

    if len(cleaned) != EXPECTED:
        print(f"[NG] 3件ちょうど渡してください（受領: {len(cleaned)}件）。")
        sys.exit(2)

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
        print(f"  [{i}] ({len(t)}文字) {t}")
    print(f"[OK] queue.json を更新し、tweets.json に追記しました（総数 {len(pool)} 件）。")


if __name__ == "__main__":
    main()
