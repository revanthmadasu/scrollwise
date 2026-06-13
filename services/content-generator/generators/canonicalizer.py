"""Topic canonicalization for prompt de-duplication.

A user's raw prompt ("teach me about the roman empire") is mapped by an LLM to a
canonical title ("Roman Empire"), then reduced by the pure `normalize()` helper
to a `canonical_key` ("roman empire"). Two differently-phrased requests for the
same topic collapse to the same key, so the pipeline can reuse an existing
curriculum instead of generating a duplicate. See packages/contract/topic-dedup.plan.md.
"""

from __future__ import annotations

import re

from generators._logging import get_logger
from generators.llm_client import LLMClient, parse_json_response
from prompts.templates import CANONICALIZE_SYSTEM, CANONICALIZE_USER

logger = get_logger(__name__)

# Articles stripped only when leading: "The Roman Empire" -> "roman empire",
# but "Lord of the Rings" keeps its interior "the".
_LEADING_ARTICLES = {"the", "a", "an"}


def normalize(title: str) -> str:
    """Reduce a title to a stable comparison key. Pure and deterministic.

    Lowercase, drop punctuation, strip leading articles, collapse whitespace.
    Unit-tested: article/case/punctuation/whitespace variants must collapse to
    the same key, while genuinely distinct topics must stay distinct.
    """
    # Replace anything that isn't a word char or space with a space, so
    # punctuation becomes a token boundary rather than gluing words together.
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    words = cleaned.split()
    while words and words[0] in _LEADING_ARTICLES:
        words.pop(0)
    return " ".join(words)


class TopicCanonicalizer:
    """Wraps an LLM call that produces a canonical topic title."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def canonicalize(self, prompt_text: str) -> tuple[str, str]:
        """Return (canonical_title, canonical_key) for a raw user prompt.

        Falls back to the raw prompt if the LLM returns nothing usable, so a
        flaky canonicalization never blocks generation — worst case is a missed
        dedup, which is exactly the accepted v1 limitation.
        """
        response = self.llm.complete(
            system=CANONICALIZE_SYSTEM,
            user=CANONICALIZE_USER.format(prompt_text=prompt_text),
            max_tokens=200,
            temperature=0.0,
        )
        try:
            data = parse_json_response(response)
            title = (data.get("canonical_title") or "").strip()
        except ValueError:
            logger.error("canonicalize_parse_failed", extra={"prompt": prompt_text})
            title = ""

        if not title:
            title = prompt_text.strip()

        key = normalize(title)
        logger.info(
            "canonicalized",
            extra={"prompt": prompt_text, "canonical_title": title, "canonical_key": key},
        )
        return title, key
