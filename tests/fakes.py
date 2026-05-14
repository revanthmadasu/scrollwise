"""Fake LLM client for tests. Returns canned JSON responses."""

import json
from typing import Callable


class FakeLLMClient:
    model_version = "fake:test"

    def __init__(self, responder: Callable[[str, str], str]):
        """responder(system, user) -> raw text response"""
        self.responder = responder

    def complete(self, system, user, *, max_tokens=2048, temperature=0.7):
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


def combined_responder(system, user) -> str:
    """Dispatch based on the system prompt's first word."""
    if "curriculum designer" in system:
        return curriculum_responder(system, user)
    elif "learning posts" in system:
        return post_responder(system, user)
    elif "test questions" in system:
        return test_responder(system, user)
    raise ValueError(f"Don't know how to respond to system: {system[:80]}")
