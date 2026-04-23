import requests
import json
import time
import sys
import random
import html
import re
from datetime import datetime
from deep_translator import GoogleTranslator

sys.stdout.reconfigure(encoding="utf-8")

translator = GoogleTranslator(source="en", target="ja")
DELIM = "\n|||8675309|||\n"

BASE_URL = "https://hacker-news.firebaseio.com/v0"
OUTPUT_FILE = "trivia_hackernews.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 0.5

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "trivia-crawler/1.0"})


def translate_combined(title, body):
    text = f"{title}{DELIM}{body}" if body else title
    try:
        result = translator.translate(text[:4500])
        if body and DELIM in result:
            t, b = result.split(DELIM, 1)
            return t.strip(), b.strip()
        return result.strip(), ""
    except Exception:
        return title, body


def fetch_story_ids():
    res = SESSION.get(f"{BASE_URL}/beststories.json")
    res.raise_for_status()
    return res.json()


def fetch_item(item_id):
    res = SESSION.get(f"{BASE_URL}/item/{item_id}.json")
    res.raise_for_status()
    return res.json()


def main():
    print("ストーリーIDを取得中...\n")
    ids = fetch_story_ids()
    sample_ids = random.sample(ids[:500], CRAWL_COUNT)

    results = []
    print(f"{CRAWL_COUNT}件のランダム記事を取得します（Hacker News）...\n")

    for i, item_id in enumerate(sample_ids):
        item = fetch_item(item_id)
        if not item or item.get("type") != "story":
            print(f"[{i+1}/{CRAWL_COUNT}] スキップ\n")
            continue

        title_en = item.get("title", "").strip()
        body_en = re.sub(r'<[^>]+>', '', html.unescape(item.get("text", ""))).strip()
        url = item.get("url", f"https://news.ycombinator.com/item?id={item_id}")
        score = item.get("score", 0)
        by = item.get("by", "")

        title_ja, body_ja = translate_combined(title_en, body_en)

        results.append({
            "title": title_ja,
            "title_en": title_en,
            "body": body_ja,
            "score": score,
            "by": by,
            "url": url,
            "fetched_at": datetime.now().isoformat(),
        })

        print(f"[{i+1}/{CRAWL_COUNT}] {title_ja}  (score: {score})")
        if body_ja:
            print(f"  {body_ja[:80]}{'...' if len(body_ja) > 80 else ''}")
        print()

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
