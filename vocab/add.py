"""Add a word: your sentence first, then the matching meaning and examples."""

from __future__ import annotations

import sys
import urllib.error
from datetime import date
from pathlib import Path
from typing import Callable

from . import dictionary, sources
from .config import Vault
from .dictionary import Sense
from .llm import SenseMatcher
from .notes import MY_SENTENCES, Note, format_sentence, new_word_note, word_path
from .sm2 import new_state

EXAMPLES_WANTED = 3


class AddError(RuntimeError):
    pass


def add_word(
    vault: Vault,
    word: str,
    sentence: str | None,
    source: str | None,
    today: date,
    matcher: SenseMatcher,
    lookup: Callable[[str], list[Sense]] = dictionary.lookup,
    fetch_text: Callable[[str], str] = sources.fetch_text,
) -> tuple[Path, bool]:
    """Create or update the word's note. Returns (path, created)."""
    word = " ".join(word.strip().split()).lower()
    if not word:
        raise AddError("Give a word.")

    if not sentence:
        if not source:
            raise AddError("Give the sentence where you saw the word (--sentence), or a link (--source).")
        sentence = sources.find_sentence(fetch_text(source), word)
        if not sentence:
            raise AddError(f"Couldn't find '{word}' on that page. Pass the sentence with --sentence.")

    my_line = format_sentence(sentence, source, today)
    path = word_path(vault.words_dir, word)

    # Seen it before: keep the review schedule, just add the new sentence.
    if path.exists():
        note = Note.load(path)
        note.append_to_section(MY_SENTENCES, f"- {my_line}")
        note.save()
        return path, False

    try:
        senses = lookup(word)
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"Dictionary lookup failed ({err}); continuing without it.", file=sys.stderr)
        senses = []

    match = matcher.match(
        word, sentence, senses, vault.requirements(), want_examples=EXAMPLES_WANTED
    )

    if match.sense_index is not None:
        sense = senses[match.sense_index]
        pos, meaning = sense.part_of_speech, sense.definition
        examples = _examples(senses, match.sense_index)
    else:
        # No dictionary sense fits (or there's no entry): use the AI's definition.
        pos, meaning = "", match.definition or "(no dictionary entry)"
        examples = []

    # Fill up to three examples with AI-written ones, labelled so you can tell them apart.
    for extra in match.examples:
        if len(examples) >= EXAMPLES_WANTED:
            break
        examples.append(f"{extra} *(AI)*")

    note = new_word_note(path, word, pos, meaning, my_line, examples, today, new_state(today))
    note.save()
    return path, True


def _examples(senses: list[Sense], chosen: int) -> list[str]:
    """The chosen sense's examples first, then others with the same part of speech."""
    sense = senses[chosen]
    pool = [sense] + [s for s in senses if s is not sense and s.part_of_speech == sense.part_of_speech]
    return [e for s in pool for e in s.examples][:EXAMPLES_WANTED]
