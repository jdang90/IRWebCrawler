# analytics.py
import atexit
from collections import Counter, defaultdict
from threading import Lock
from urllib.parse import urldefrag, urlparse

class Analytics:
    def __init__(self, min_words=50, report_path="crawl_report.txt"):
        self.lock = Lock()
        self.min_words = min_words
        self.report_path = report_path

        self.unique_urls = set()          # defrag URL uniqueness
        self.word_freq = Counter()        # global word counts
        self.longest_url = None
        self.longest_word_count = 0
        self.subdomain_pages = defaultdict(set)  # hostname -> set(urls)

        atexit.register(self.write_report)

    def defrag(self, url: str) -> str:
        return urldefrag(url)[0]

    def hostname(self, url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    def clean_tokens(self, tokens: list[str]) -> list[str]:
        # teep behavior aligned with scraper tokens, but remove obvious junk
        cleaned = []
        for t in tokens:
            t = (t or "").lower()
            if not t:
                continue
            if t.isnumeric():     # removes "2025", "123", etc.
                continue
            if len(t) <= 1:       # removes "x", "1", etc.
                continue
            cleaned.append(t)
        return cleaned

    def add_page(self, url: str, *, tokens: list[str]):
        if not url:
            return

        url = self.defrag(url)
        tokens = self.clean_tokens(tokens)
        if len(tokens) < self.min_words:
            return

        with self.lock:
            if url in self.unique_urls:
                return
            self.unique_urls.add(url)

            wc = len(tokens)
            if wc > self.longest_word_count:
                self.longest_word_count = wc
                self.longest_url = url

            self.word_freq.update(tokens)

            host = self.hostname(url)
            if host and host.endswith(".uci.edu"):
                self.subdomain_pages[host].add(url)

    def write_report(self):
        try:
            with self.lock:
                unique_pages = len(self.unique_urls)
                longest_url = self.longest_url
                longest_wc = self.longest_word_count
                top50 = self.word_freq.most_common(50)
                subs = sorted(
                    [(sd, len(urls)) for sd, urls in self.subdomain_pages.items()],
                    key=lambda x: x[0]
                )

            lines = []
            lines.append(f"Unique pages: {unique_pages}")
            lines.append(f"Longest page: {longest_url}, {longest_wc}")
            lines.append("")
            lines.append("Top 50 words (word, count):")
            for w, c in top50:
                lines.append(f"{w}, {c}")
            lines.append("")
            lines.append("Subdomains (alphabetical) and unique page counts:")
            for sd, c in subs:
                lines.append(f"{sd}, {c}")

            with open(self.report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

analytics = Analytics()
