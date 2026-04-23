import requests
import json
import time
import sys
from datetime import datetime
from deep_translator import GoogleTranslator

sys.stdout.reconfigure(encoding="utf-8")

translator = GoogleTranslator(source="en", target="ja")
DELIM = "\n---SPLIT---\n"

import random

BASE_URL = "https://www.reddit.com"
OUTPUT_FILE = "trivia_reddit.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 1.0

SUBREDDITS = [
    "todayilearned", "science", "worldnews", "history", "space",
    "explainlikeimfive", "askscience", "futurology", "technology",
    "philosophy", "psychology", "economics", "math", "programming",
    "biology", "chemistry", "physics", "linguistics", "geopolitics",
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "trivia-crawler/1.0"})


def translate_combined(title, body):
    if not body:
        try:
            return translator.translate(title[:4500]), ""
        except Exception:
            return title, ""
    combined = f"{title}{DELIM}{body}"
    try:
        result = translator.translate(combined[:4500])
        if DELIM in result:
            t, b = result.split(DELIM, 1)
            return t.strip(), b.strip()
        return result.strip(), ""
    except Exception:
        return title, body


def fetch_random_post():
    subreddit = random.choice(SUBREDDITS)
    res = SESSION.get(f"{BASE_URL}/r/{subreddit}/random.json", allow_redirects=True)
    res.raise_for_status()
    data = res.json()
    posts = data[0]["data"]["children"]
    if not posts:
        return None
    post = posts[0]["data"]
    subreddit = post.get("subreddit", "")
    title_en = post.get("title", "").strip()
    body_en = post.get("selftext", "").strip()
    url = BASE_URL + post.get("permalink", "")
    score = post.get("score", 0)

    title_ja, body_ja = translate_combined(title_en, body_en)

    return {
        "title": title_ja,
        "title_en": title_en,
        "body": body_ja,
        "subreddit": subreddit,
        "score": score,
        "url": url,
        "fetched_at": datetime.now().isoformat(),
    }


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム投稿を取得します（Reddit）...\n")

    for i in range(CRAWL_COUNT):
        try:
            post = fetch_random_post()
        except Exception as e:
            print(f"[{i+1}/{CRAWL_COUNT}] 取得失敗: {e}\n")
            continue
        if not post:
            print(f"[{i+1}/{CRAWL_COUNT}] 投稿なし、スキップ\n")
            continue

        results.append(post)
        print(f"[{i+1}/{CRAWL_COUNT}] r/{post['subreddit']} | {post['title']}")
        body_preview = post["body"][:80] if post["body"] else "(本文なし)"
        print(f"  {body_preview}{'...' if len(post['body']) > 80 else ''}\n")

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
