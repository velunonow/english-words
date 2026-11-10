"""Read and write word notes: Markdown files with YAML frontmatter.

A word note looks like this in Obsidian:

    ---
    word: serendipity
    part_of_speech: noun
    meaning: finding something good without looking for it
    added: 2026-11-10
    due: 2026-11-11
    interval: 0
    ease: 2.5
    repetitions: 0
    tags: [vocab]
    ---
    # serendipity

    **noun** · finding something good without looking for it

    ## My sentences
    - It was pure serendipity that we met. ([source](https://...)) · 2026-11-10

    ## Dictionary examples
    - ...

    ## Review log
    - 2026-11-11 good, next 2026-11-17
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .sm2 import ReviewState

MY_SENTENCES = "My sentences"
EXAMPLES = "Dictionary examples"
REVIEW_LOG = "Review log"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


@dataclass
class Note:
    """Any Markdown note with frontmatter (word notes and review notes)."""

    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""

    @classmethod
    def load(cls, path: Path) -> "Note":
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER.match(text)
        if not match:
            return cls(path, {}, text)
        meta = yaml.safe_load(match.group(1)) or {}
        return cls(path, meta, text[match.end():])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        front = yaml.safe_dump(self.meta, sort_keys=False, allow_unicode=True).strip()
        self.path.write_text(f"---\n{front}\n---\n{self.body}", encoding="utf-8")

    # --- sections -----------------------------------------------------------

    def section_items(self, heading: str) -> list[str]:
        """The bullet lines under a '## heading', without the leading '- '."""
        return [line[2:] for line in _section_lines(self.body, heading) if line.startswith("- ")]

    def append_to_section(self, heading: str, line: str) -> None:
        """Add a line at the end of a '## heading' section (creating it if missing)."""
        lines = self.body.rstrip("\n").split("\n")
        start = _find_heading(lines, heading)
        if start is None:
            self.body = self.body.rstrip("\n") + f"\n\n## {heading}\n{line}\n"
            return
        end = start + 1
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        # Insert after the last non-blank line of the section.
        insert_at = end
        while insert_at > start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines.insert(insert_at, line)
        self.body = "\n".join(lines) + "\n"


def _find_heading(lines: list[str], heading: str) -> int | None:
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            return i
    return None


def _section_lines(body: str, heading: str) -> list[str]:
    lines = body.split("\n")
    start = _find_heading(lines, heading)
    if start is None:
        return []
    out = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


# --- word notes -------------------------------------------------------------


def word_path(words_dir: Path, word: str) -> Path:
    safe = re.sub(r'[\\/:*?"<>|]', "-", word)
    return words_dir / f"{safe}.md"


def format_sentence(sentence: str, source: str | None, on: date) -> str:
    sentence = " ".join(sentence.split())
    src = f" ([source]({source}))" if source else ""
    return f"{sentence}{src} · {on.isoformat()}"


def new_word_note(
    path: Path,
    word: str,
    part_of_speech: str,
    meaning: str,
    my_sentence: str,
    examples: list[str],
    added: date,
    state: ReviewState,
) -> Note:
    meta = {
        "word": word,
        "part_of_speech": part_of_speech,
        "meaning": meaning,
        "added": added,
        **state_to_meta(state),
        "tags": ["vocab"],
    }
    headline = f"**{part_of_speech}** · {meaning}" if part_of_speech else meaning
    example_lines = "\n".join(f"- {e}" for e in examples) or "_(none found yet)_"
    body = (
        f"# {word}\n\n"
        f"{headline}\n\n"
        f"## {MY_SENTENCES}\n- {my_sentence}\n\n"
        f"## {EXAMPLES}\n{example_lines}\n\n"
        f"## {REVIEW_LOG}\n"
    )
    return Note(path, meta, body)


def state_to_meta(state: ReviewState) -> dict:
    return {
        "due": state.due,
        "interval": state.interval,
        "ease": state.ease,
        "repetitions": state.repetitions,
    }


def state_from_meta(meta: dict) -> ReviewState:
    return ReviewState(
        due=_as_date(meta["due"]),
        interval=int(meta.get("interval", 0)),
        ease=float(meta.get("ease", 2.5)),
        repetitions=int(meta.get("repetitions", 0)),
    )


def _as_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))
