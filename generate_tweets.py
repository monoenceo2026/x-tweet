"""
株式会社モノエン 中村貴広（@monoenceo2026） 用 ツイート自動生成スクリプト。

毎朝6:00（JST）に GitHub Actions から実行され、Claude が「本日の3投稿」を生成する。

- 声・方針は voice_profile.md（人が編集できる）を中核プロンプトとして使う。
- Claude の Web検索ツールで、日本の製造業・ライブコマース・地方産業・スタートアップ採用
  まわりの最新トレンドを軽く確認し、無理なく投稿に活かす（トレンド分析）。
- 可能なら X API で @monoenceo2026 の直近ツイートを読み、口調の参考＆重複回避に使う
  （無料枠の制限などで取得できなければ、静的な声プロファイルにフォールバック）。
- 生成した3件を queue.json（本日分・当日投稿用）に書き出し、
  さらに tweets.json（蓄積アーカイブ兼・予備プール）にも追記する＝GitHub上でツイートが拡充される。

生成された投稿は post_tweet.py が朝8:00 / 昼12:00 / 夜20:00 に1件ずつ投稿する。
"""

import json
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

JST = ZoneInfo("Asia/Tokyo")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_PATH = os.path.join(BASE_DIR, "voice_profile.md")
TWEETS_PATH = os.path.join(BASE_DIR, "tweets.json")
QUEUE_PATH = os.path.join(BASE_DIR, "queue.json")

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
MAX_LEN = 140          # 日本語の1投稿の上限（ヒアリングシート準拠）
RECENT_FOR_DEDUP = 30  # 重複回避のために渡す直近アーカイブ件数
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

BANNED = ["絶対に成功", "誰でも簡単", "必ず儲か", "100%成功"]

OUTPUT_RULES = """\
------
【今日の出力タスク】
上のプロファイルに厳密に従い、中村貴広本人が書いたものとして、本日ぶんの X 投稿を「3件」作成してください。

- 3件は投稿される時間帯が異なります。次の並び順・トーンで作ってください。
  1件目（朝8:00枠）：ビジョン・価値観・覚悟、または一日の始まりに響く思想寄りの一本。
  2件目（昼12:00枠）：職人・工場・商品の物語、事業の裏側・進捗、またはブランディング／ライブコマースのノウハウ。
  3件目（夜20:00枠）：採用・仲間への呼びかけ、または日常・人間味。3件のうち少なくとも1件は採用（仲間募集）に関する内容にする。
- 各投稿は日本語で140文字以内。改行は使ってよいが多用しない。
- 3件はテーマも切り口も読後感も変える。互いに似せない。
- 「直近の投稿」（後述）と主張・言い回し・切り口が被らないようにする。
- ハッシュタグ・絵文字は原則なし（プロファイルの例外に従う）。画像前提の表現は禁止。
- Web検索は必要に応じてのみ使い、トレンドは無理に絡めず自然に。ニュースの又聞き実況にはしない。
  検索した固有名詞・数字・日付は必ず一次情報で裏取りできたものだけ使う。

【出力フォーマット】必ず次の形式だけを最後に出力すること（前置き・解説・番号・引用符は書かない）。
<tweet>1件目の本文</tweet>
<tweet>2件目の本文</tweet>
<tweet>3件目の本文</tweet>
"""


def load_voice():
    with open(VOICE_PATH, encoding="utf-8") as f:
        return f.read()


