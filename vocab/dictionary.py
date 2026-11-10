"""Look a word up in the Free Dictionary API (https://dictionaryapi.dev, no key needed)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"


@dataclass
class Sense:
    """One meaning of a word, with the dictionary's own examples for it."""

    part_of_speech: str
    definition: str
    examples: list[str] = field(default_factory=list)


def parse_entries(data: list[dict]) -> list[Sense]:
    senses: list[Sense] = []
    for entry in data:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "")
            for d in meaning.get("definitions", []):
                example = d.get("example")
                senses.append(Sense(pos, d.get("definition", ""), [example] if example else []))
    return senses


def lookup(word: str, timeout: float = 15.0) -> list[Sense]:
    """All senses of a word, or an empty list if the dictionary doesn't know it."""
    url = API_URL.format(word=urllib.parse.quote(word))
    request = urllib.request.Request(url, headers={"User-Agent": "english-words/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse_entries(json.load(response))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return []
        raise
