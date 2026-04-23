import requests
import json
import time
import sys
from datetime import datetime
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

RANDOM_URL = "https://ja.uncyclopedia.info/wiki/Special:Random"
OUTPUT_FILE = "trivia_a_ansaikuro.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 1.5

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
})


def fetch_random_article():
    res = SESSION.get(RANDOM_URL, allow_redirects=True)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    title = soup.find("h1", id="firstHeading")
    title = title.get_text(strip=True) if title else "不明"

    content_div = soup.find("div", id="mw-content-text")
    summary = ""
    if content_div:
        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                summary = text
                break

    return {
        "title": title,
        "summary": summary,
        "url": res.url,
        "fetched_at": datetime.now().isoformat(),
    }


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム記事を取得します（アンサイクロペディア）...\n")

    for i in range(CRAWL_COUNT):
        article = fetch_random_article()
        results.append(article)

        print(f"[{i+1}/{CRAWL_COUNT}] {article['title']}")
        print(f"  {article['summary'][:80]}{'...' if len(article['summary']) > 80 else ''}\n")

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
