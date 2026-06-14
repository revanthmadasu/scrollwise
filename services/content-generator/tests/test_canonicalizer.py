"""Tests for topic canonicalization (normalize() + the LLM-backed wrapper)."""

import json

from generators.canonicalizer import TopicCanonicalizer, normalize
from tests.fakes import FakeLLMClient


def test_normalize_collapses_case_punctuation_and_whitespace():
    variants = [
        "The Roman Empire",
        "the roman empire",
        "Roman Empire!",
        "  Roman   Empire  ",
        "ROMAN EMPIRE",
        "Roman, Empire.",
    ]
    assert {normalize(v) for v in variants} == {"roman empire"}


def test_normalize_strips_only_leading_articles():
    # Leading article dropped...
    assert normalize("A Brief History of Time") == "brief history of time"
    # ...but interior articles are kept.
    assert normalize("Lord of the Rings") == "lord of the rings"


def test_normalize_keeps_distinct_topics_distinct():
    assert normalize("World War I") != normalize("World War II")
    assert normalize("Roman Empire") != normalize("Ottoman Empire")


def test_canonicalizer_returns_title_and_key():
    llm = FakeLLMClient(lambda s, u: json.dumps({"canonical_title": "World War II"}))
    title, key = TopicCanonicalizer(llm).canonicalize("teach me about WWII please")
    assert title == "World War II"
    assert key == "world war ii"


def test_canonicalizer_falls_back_when_llm_output_unusable():
    # Garbage that can't be parsed -> fall back to the raw prompt, never crash.
    llm = FakeLLMClient(lambda s, u: "not json at all")
    title, key = TopicCanonicalizer(llm).canonicalize("Quantum Mechanics")
    assert title == "Quantum Mechanics"
    assert key == "quantum mechanics"
