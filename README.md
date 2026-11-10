# english-words

My personal English vocabulary notebook. It is an Obsidian vault and a small Python tool:

1. **Add a word** with the sentence where I met it. The tool writes a note for the word: my sentence first, then the meaning that fits it and a few example sentences.
2. **Review every morning.** A daily note lists the words due today, picked by SM-2 (the spaced-repetition method behind Anki, based on the Ebbinghaus forgetting curve). I tick how well I remembered each word, and the next review reschedules it.

```
words/        one note per word (meaning, my sentences, examples, review state)
reviews/      one review note per day
vocab/        the Python tool
my-requirements.md   my rules for AI-written example sentences
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ,anthropic to use Claude: ".[dev,anthropic]"
cp .env.example .env             # optional: set an AI provider for sense matching
```

Then open this folder as a vault in Obsidian.

## Add a word

```bash
vocab add serendipity --sentence "Meeting her there was pure serendipity."
vocab add serendipity --source https://example.com/article     # finds the sentence on the page
vocab add serendipity -s "..." -u https://example.com/article  # both
```

Adding a word you already have just adds the new sentence to its note and keeps its schedule.

Meanings and dictionary examples come from the free [Free Dictionary API](https://dictionaryapi.dev). With an AI provider set in `.env`, the tool also:

- picks the dictionary meaning that matches **your** sentence (for "bank", river or money?), and
- fills up to three examples with AI-written sentences that follow `my-requirements.md`, marked *(AI)*.

Without one, it uses the first dictionary meaning and only dictionary examples.

## Morning review

```bash
vocab review
```

This writes `reviews/YYYY-MM-DD.md`. For each word: read your sentence, recall the meaning, open the folded answer, then tick **again**, **hard**, **good** or **easy**. The next `vocab review` reads your ticks and reschedules each word (first good answer: 1 day, then 6 days, then longer each time; "again" starts it over). A word you didn't tick stays due.

## Sync with Obsidian

Install the **Obsidian Git** community plugin and turn on auto pull and push, so notes stay in sync with this repo across devices.

The **Morning review** GitHub Action (`.github/workflows/morning-review.yml`) can write the review note for you every morning and commit it, so it shows up in Obsidian after a pull. It is off by default: run it by hand from the Actions tab, or uncomment its `schedule`.

## How it works

| File | What it does |
|---|---|
| `vocab/sm2.py` | SM-2 scheduling: quality 0-5 in, next due date out |
| `vocab/notes.py` | Markdown notes with YAML frontmatter (the review state lives there) |
| `vocab/dictionary.py` | Free Dictionary API lookup |
| `vocab/llm.py` | Pluggable AI backends: `anthropic` (Anthropic SDK) or `openai` (any OpenAI-compatible API) |
| `vocab/add.py` | Adding a word |
| `vocab/review.py` | Applying ticks and writing the daily review note |

Run the tests with `pytest`.
