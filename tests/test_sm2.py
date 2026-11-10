from datetime import date, timedelta

import pytest

from vocab.sm2 import GRADES, MIN_EASE, ReviewState, new_state, schedule

DAY = date(2026, 11, 10)


def test_new_word_is_due_tomorrow():
    state = new_state(DAY)
    assert state.due == DAY + timedelta(days=1)
    assert (state.interval, state.ease, state.repetitions) == (0, 2.5, 0)


def test_good_answers_grow_the_interval_1_6_then_times_ease():
    s = new_state(DAY)
    s = schedule(s, GRADES["good"], DAY)
    assert (s.interval, s.repetitions) == (1, 1)
    s = schedule(s, GRADES["good"], DAY)
    assert (s.interval, s.repetitions) == (6, 2)
    s = schedule(s, GRADES["good"], DAY)
    assert s.interval == 15  # round(6 * 2.5)
    assert s.due == DAY + timedelta(days=15)


def test_again_starts_the_word_over():
    s = ReviewState(due=DAY, interval=15, ease=2.5, repetitions=3)
    s = schedule(s, GRADES["again"], DAY)
    assert (s.interval, s.repetitions) == (1, 0)
    assert s.due == DAY + timedelta(days=1)


@pytest.mark.parametrize(
    "grade, ease",
    [("easy", 2.6), ("good", 2.5), ("hard", 2.36), ("again", 1.96)],
)
def test_ease_moves_with_the_grade(grade, ease):
    s = schedule(ReviewState(due=DAY), GRADES[grade], DAY)
    assert s.ease == pytest.approx(ease)


def test_ease_never_drops_below_the_minimum():
    s = ReviewState(due=DAY, ease=1.4)
    for _ in range(5):
        s = schedule(s, GRADES["again"], DAY)
    assert s.ease == MIN_EASE


def test_quality_out_of_range_is_rejected():
    with pytest.raises(ValueError):
        schedule(ReviewState(due=DAY), 6, DAY)
