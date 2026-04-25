import requests
import json
import time
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://ja.wikipedia.org/api/rest_v1/page/random/summary"
OUTPUT_FILE = "trivia_wiki.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 1.0  # Wikipedia APIの礼儀として1秒待つ


def fetch_random_article():
    res = requests.get(API_URL, headers={"User-Agent": "trivia-crawler/1.0"})
    res.raise_for_status()
    data = res.json()
    return {
        "title": data.get("title", ""),
        "summary": data.get("extract", ""),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "fetched_at": datetime.utcnow().isoformat(),
    }


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム記事を取得します...\n")

    for i in range(CRAWL_COUNT):
        article = fetch_random_article()
        results.append(article)
        print(f"[{i+1}/{CRAWL_COUNT}] {article['title']}")
        print(f"  {article['summary'][:80]}{'...' if len(article['summary']) > 80 else ''}\n")
        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
