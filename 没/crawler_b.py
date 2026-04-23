import requests
import json
import time
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://ja.wikipedia.org/w/api.php"
OUTPUT_FILE = "trivia_b.json"
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


def fetch_article(title):
    res = SESSION.get(BASE_URL, params={
        "action": "query",
        "prop": "extracts|categories",
        "exintro": True,
        "explaintext": True,
        "cllimit": 10,
        "clshow": "!hidden",  # 管理用の隠しカテゴリを除外
        "titles": title,
        "format": "json",
    })
    res.raise_for_status()
    page = next(iter(res.json()["query"]["pages"].values()))

    summary = page.get("extract", "")
    raw_cats = page.get("categories", [])
    categories = [c["title"].replace("Category:", "").replace("カテゴリ:", "") for c in raw_cats]

    return summary, categories


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム記事を取得します（Wikipedia日本語版 + カテゴリ）...\n")

    for i in range(CRAWL_COUNT):
        title = fetch_random_title()
        summary, categories = fetch_article(title)
        url = f"https://ja.wikipedia.org/wiki/{requests.utils.quote(title)}"

        results.append({
            "title": title,
            "summary": summary,
            "categories": categories,
            "url": url,
            "fetched_at": datetime.now().isoformat(),
        })

        print(f"[{i+1}/{CRAWL_COUNT}] {title}")
        print(f"  カテゴリ: {', '.join(categories) if categories else 'なし'}")
        print(f"  {summary[:60]}{'...' if len(summary) > 60 else ''}\n")

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
