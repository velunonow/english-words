"""Command line: `vocab add` and `vocab review`."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from .add import AddError, add_word
from .config import find_vault, load_dotenv
from .llm import LLMConfigError, matcher_from_env
from .review import morning_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vocab", description="Your English vocabulary notebook.")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add a word with the sentence where you saw it")
    add.add_argument("word")
    add.add_argument("-s", "--sentence", help="the sentence where you met the word")
    add.add_argument("-u", "--source", help="link to where you saw it (used to find the sentence if none is given)")

    review = sub.add_parser("review", help="apply your ticks and write today's review note")
    review.add_argument("--date", type=date.fromisoformat, default=None, help="YYYY-MM-DD, default today")
    review.add_argument("--force", action="store_true", help="rewrite today's note even if it exists")

    args = parser.parse_args(argv)
    vault = find_vault()
    load_dotenv(vault.root / ".env")

    try:
        if args.command == "add":
            path, created = add_word(vault, args.word, args.sentence, args.source, date.today(), matcher_from_env())
            verb = "Added" if created else "Added a new sentence to"
            print(f"{verb} {path.relative_to(vault.root)}")
        else:
            result = morning_review(vault, args.date or date.today(), force=args.force)
            for word, grade in result.applied:
                print(f"Rescheduled {word} ({grade})")
            if result.already_existed:
                print(f"{result.path.relative_to(vault.root)} already exists; use --force to rewrite it.")
            elif result.path is None:
                print("Nothing due today.")
            else:
                print(f"Wrote {result.path.relative_to(vault.root)} with {result.due_count} word(s).")
    except (AddError, LLMConfigError) as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
