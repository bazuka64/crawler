import requests
import json
import time
import sys
import random
from urllib.parse import unquote
from datetime import datetime
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dic.pixiv.net"
START_ARTICLE = "/a/初音ミク"
OUTPUT_FILE = "trivia_pixiv.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 1.5

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
})

SKIP_PHRASES = ("pixivで", "pixiv で", "投稿する", "見る", "読む")


def fetch_article(path):
    res = SESSION.get(BASE + path, allow_redirects=True)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else unquote(path.replace("/a/", ""))

    summary = ""
    article = soup.find("article")
    if article:
        # 「概要」見出し以降のpを優先、なければ全体から探す
        gaiyou = article.find(lambda t: t.name in ("h2", "h3") and "概要" in t.get_text())
        search_scope = gaiyou.find_all_next("p") if gaiyou else article.find_all("p")
        for p in search_scope:
            text = p.get_text(strip=True)
            if text and len(text) > 15 and not any(s in text for s in SKIP_PHRASES):
                summary = text
                break

    next_links = []
    if article:
        next_links = [
            a["href"] for a in article.find_all("a", href=True)
            if a["href"].startswith("/a/") and not a["href"].startswith("/a/Special")
        ]

    return title, summary, res.url, next_links


def main():
    results = []
    visited = set()
    current_path = START_ARTICLE

    print(f"{CRAWL_COUNT}件を巡回します（ピクシブ百科事典 ランダムウォーク）...\n")

    for i in range(CRAWL_COUNT):
        title, summary, url, next_links = fetch_article(current_path)
        visited.add(current_path)

        results.append({
            "title": title,
            "summary": summary,
            "url": url,
            "fetched_at": datetime.now().isoformat(),
        })

        print(f"[{i+1}/{CRAWL_COUNT}] {title}")
        print(f"  {summary[:80]}{'...' if len(summary) > 80 else ''}\n")

        unvisited = [l for l in next_links if l not in visited]
        current_path = random.choice(unvisited if unvisited else next_links or [START_ARTICLE])

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
