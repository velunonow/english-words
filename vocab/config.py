"""Where the vault is, and settings read from the environment or a .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Vault:
    root: Path

    @property
    def words_dir(self) -> Path:
        return self.root / "words"

    @property
    def reviews_dir(self) -> Path:
        return self.root / "reviews"

    @property
    def requirements_file(self) -> Path:
        return self.root / "my-requirements.md"

    def requirements(self) -> str:
        """The learner's own rules for example sentences, if they wrote any."""
        if self.requirements_file.exists():
            return self.requirements_file.read_text(encoding="utf-8").strip()
        return ""


def load_dotenv(path: Path) -> None:
    """Load KEY=value lines from a .env file without overriding real env vars."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def find_vault() -> Vault:
    """The vault is VOCAB_VAULT if set, otherwise the current directory."""
    root = Path(os.environ.get("VOCAB_VAULT", ".")).expanduser().resolve()
    return Vault(root)