def load_pool():
    if not os.path.exists(TWEETS_PATH):
        return []
    with open(TWEETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def try_fetch_recent_tweets(limit=15):
    """
    X API で @monoenceo2026 の直近ツイートを best-effort で取得し、口調学習＆重複回避に使う。
    無料枠の読み取り制限・権限などで失敗しても致命的ではない（空リストを返す）。
    """
    needed = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    if not all(os.environ.get(k) for k in needed):
        return []
    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        me = client.get_me()
        uid = me.data.id
        resp = client.get_users_tweets(
            uid, max_results=max(5, min(limit, 100)), exclude=["retweets", "replies"]
        )
        if not resp or not resp.data:
            return []
        return [t.text for t in resp.data][:limit]
    except Exception as e:  # noqa: BLE001 - 読み取りは任意。失敗しても続行する。
        print(f"[INFO] 直近ツイートの取得はスキップしました（{type(e).__name__}: {e}）。"
              "静的な声プロファイルで生成します。")
        return []


def build_system(voice, recent_live, recent_archive):
    parts = [voice]
    if recent_live:
        joined = "\n".join(f"- {t}" for t in recent_live)
        parts.append(
            "------\n【本人の直近ツイート（口調・語彙・リズムの参考。内容は繰り返さない）】\n" + joined
        )
    if recent_archive:
        joined = "\n".join(f"- {t}" for t in recent_archive)
        parts.append(
            "------\n【最近このアカウントで作成済みの投稿（重複回避用。主張も切り口も被らせない）】\n" + joined
        )
    parts.append(OUTPUT_RULES)
    return "\n\n".join(parts)


def generate(system_prompt, now_jst):
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から読む
    tools = [{
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": 4,
        "user_location": {"type": "approximate", "country": "JP", "timezone": "Asia/Tokyo"},
    }]
    weekday = WEEKDAY_JP[now_jst.weekday()]
    user = (
        f"今日は {now_jst:%Y年%m月%d日}（{weekday}）です。"
        "本日ぶんの3投稿を、指示されたフォーマットで作成してください。"
    )

    messages = [{"role": "user", "content": user}]
    for _ in range(6):  # サーバーツール(web検索)の pause_turn を最大6回まで継続
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=system_prompt,
            tools=tools,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=messages,
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        if resp.stop_reason == "refusal":
            raise RuntimeError("生成が安全上の理由で拒否されました（refusal）。")
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text
    raise RuntimeError("web検索の pause_turn が続き、生成を完了できませんでした。")


def parse_tweets(text):
    return [m.strip() for m in re.findall(r"<tweet>(.*?)</tweet>", text, flags=re.DOTALL)]


def validate(candidates, existing):
    seen = set(existing)
    out = []
    for t in candidates:
        t = t.strip()
        if not t:
            continue
        if len(t) > MAX_LEN:
            print(f"[WARN] 140文字超のため除外（{len(t)}文字）: {t[:30]}…")
            continue
        if any(b in t for b in BANNED):
            print(f"[WARN] NG表現を含むため除外: {t[:30]}…")
            continue
        if t in seen:
            print(f"[WARN] 重複のため除外: {t[:30]}…")
            continue
        seen.add(t)
        out.append(t)
    return out


def main():
    now_jst = datetime.now(JST)
    voice = load_voice()
    pool = load_pool()
    recent_archive = pool[-RECENT_FOR_DEDUP:] if pool else []
    recent_live = try_fetch_recent_tweets()

    system_prompt = build_system(voice, recent_live, recent_archive)
    raw = generate(system_prompt, now_jst)
    candidates = parse_tweets(raw)

    if not candidates:
        print("[NG] 生成結果からツイートを抽出できませんでした。出力:\n" + raw)
        sys.exit(1)

    tweets = validate(candidates, existing=pool)
    if not tweets:
        print("[NG] 検証を通過したツイートがありませんでした。")
        sys.exit(1)

    tweets = tweets[:3]
    print(f"[OK] {len(tweets)}件のツイートを生成しました（model={MODEL}）:")
    for i, t in enumerate(tweets):
        print(f"  [{i}] ({len(t)}文字) {t}")

    # 本日分キュー（当日投稿用）
    queue = {
        "date": now_jst.strftime("%Y-%m-%d"),
        "generated_at": now_jst.isoformat(timespec="seconds"),
        "model": MODEL,
        "used_x_api": bool(recent_live),
        "tweets": tweets,
    }
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    # アーカイブ兼・予備プールに追記（＝GitHub上でツイートが拡充される）
    pool.extend(tweets)
    with open(TWEETS_PATH, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)

    print(f"[OK] queue.json を更新し、tweets.json に追記しました（総数 {len(pool)} 件）。")


if __name__ == "__main__":
    main()
