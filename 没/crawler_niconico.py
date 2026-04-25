import requests
import json
import time
import sys
import random
from urllib.parse import unquote
from datetime import datetime
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dic.nicovideo.jp"
START_ARTICLE = "/a/初音ミク"
OUTPUT_FILE = "trivia_niconico.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 1.5

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
})


def fetch_article(path):
    res = SESSION.get(BASE + path, allow_redirects=True)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else unquote(path.replace("/a/", ""))
    # h1に「単語」「動画」などの種別ラベルが混入するので除去
    for span in h1.find_all("span") if h1 else []:
        span.decompose()
    title = h1.get_text(strip=True) if h1 else title

    summary = ""
    article_div = soup.find("div", id="article")
    if article_div:
        for p in article_div.find_all("p"):
            text = p.get_text(strip=True)
            if text and len(text) > 10:
                summary = text
                break
        # pタグがなければliも見る
        if not summary:
            for li in article_div.find_all("li"):
                text = li.get_text(strip=True)
                if text and len(text) > 10:
                    summary = text
                    break

    # 次に飛ぶ候補リンクを収集
    next_links = []
    if article_div:
        next_links = [a["href"] for a in article_div.find_all("a", href=True)
                      if a["href"].startswith("/a/")]

    return title, summary, res.url, next_links


def main():
    results = []
    visited = set()
    current_path = START_ARTICLE

    print(f"{CRAWL_COUNT}件を巡回します（ニコニコ大百科 ランダムウォーク）...\n")

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

        # 未訪問リンクからランダムに次を選ぶ
        unvisited = [l for l in next_links if l not in visited]
        if not unvisited:
            unvisited = next_links  # 全部訪問済みなら再訪も許可
        current_path = random.choice(unvisited) if unvisited else START_ARTICLE

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
