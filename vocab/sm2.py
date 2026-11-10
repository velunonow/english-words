"""SM-2 spaced repetition, the practical form of the Ebbinghaus forgetting curve.

Each review gets a quality score from 0 to 5. A good score pushes the next
review further out (1 day, then 6 days, then interval x ease). A failed score
starts the word over at 1 day. The ease factor moves up or down a little after
every review, so easy words drift apart and hard words come back often.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# The four buttons in the review note, mapped to SM-2 quality scores (like Anki).
GRADES: dict[str, int] = {"again": 1, "hard": 3, "good": 4, "easy": 5}

DEFAULT_EASE = 2.5
MIN_EASE = 1.3


@dataclass(frozen=True)
class ReviewState:
    """Where a word stands in its review schedule."""

    due: date
    interval: int = 0  # days until the next review, as last scheduled
    ease: float = DEFAULT_EASE
    repetitions: int = 0  # successful reviews in a row


def new_state(added: date) -> ReviewState:
    """A word added today is first reviewed tomorrow."""
    return ReviewState(due=added + timedelta(days=1))


def schedule(state: ReviewState, quality: int, reviewed_on: date) -> ReviewState:
    """Return the state after a review with the given quality (0-5)."""
    if not 0 <= quality <= 5:
        raise ValueError(f"quality must be between 0 and 5, got {quality}")

    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = max(1, round(state.interval * state.ease))
        repetitions = state.repetitions + 1

    ease = state.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(MIN_EASE, round(ease, 2))

    return ReviewState(
        due=reviewed_on + timedelta(days=interval),
        interval=interval,
        ease=ease,
        repetitions=repetitions,
    )
