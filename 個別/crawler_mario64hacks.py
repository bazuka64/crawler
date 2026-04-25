import requests
import json
import time
import sys
import re
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://mario64hacks.fandom.com/api.php"
OUTPUT_FILE = "trivia_mario64hacks.json"
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


def wikitext_to_plain(text):
    text = re.sub(r'\{\{[^{}]*\}\}', '', text)       # {{テンプレート}} 除去
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)  # [[リンク]] → 表示テキスト
    text = re.sub(r"'{2,3}", '', text)                # '''太字''' 除去
    text = re.sub(r'<[^>]+>', '', text)               # HTMLタグ除去
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_summary(title):
    res = SESSION.get(BASE_URL, params={
        "action": "query",
        "prop": "revisions",
        "rvslots": "*",
        "rvprop": "content",
        "titles": title,
        "format": "json",
    })
    res.raise_for_status()
    page = next(iter(res.json()["query"]["pages"].values()))
    raw = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
    plain = wikitext_to_plain(raw)
    # 最初の文（ピリオドまで）を返す
    match = re.search(r'[^.!?]+[.!?]', plain)
    return match.group(0).strip() if match else plain[:120]


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム記事を取得します（Mario 64 Hacks Wiki）...\n")

    for i in range(CRAWL_COUNT):
        title = fetch_random_title()
        summary = fetch_summary(title)
        url = f"https://mario64hacks.fandom.com/wiki/{requests.utils.quote(title.replace(' ', '_'))}"

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
