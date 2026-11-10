"""Find the sentence a word came from on a web page."""

from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "nav", "header", "footer"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skipping += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skipping:
            self._skipping -= 1

    def handle_data(self, data):
        if not self._skipping:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def fetch_text(url: str, timeout: float = 20.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 english-words/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return html_to_text(response.read().decode(charset, errors="replace"))


def find_sentence(text: str, word: str, max_len: int = 400) -> str | None:
    """The first sentence that uses the word (or a form of it, like 'words' or 'worded')."""
    pattern = re.compile(rf"\b{re.escape(word)}\w*\b", re.IGNORECASE)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if pattern.search(sentence) and len(sentence) <= max_len:
            return sentence.strip()
    return None
