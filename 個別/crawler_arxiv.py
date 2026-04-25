import requests
import json
import time
import sys
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator

sys.stdout.reconfigure(encoding="utf-8")

API_URL = "https://export.arxiv.org/api/query"
OUTPUT_FILE = "trivia_arxiv.json"
CRAWL_COUNT = 10
INTERVAL_SEC = 3.0  # arXivのレート制限は3秒推奨
BATCH_SIZE = 5      # 1リクエストで取得する件数
TRANSLATE_WORKERS = 4

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

DELIM = "\n---SPLIT---\n"


def translate(text):
    if not text:
        return ""
    try:
        return GoogleTranslator(source="en", target="ja").translate(text[:4500])
    except Exception:
        return text


def fetch_batch(size, retries=5):
    for _ in range(retries):
        cat = random.choice(CATEGORIES)
        start = random.randint(0, 500)
        res = SESSION.get(API_URL, params={
            "search_query": f"cat:{cat}",
            "start": start,
            "max_results": size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        if res.status_code == 429:
            time.sleep(10)
            continue
        res.raise_for_status()
        entries = ET.fromstring(res.content).findall("atom:entry", NS)
        if entries:
            return entries
        time.sleep(3)
    return []


def translate_entry(entry):
    title = entry.findtext("atom:title", "", NS).replace("\n", " ").strip()
    abstract = entry.findtext("atom:summary", "", NS).replace("\n", " ").strip()
    url = entry.findtext("atom:id", "", NS).strip()
    authors = [a.findtext("atom:name", "", NS) for a in entry.findall("atom:author", NS)]
    categories = [c.get("term", "") for c in entry.findall("atom:category", NS)]

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
    print(f"{CRAWL_COUNT}件のランダム論文を取得します（arXiv 全ジャンル）...\n")

    # バッチ取得（リクエスト数を削減）
    all_entries = []
    num_batches = (CRAWL_COUNT + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(num_batches):
        if i > 0:
            time.sleep(INTERVAL_SEC)
        need = CRAWL_COUNT - len(all_entries)
        all_entries.extend(fetch_batch(min(BATCH_SIZE, need)))
        if len(all_entries) >= CRAWL_COUNT:
            break
    all_entries = all_entries[:CRAWL_COUNT]

    if not all_entries:
        print("取得失敗")
        return

    # 並列翻訳
    done = 0
    completed = [None] * len(all_entries)
    with ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS) as executor:
        futures = {executor.submit(translate_entry, e): i for i, e in enumerate(all_entries)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                paper = future.result()
                completed[i] = paper
                done += 1
                print(f"[{done}/{len(all_entries)}] {paper['title']}")
                print(f"  著者: {', '.join(paper['authors'])}")
                print(f"  カテゴリ: {', '.join(paper['categories'][:3])}")
                print(f"  {paper['abstract'][:80]}{'...' if len(paper['abstract']) > 80 else ''}\n")
            except Exception as e:
                done += 1
                print(f"[{done}/{len(all_entries)}] 翻訳失敗: {e}\n")

    results = [p for p in completed if p is not None]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了！{OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
