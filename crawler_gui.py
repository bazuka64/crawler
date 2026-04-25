import tkinter as tk
from tkinter import ttk
import threading
import queue
import requests
import json
import time
import random
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

DELIM_ARXIV = "\n---SPLIT---\n"
DELIM_HN = "\n|||8675309|||\n"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
ARXIV_CATEGORIES = [
    "cs", "math", "physics", "stat", "q-bio", "q-fin", "econ",
    "astro-ph", "cond-mat", "gr-qc", "hep-th", "quant-ph", "nlin", "eess",
]


def _translate(text):
    if not text or not HAS_TRANSLATOR:
        return text
    try:
        return GoogleTranslator(source="en", target="ja").translate(text[:4500])
    except Exception:
        return text


def _short(s, n=80):
    return s[:n] + ("..." if len(s) > n else "")


# ── Wikipedia ──────────────────────────────────────────────────────────────────
def crawl_wiki(count, log):
    API_URL = "https://ja.wikipedia.org/api/rest_v1/page/random/summary"
    session = requests.Session()
    session.headers.update({"User-Agent": "trivia-crawler/1.0"})
    log(f"[Wikipedia] {count}件取得開始...\n")
    results = []
    for i in range(count):
        try:
            data = session.get(API_URL).json()
            article = {
                "title": data.get("title", ""),
                "summary": data.get("extract", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "fetched_at": datetime.utcnow().isoformat(),
            }
            results.append(article)
            log(f"[Wiki {i+1}/{count}] {article['title']}\n  {_short(article['summary'])}\n\n")
        except Exception as e:
            log(f"[Wiki {i+1}/{count}] エラー: {e}\n\n")
        if i < count - 1:
            time.sleep(1.0)
    with open("trivia_wiki.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("[Wikipedia] 完了！trivia_wiki.json に保存しました。\n\n")


# ── arXiv ──────────────────────────────────────────────────────────────────────
def crawl_arxiv(count, log):
    API_URL = "https://export.arxiv.org/api/query"
    BATCH_SIZE = 5
    session = requests.Session()
    session.headers.update({"User-Agent": "trivia-crawler/1.0"})
    log(f"[arXiv] {count}件取得開始...\n")

    def fetch_batch(size, retries=5):
        for _ in range(retries):
            cat = random.choice(ARXIV_CATEGORIES)
            res = session.get(API_URL, params={
                "search_query": f"cat:{cat}",
                "start": random.randint(0, 500),
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
        combined = _translate(f"{title}{DELIM_ARXIV}{abstract}")
        if DELIM_ARXIV in combined:
            title_ja, abstract_ja = combined.split(DELIM_ARXIV, 1)
        else:
            title_ja, abstract_ja = _translate(title), _translate(abstract)
        return {
            "title": title_ja.strip(),
            "title_en": title,
            "authors": authors[:3],
            "abstract": abstract_ja.strip(),
            "categories": categories,
            "url": url,
            "fetched_at": datetime.now().isoformat(),
        }

    all_entries = []
    for i in range((count + BATCH_SIZE - 1) // BATCH_SIZE):
        if i > 0:
            time.sleep(3.0)
        all_entries.extend(fetch_batch(min(BATCH_SIZE, count - len(all_entries))))
        if len(all_entries) >= count:
            break
    all_entries = all_entries[:count]

    if not all_entries:
        log("[arXiv] 取得失敗\n")
        return

    done = 0
    completed = [None] * len(all_entries)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(translate_entry, e): i for i, e in enumerate(all_entries)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                paper = future.result()
                completed[idx] = paper
                done += 1
                log(f"[arXiv {done}/{len(all_entries)}] {paper['title']}\n"
                    f"  著者: {', '.join(paper['authors'])}\n"
                    f"  {_short(paper['abstract'])}\n\n")
            except Exception as e:
                done += 1
                log(f"[arXiv {done}/{len(all_entries)}] 翻訳失敗: {e}\n\n")

    results = [p for p in completed if p is not None]
    with open("trivia_arxiv.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("[arXiv] 完了！trivia_arxiv.json に保存しました。\n\n")


# ── Hacker News ────────────────────────────────────────────────────────────────
def crawl_hackernews(count, log):
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    session = requests.Session()
    session.headers.update({"User-Agent": "trivia-crawler/1.0"})
    log(f"[HackerNews] {count}件取得開始...\n")

    def translate_combined(title, body):
        text = f"{title}{DELIM_HN}{body}" if body else title
        try:
            result = GoogleTranslator(source="en", target="ja").translate(text[:4500])
            if body and DELIM_HN in result:
                t, b = result.split(DELIM_HN, 1)
                return t.strip(), b.strip()
            return result.strip(), ""
        except Exception:
            return title, body

    ids = session.get(f"{BASE_URL}/beststories.json").json()
    sample_ids = random.sample(ids[:500], min(count, len(ids[:500])))
    results = []

    for i, item_id in enumerate(sample_ids):
        try:
            item = session.get(f"{BASE_URL}/item/{item_id}.json").json()
            if not item or item.get("type") != "story":
                log(f"[HN {i+1}/{count}] スキップ\n\n")
                continue
            title_en = item.get("title", "").strip()
            body_en = re.sub(r'<[^>]+>', '', html.unescape(item.get("text", ""))).strip()
            url = item.get("url", f"https://news.ycombinator.com/item?id={item_id}")
            score = item.get("score", 0)
            title_ja, body_ja = translate_combined(title_en, body_en) if HAS_TRANSLATOR else (title_en, body_en)
            results.append({
                "title": title_ja,
                "title_en": title_en,
                "body": body_ja,
                "score": score,
                "by": item.get("by", ""),
                "url": url,
                "fetched_at": datetime.now().isoformat(),
            })
            log(f"[HN {i+1}/{count}] {title_ja}  (score: {score})\n"
                f"  {_short(body_ja) if body_ja else ''}\n\n")
        except Exception as e:
            log(f"[HN {i+1}/{count}] エラー: {e}\n\n")
        if i < count - 1:
            time.sleep(0.5)

    with open("trivia_hackernews.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("[HackerNews] 完了！trivia_hackernews.json に保存しました。\n\n")


# ── チャクウィキ ────────────────────────────────────────────────────────────────
def crawl_chakuwiki(count, log):
    BASE_URL = "https://chakuwiki.org/api.php"
    session = requests.Session()
    session.headers.update({"User-Agent": "trivia-crawler/1.0"})
    log(f"[チャクウィキ] {count}件取得開始...\n")
    results = []
    for i in range(count):
        try:
            title = session.get(BASE_URL, params={
                "action": "query", "list": "random",
                "rnnamespace": 0, "rnlimit": 1, "format": "json",
            }).json()["query"]["random"][0]["title"]
            pages = session.get(BASE_URL, params={
                "action": "query", "prop": "extracts",
                "exintro": True, "explaintext": True,
                "titles": title, "format": "json",
            }).json()["query"]["pages"]
            summary = next(iter(pages.values())).get("extract", "")
            url = f"https://chakuwiki.org/wiki/{requests.utils.quote(title)}"
            results.append({"title": title, "summary": summary, "url": url, "fetched_at": datetime.now().isoformat()})
            log(f"[チャクウィキ {i+1}/{count}] {title}\n  {_short(summary)}\n\n")
        except Exception as e:
            log(f"[チャクウィキ {i+1}/{count}] エラー: {e}\n\n")
        if i < count - 1:
            time.sleep(1.0)
    with open("trivia_chakuwiki.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("[チャクウィキ] 完了！trivia_chakuwiki.json に保存しました。\n\n")


# ── Wikibooks ──────────────────────────────────────────────────────────────────
def crawl_wikibooks(count, log):
    BASE_URL = "https://ja.wikibooks.org/w/api.php"
    session = requests.Session()
    session.headers.update({"User-Agent": "trivia-crawler/1.0"})
    log(f"[Wikibooks] {count}件取得開始...\n")
    results = []
    for i in range(count):
        try:
            title = session.get(BASE_URL, params={
                "action": "query", "list": "random",
                "rnnamespace": 0, "rnlimit": 1, "format": "json",
            }).json()["query"]["random"][0]["title"]
            pages = session.get(BASE_URL, params={
                "action": "query", "prop": "extracts",
                "exintro": True, "explaintext": True,
                "titles": title, "format": "json",
            }).json()["query"]["pages"]
            summary = next(iter(pages.values())).get("extract", "")
            url = f"https://ja.wikibooks.org/wiki/{requests.utils.quote(title)}"
            results.append({"title": title, "summary": summary, "url": url, "fetched_at": datetime.now().isoformat()})
            log(f"[Wikibooks {i+1}/{count}] {title}\n  {_short(summary)}\n\n")
        except Exception as e:
            log(f"[Wikibooks {i+1}/{count}] エラー: {e}\n\n")
        if i < count - 1:
            time.sleep(1.0)
    with open("trivia_wikibooks.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("[Wikibooks] 完了！trivia_wikibooks.json に保存しました。\n\n")


# ── Mario 64 Hacks ─────────────────────────────────────────────────────────────
def crawl_mario64hacks(count, log):
    BASE_URL = "https://mario64hacks.fandom.com/api.php"
    session = requests.Session()
    session.headers.update({"User-Agent": "trivia-crawler/1.0"})
    log(f"[Mario64Hacks] {count}件取得開始...\n")

    def wikitext_to_plain(text):
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)
        text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
        text = re.sub(r"'{2,3}", '', text)
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    results = []
    for i in range(count):
        try:
            title = session.get(BASE_URL, params={
                "action": "query", "list": "random",
                "rnnamespace": 0, "rnlimit": 1, "format": "json",
            }).json()["query"]["random"][0]["title"]
            page = next(iter(session.get(BASE_URL, params={
                "action": "query", "prop": "revisions",
                "rvslots": "*", "rvprop": "content",
                "titles": title, "format": "json",
            }).json()["query"]["pages"].values()))
            raw = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
            plain = wikitext_to_plain(raw)
            match = re.search(r'[^.!?]+[.!?]', plain)
            summary = match.group(0).strip() if match else plain[:120]
            url = f"https://mario64hacks.fandom.com/wiki/{requests.utils.quote(title.replace(' ', '_'))}"
            results.append({"title": title, "summary": summary, "url": url, "fetched_at": datetime.now().isoformat()})
            log(f"[Mario64Hacks {i+1}/{count}] {title}\n  {_short(summary)}\n\n")
        except Exception as e:
            log(f"[Mario64Hacks {i+1}/{count}] エラー: {e}\n\n")
        if i < count - 1:
            time.sleep(1.0)
    with open("trivia_mario64hacks.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("[Mario64Hacks] 完了！trivia_mario64hacks.json に保存しました。\n\n")


# ── GUI ────────────────────────────────────────────────────────────────────────

CRAWLERS = [
    ("Wikipedia",     crawl_wiki),
    ("arXiv",         crawl_arxiv),
    ("Hacker News",   crawl_hackernews),
    ("チャクウィキ",   crawl_chakuwiki),
    ("Wikibooks",     crawl_wikibooks),
    ("Mario64 Hacks", crawl_mario64hacks),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Trivia Crawler")
        self.minsize(620, 520)
        self._queue = queue.Queue()
        self._active = 0
        self._lock = threading.Lock()
        self._build_ui()
        self._poll()

    def _build_ui(self):
        # ── Crawler checkboxes ──
        cb_frame = ttk.LabelFrame(self, text="クローラー選択")
        cb_frame.pack(fill="x", padx=10, pady=(10, 4))

        self._vars = []
        for i, (name, _) in enumerate(CRAWLERS):
            var = tk.BooleanVar(value=True)
            self._vars.append(var)
            ttk.Checkbutton(cb_frame, text=name, variable=var).grid(
                row=i // 3, column=i % 3, sticky="w", padx=10, pady=3
            )

        # ── Controls ──
        ctrl = ttk.Frame(self)
        ctrl.pack(fill="x", padx=10, pady=4)

        ttk.Label(ctrl, text="取得件数:").pack(side="left")
        self._count_var = tk.IntVar(value=10)
        ttk.Spinbox(ctrl, from_=1, to=500, textvariable=self._count_var, width=7).pack(side="left", padx=6)

        ttk.Button(ctrl, text="全選択", command=lambda: [v.set(True) for v in self._vars]).pack(side="left", padx=(12, 2))
        ttk.Button(ctrl, text="全解除", command=lambda: [v.set(False) for v in self._vars]).pack(side="left", padx=2)
        ttk.Button(ctrl, text="ログをクリア", command=self._clear_log).pack(side="left", padx=(12, 2))

        self._start_btn = ttk.Button(ctrl, text="▶ クロール開始", command=self._start)
        self._start_btn.pack(side="right")

        # ── Log area ──
        log_frame = ttk.LabelFrame(self, text="ログ")
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self._log = tk.Text(log_frame, wrap="word", state="disabled", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=2, pady=2)

        # ── Status bar ──
        self._status = tk.StringVar(value="待機中")
        ttk.Label(self, textvariable=self._status, relief="sunken", anchor="w").pack(
            fill="x", padx=10, pady=(0, 6)
        )

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _append(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg is None:
                    with self._lock:
                        self._active -= 1
                        if self._active == 0:
                            self._start_btn.configure(state="normal")
                            self._status.set("完了")
                else:
                    self._append(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _start(self):
        selected = [(name, fn) for (name, fn), var in zip(CRAWLERS, self._vars) if var.get()]
        if not selected:
            return
        count = self._count_var.get()
        self._start_btn.configure(state="disabled")
        self._status.set(f"実行中... ({len(selected)} クローラー)")

        with self._lock:
            self._active = len(selected)

        for name, fn in selected:
            def worker(fn=fn):
                def log(text):
                    self._queue.put(text)
                try:
                    fn(count, log)
                except Exception as e:
                    self._queue.put(f"[エラー] {e}\n")
                finally:
                    self._queue.put(None)
            threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
