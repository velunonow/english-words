"""Add a word, get it in a review note, tick a box, see it rescheduled."""

from datetime import date, timedelta

from vocab.add import add_word
from vocab.config import Vault
from vocab.dictionary import Sense, parse_entries
from vocab.llm import Match, NoLLM, SenseMatcher, parse_reply
from vocab.notes import Note
from vocab.review import morning_review, read_grades
from vocab.sources import find_sentence, html_to_text

DAY = date(2026, 11, 10)

SENSES = [
    Sense("noun", "A financial institution.", ["I deposited money at the bank."]),
    Sense("noun", "The edge of a river.", ["We sat on the bank of the river.", "The bank was muddy."]),
    Sense("verb", "To rely on.", ["You can bank on it."]),
]


def fake_lookup(word):
    return SENSES


class PicksRiver(SenseMatcher):
    def match(self, word, sentence, senses, requirements, want_examples):
        return Match(sense_index=1, examples=["Kids fished from the bank.", "Another one."])


def test_add_word_writes_note_with_my_sentence_first(tmp_path):
    vault = Vault(tmp_path)
    path, created = add_word(vault, "Bank", "They walked along the bank.", None, DAY, PicksRiver(), fake_lookup)

    assert created and path == tmp_path / "words" / "bank.md"
    note = Note.load(path)
    assert note.meta["meaning"] == "The edge of a river."
    assert note.meta["due"] == DAY + timedelta(days=1)
    assert note.section_items("My sentences")[0].startswith("They walked along the bank.")
    examples = note.section_items("Dictionary examples")
    # The river sense's examples first, then other noun senses; capped at three.
    assert examples[:2] == ["We sat on the bank of the river.", "The bank was muddy."]
    assert len(examples) == 3


def test_without_llm_uses_first_sense(tmp_path):
    path, _ = add_word(Vault(tmp_path), "bank", "s", None, DAY, NoLLM(), fake_lookup)
    assert Note.load(path).meta["meaning"] == "A financial institution."


def test_adding_again_keeps_schedule_and_appends_sentence(tmp_path):
    vault = Vault(tmp_path)
    add_word(vault, "bank", "First sentence.", None, DAY, NoLLM(), fake_lookup)
    _, created = add_word(vault, "bank", "Second sentence.", "https://example.com/a", DAY, NoLLM(), fake_lookup)
    note = Note.load(tmp_path / "words" / "bank.md")
    assert not created
    assert len(note.section_items("My sentences")) == 2
    assert note.meta["due"] == DAY + timedelta(days=1)


def test_sentence_found_from_link(tmp_path):
    html = "<html><script>bank()</script><p>Hello there. The river bank flooded again! Bye.</p></html>"
    path, _ = add_word(
        Vault(tmp_path), "bank", None, "https://example.com", DAY, NoLLM(), fake_lookup, fetch_text=lambda url: html_to_text(html)
    )
    assert Note.load(path).section_items("My sentences")[0].startswith("The river bank flooded again!")


def test_review_round_trip(tmp_path):
    vault = Vault(tmp_path)
    add_word(vault, "bank", "They walked along the bank.", None, DAY, NoLLM(), fake_lookup)

    tomorrow = DAY + timedelta(days=1)
    result = morning_review(vault, tomorrow)
    assert result.due_count == 1
    review = Note.load(result.path)
    assert "> They walked along the bank." in review.body

    # Tick "good" in Obsidian.
    result.path.write_text(result.path.read_text().replace("- [ ] good", "- [x] good"))

    next_day = tomorrow + timedelta(days=1)
    result = morning_review(vault, next_day)
    assert result.applied == [("bank", "good")]
    note = Note.load(tmp_path / "words" / "bank.md")
    assert note.meta["repetitions"] == 1
    assert note.meta["due"] == next_day  # first good answer: back in 1 day
    assert note.section_items("Review log") == [f"{tomorrow.isoformat()} good, next {next_day.isoformat()}"]
    assert Note.load(tmp_path / "reviews" / f"{tomorrow.isoformat()}.md").meta["applied"] is True

    # Second good answer: back in 6 days.
    assert result.due_count == 1
    result.path.write_text(result.path.read_text().replace("- [ ] good", "- [x] good"))
    morning_review(vault, next_day + timedelta(days=1))
    assert Note.load(tmp_path / "words" / "bank.md").meta["due"] == next_day + timedelta(days=6)


def test_existing_review_note_is_not_overwritten(tmp_path):
    vault = Vault(tmp_path)
    add_word(vault, "bank", "s", None, DAY, NoLLM(), fake_lookup)
    first = morning_review(vault, DAY + timedelta(days=1))
    again = morning_review(vault, DAY + timedelta(days=1))
    assert again.already_existed and again.path == first.path


def test_read_grades_takes_first_tick_per_word():
    body = "## bank\n- [ ] again\n- [x] hard\n- [x] easy\n\n## river\n- [ ] good\n\n## tide\n- [X] easy\n"
    assert read_grades(body) == {"bank": "hard", "tide": "easy"}


def test_parse_reply_handles_fences_and_garbage():
    reply = 'Sure!\n```json\n{"sense": 2, "definition": "edge of a river", "examples": ["A.", " "]}\n```'
    match = parse_reply(reply, n_senses=3)
    assert match.sense_index == 1 and match.examples == ["A."]
    assert parse_reply("no json here", n_senses=3).sense_index == 0
    assert parse_reply('{"sense": 9}', n_senses=3).sense_index is None


def test_find_sentence_matches_word_forms():
    text = "Nothing here. She was banking on a raise. Later."
    assert find_sentence(text, "bank") == "She was banking on a raise."
    assert find_sentence(text, "river") is None


def test_parse_entries():
    data = [{"meanings": [{"partOfSpeech": "noun", "definitions": [
        {"definition": "d1", "example": "e1"}, {"definition": "d2"}]}]}]
    senses = parse_entries(data)
    assert [(s.part_of_speech, s.definition, s.examples) for s in senses] == [("noun", "d1", ["e1"]), ("noun", "d2", [])]


def test_add_without_a_sentence_then_add_one_later(tmp_path):
    vault = Vault(tmp_path)
    path, created = add_word(vault, "bank", None, None, DAY, NoLLM(), fake_lookup)
    assert created and Note.load(path).section_items("My sentences") == []

    review = morning_review(vault, DAY + timedelta(days=1))
    assert "> I deposited money at the bank." in Note.load(review.path).body  # dictionary example as the cue

    add_word(vault, "bank", "Mine at last.", None, DAY, NoLLM(), fake_lookup)
    note = Note.load(path)
    assert note.section_items("My sentences")[0].startswith("Mine at last.")
    assert "_(none yet)_" not in note.body
