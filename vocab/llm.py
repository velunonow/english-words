"""The AI part: pick the dictionary sense that matches your sentence, and write
extra example sentences that follow your requirements.

Pluggable on purpose. Every backend implements one method, `complete(prompt)`,
and shares the prompt and the parsing in `LLMMatcher`. Choose one with env vars:

    VOCAB_LLM_PROVIDER=anthropic   # Claude, through the official Anthropic SDK
    VOCAB_LLM_PROVIDER=openai      # any OpenAI-compatible API (OpenAI, DeepSeek, Qwen, ...)
    VOCAB_LLM_MODEL=<model id from your provider>

With no provider set, `NoLLM` is used: the first dictionary sense, no AI examples.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .dictionary import Sense


class LLMConfigError(RuntimeError):
    pass


@dataclass
class Match:
    sense_index: int | None  # index into the senses list, or None if unknown
    definition: str = ""  # used when the dictionary had no fitting sense
    examples: list[str] = field(default_factory=list)  # AI-written examples


class SenseMatcher(ABC):
    @abstractmethod
    def match(self, word: str, sentence: str, senses: list[Sense], requirements: str, want_examples: int) -> Match:
        ...


class NoLLM(SenseMatcher):
    """Works with no API key: the dictionary's first sense, no generated examples."""

    def match(self, word, sentence, senses, requirements, want_examples):
        return Match(sense_index=0 if senses else None)


class LLMMatcher(SenseMatcher):
    """Template for real backends: build the prompt, call the model, parse JSON."""

    def match(self, word, sentence, senses, requirements, want_examples):
        prompt = build_prompt(word, sentence, senses, requirements, want_examples)
        return parse_reply(self.complete(prompt), len(senses))

    @abstractmethod
    def complete(self, prompt: str) -> str:
        ...


def build_prompt(word: str, sentence: str, senses: list[Sense], requirements: str, want_examples: int) -> str:
    sense_list = "\n".join(f"{i}. ({s.part_of_speech}) {s.definition}" for i, s in enumerate(senses, 1))
    return f"""You help a learner keep an English vocabulary notebook.

Word: {word}
The learner met it in this sentence: "{sentence}"

Dictionary senses:
{sense_list or "(the dictionary has no entry for this word)"}

The learner's requirements for example sentences:
{requirements or "(none)"}

Reply with only a JSON object, no other text:
{{"sense": <number of the sense above that matches the learner's sentence, or 0 if none fits>,
  "definition": "<a short, plain definition of the word as used in the learner's sentence>",
  "examples": [<exactly {want_examples} new example sentences that use the word in that same sense and follow the requirements>]}}"""


def parse_reply(text: str, n_senses: int) -> Match:
    """Pull the JSON object out of the model's reply; fall back safely if it's malformed."""
    found = re.search(r"\{.*\}", text, re.DOTALL)
    if not found:
        return Match(sense_index=0 if n_senses else None)
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        return Match(sense_index=0 if n_senses else None)

    try:
        number = int(data.get("sense", 0))
    except (TypeError, ValueError):
        number = 0
    index = number - 1 if 1 <= number <= n_senses else None
    examples = [str(e).strip() for e in data.get("examples", []) if str(e).strip()]
    return Match(sense_index=index, definition=str(data.get("definition", "")).strip(), examples=examples)


class AnthropicMatcher(LLMMatcher):
    """Claude via the official SDK (`pip install anthropic`). Reads ANTHROPIC_API_KEY."""

    def __init__(self, model: str) -> None:
        try:
            import anthropic
        except ImportError as err:
            raise LLMConfigError("Install the SDK first: pip install anthropic") from err
        self.client = anthropic.Anthropic()
        self.model = model

    def complete(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The model declined this request.")
        return "".join(block.text for block in response.content if block.type == "text")


class OpenAICompatibleMatcher(LLMMatcher):
    """Any provider with an OpenAI-style /chat/completions endpoint."""

    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def complete(self, prompt: str) -> str:
        body = json.dumps({"model": self.model, "messages": [{"role": "user", "content": prompt}]}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
        return data["choices"][0]["message"]["content"]


def matcher_from_env(env: dict[str, str] | None = None) -> SenseMatcher:
    env = dict(os.environ if env is None else env)
    provider = env.get("VOCAB_LLM_PROVIDER", "").strip().lower()
    if not provider:
        return NoLLM()

    model = env.get("VOCAB_LLM_MODEL", "").strip()
    if not model:
        raise LLMConfigError("Set VOCAB_LLM_MODEL to a model id from your provider.")

    if provider == "anthropic":
        return AnthropicMatcher(model)
    if provider == "openai":
        api_key = env.get("VOCAB_LLM_API_KEY", "").strip()
        if not api_key:
            raise LLMConfigError("Set VOCAB_LLM_API_KEY for the openai provider.")
        base_url = env.get("VOCAB_LLM_BASE_URL", "https://api.openai.com/v1")
        return OpenAICompatibleMatcher(model, api_key, base_url)
    raise LLMConfigError(f"Unknown VOCAB_LLM_PROVIDER {provider!r}; use 'anthropic' or 'openai'.")
