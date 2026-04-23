import requests
import json
import time
import sys
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source="en", target="ja")


def translate(text):
    if not text:
        return ""
    try:
        return translator.translate(text[:4500])
    except Exception:
        return text

sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://export.arxiv.org/api/query"
OUTPUT_FILE = "trivia_arxiv.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 3.0  # arXivのレート制限は3秒推奨

CATEGORIES = [
    "cs", "math", "physics", "stat", "q-bio", "q-fin", "econ",
    "astro-ph", "cond-mat", "gr-qc", "hep-th", "quant-ph",
    "nlin", "eess",
]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "trivia-crawler/1.0"})


def fetch_random_paper(retries=5):
    for _ in range(retries):
        cat = random.choice(CATEGORIES)
        start = random.randint(0, 500)

        res = SESSION.get(API_URL, params={
            "search_query": f"cat:{cat}",
            "start": start,
            "max_results": 1,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        if res.status_code == 429:
            time.sleep(10)
            continue
        res.raise_for_status()

        root = ET.fromstring(res.content)
        entry = root.find("atom:entry", NS)
        if entry is not None:
            break
        time.sleep(3)
    else:
        return None

    title = entry.findtext("atom:title", "", NS).replace("\n", " ").strip()
    abstract = entry.findtext("atom:summary", "", NS).replace("\n", " ").strip()
    url = entry.findtext("atom:id", "", NS).strip()
    authors = [a.findtext("atom:name", "", NS) for a in entry.findall("atom:author", NS)]
    categories = [c.get("term", "") for c in entry.findall("atom:category", NS)]

    DELIM = "\n---SPLIT---\n"
    combined = translate(f"{title}{DELIM}{abstract}")
    if DELIM in combined:
        title_ja, abstract_ja = combined.split(DELIM, 1)
    else:
        title_ja, abstract_ja = translate(title), translate(abstract)

    return {
        "title": title_ja.strip(),
        "title_en": title,
        "authors": authors[:3],
        "abstract": abstract_ja.strip(),
        "categories": categories,
        "url": url,
        "fetched_at": datetime.now().isoformat(),
    }


def main():
    results = []
    print(f"{CRAWL_COUNT}件のランダム論文を取得します（arXiv 全ジャンル）...\n")

    for i in range(CRAWL_COUNT):
        paper = fetch_random_paper()
        if not paper:
            print(f"[{i+1}/{CRAWL_COUNT}] 取得失敗、スキップ\n")
            continue

        results.append(paper)
        print(f"[{i+1}/{CRAWL_COUNT}] {paper['title']}")
        print(f"  著者: {', '.join(paper['authors'])}")
        print(f"  カテゴリ: {', '.join(paper['categories'][:3])}")
        print(f"  {paper['abstract'][:80]}{'...' if len(paper['abstract']) > 80 else ''}\n")

        if i < CRAWL_COUNT - 1:
            time.sleep(INTERVAL_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
