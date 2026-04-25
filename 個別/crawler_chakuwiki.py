import requests
import json
import time
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://chakuwiki.org/api.php"
OUTPUT_FILE = "trivia_chakuwiki.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 1.0

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "trivia-crawler/1.0"})


def fetch_random_title():
    res = SESSION.get(BASE_URL, params={
        "action": "query",
        "list": "random",
        "rnnamespace": 0,
        "rnlimit": 1,
        "format": "json",
    })
    res.raise_for_status()
    return res.json()["query"]["random"][0]["title"]


def fetch_summary(title):
    res = SESSION.get(BASE_URL, params={
        "action": "query",
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "titles": title,
        "format": "json",
    })
    res.raise_for_status()
    pages = res.json()["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("extract", "")


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム記事を取得します（チャクウィキ）...\n")

    for i in range(CRAWL_COUNT):
        title = fetch_random_title()
        summary = fetch_summary(title)
        url = f"https://chakuwiki.org/wiki/{requests.utils.quote(title)}"

        results.append({
            "title": title,
            "summary": summary,
            "url": url,
            "fetched_at": datetime.now().isoformat(),
        })

        print(f"[{i+1}/{CRAWL_COUNT}] {title}")
        print(f"  {summary[:80]}{'...' if len(summary) > 80 else ''}\n")

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
