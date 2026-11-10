"""The morning review: apply yesterday's ticks, then list what's due today.

A review note has one section per due word. You read your own sentence, try to
recall the meaning, open the folded answer, and tick one box: again, hard, good
or easy. The next `vocab review` reads those ticks and reschedules each word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import Vault
from .notes import EXAMPLES, MY_SENTENCES, REVIEW_LOG, Note, state_from_meta, state_to_meta, word_path
from .sm2 import GRADES, schedule

_HEADING = re.compile(r"^## (.+?)\s*$")
_TICKED = re.compile(r"^- \[[xX]\] (again|hard|good|easy)\b")
_ADDED_ON = re.compile(r" · \d{4}-\d{2}-\d{2}$")  # the date suffix on "My sentences" lines


@dataclass
class ReviewResult:
    path: Path | None  # today's review note, or None if nothing is due
    due_count: int
    applied: list[tuple[str, str]]  # (word, grade) applied from earlier notes
    already_existed: bool = False


def read_grades(review_body: str) -> dict[str, str]:
    """{word: grade} for every word with a ticked box (the first tick wins)."""
    grades: dict[str, str] = {}
    word = None
    for line in review_body.splitlines():
        heading = _HEADING.match(line)
        if heading:
            word = heading.group(1)
            continue
        ticked = _TICKED.match(line.strip())
        if word and ticked and word not in grades:
            grades[word] = ticked.group(1)
    return grades


def apply_grades(vault: Vault) -> list[tuple[str, str]]:
    """Reschedule words from every review note that hasn't been applied yet."""
    applied = []
    for path in sorted(vault.reviews_dir.glob("*.md")):
        review = Note.load(path)
        if review.meta.get("applied", True):
            continue
        reviewed_on = review.meta["date"]
        if not isinstance(reviewed_on, date):
            reviewed_on = date.fromisoformat(str(reviewed_on))
        for word, grade in read_grades(review.body).items():
            word_file = word_path(vault.words_dir, word)
            if not word_file.exists():
                continue
            note = Note.load(word_file)
            state = schedule(state_from_meta(note.meta), GRADES[grade], reviewed_on)
            note.meta.update(state_to_meta(state))
            note.meta["last_reviewed"] = reviewed_on
            note.append_to_section(REVIEW_LOG, f"- {reviewed_on.isoformat()} {grade}, next {state.due.isoformat()}")
            note.save()
            applied.append((word, grade))
        review.meta["applied"] = True
        review.save()
    return applied


def due_words(vault: Vault, today: date) -> list[Note]:
    notes = [Note.load(p) for p in vault.words_dir.glob("*.md")]
    due = [n for n in notes if "due" in n.meta and state_from_meta(n.meta).due <= today]
    return sorted(due, key=lambda n: (state_from_meta(n.meta).due, n.path.stem))


def render_review(today: date, words: list[Note]) -> Note:
    count = f"{len(words)} word{'s' if len(words) != 1 else ''} due."
    parts = [
        f"# Review {today.isoformat()}\n",
        f"{count} Read your sentence, recall the meaning, open the answer, then tick one box.\n",
    ]
    for note in words:
        word = note.path.stem
        mine = [_ADDED_ON.sub("", s) for s in note.section_items(MY_SENTENCES)]
        examples = note.section_items(EXAMPLES)
        pos = note.meta.get("part_of_speech") or ""
        meaning = note.meta.get("meaning", "")
        answer = [f"> **{pos}** · {meaning}" if pos else f"> {meaning}"]
        answer += [f"> - {e}" for e in examples]
        answer += [f"> - {s}" for s in mine[1:]]  # your other sentences, if any
        parts.append(
            f"## {word}\n"
            f"> {mine[0] if mine else '(no sentence yet)'}\n\n"
            f"> [!note]- Meaning and examples\n" + "\n".join(answer) + "\n\n"
            "- [ ] again\n- [ ] hard\n- [ ] good\n- [ ] easy\n\n"
            f"Note: [[{word}]]\n"
        )
    return Note(Path(), {"date": today, "applied": False}, "\n".join(parts))


def morning_review(vault: Vault, today: date, force: bool = False) -> ReviewResult:
    """Apply earlier ticks, then write reviews/<today>.md with the words due."""
    vault.reviews_dir.mkdir(parents=True, exist_ok=True)
    path = vault.reviews_dir / f"{today.isoformat()}.md"
    if path.exists() and not force:
        # Don't overwrite a note you may already be ticking.
        return ReviewResult(path, 0, [], already_existed=True)

    applied = apply_grades(vault)
    words = due_words(vault, today)
    if not words:
        return ReviewResult(None, 0, applied)

    review = render_review(today, words)
    review.path = path
    review.save()
    return ReviewResult(path, len(words), applied)
