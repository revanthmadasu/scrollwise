"""Fake LLM client for tests. Returns canned JSON responses."""

import json
from typing import Callable


class FakeLLMClient:
    model_version = "fake:test"

    def __init__(self, responder: Callable[[str, str], str]):
        """responder(system, user) -> raw text response"""
        self.responder = responder

    def complete(self, system, user, *, max_tokens=4096, temperature=0.7):
        return self.responder(system, user)


def curriculum_responder(system, user) -> str:
    return json.dumps({
        "topic_id": "test_topic",
        "title": "Test Topic",
        "description": "A topic for tests.",
        "modules": [
            {
                "module_id": "mod_a",
                "title": "Module A",
                "description": "First module",
                "subtopics": [
                    {
                        "subtopic_id": "st_a1",
                        "title": "Subtopic A1",
                        "description": "An idea",
                        "learning_objective": "Understand A1",
                        "prerequisites": []
                    },
                    {
                        "subtopic_id": "st_a2",
                        "title": "Subtopic A2",
                        "description": "Another idea",
                        "learning_objective": "Understand A2",
                        "prerequisites": ["st_a1"]
                    }
                ]
            }
        ]
    })


def post_responder(system, user) -> str:
    return json.dumps({
        "title": "A fake post title",
        "body": "Some body text explaining the idea concretely.",
        "image_prompts": ["a serene mountain scene at dawn"]
    })


def test_responder(system, user) -> str:
    return json.dumps({
        "question": "Which of these is correct?",
        "options": ["Wrong A", "Correct B", "Wrong C", "Wrong D"],
        "correct_index": 1,
        "explanation": "B is correct because of the relevant property."
    })


def canonicalize_responder(system, user) -> str:
    # Constant canonical title; matches the fake curriculum's title so a single
    # topic per test DB normalizes to one stable key.
    return json.dumps({"canonical_title": "Test Topic"})


def fill_responder(system, user) -> str:
    """A kitchen-sink structured payload. validate_inputs keeps only the keys a
    given template's field-spec declares, so this works for any fill request."""
    return json.dumps({
        "title": "Filled title",
        "subtitle": "A grounded subtitle",
        "value": "42",
        "unit": "x",
        "level": "Lv 1",
        "kicker": "Topic",
        "stats": [
            {"label": "Alpha", "value": "10", "unit": "x"},
            {"label": "Beta", "value": "20"},
        ],
        "steps": [
            {"title": "First", "text": "do this"},
            {"title": "Second", "text": "then that"},
        ],
        "options": ["Option A", "Option B", "Option C"],
        "sides": [
            {"label": "Left", "value": "one side"},
            {"label": "Right", "value": "the other"},
        ],
        "items": [{"label": "Item 1", "value": "v1"}, {"label": "Item 2", "value": "v2"}],
        "events": [{"when": "2020", "title": "An event", "text": "it happened"}],
        "ingredients": ["a thing", "another thing"],
        "body": "Filled body text.",
    })


def combined_responder(system, user) -> str:
    """Dispatch based on a distinctive phrase in the system prompt."""
    if "normalize a user" in system:
        return canonicalize_responder(system, user)
    elif "curriculum designer" in system:
        return curriculum_responder(system, user)
    elif "reshape a learning post" in system:
        return fill_responder(system, user)
    elif "learning posts" in system:
        return post_responder(system, user)
    elif "test questions" in system:
        return test_responder(system, user)
    raise ValueError(f"Don't know how to respond to system: {system[:80]}")
