"""Tests for the user_prompts -> generation consumer."""

import tempfile
import uuid
from pathlib import Path

import pytest

from generators import prompt_consumer as pc
from generators.embedding_client import HashEmbeddingClient
from generators.image_client import StubImageClient
from generators.models import Level
from generators.pipeline import Pipeline
from storage.repository import Repository
from tests.fakes import FakeLLMClient, combined_responder

# Minimal stand-in for the apps/api-owned table (api would normally create it).
_USER_PROMPTS_DDL = """
CREATE TABLE IF NOT EXISTS user_prompts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    topic_id TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _enqueue(repo: Repository, text: str) -> str:
    pid = str(uuid.uuid4())
    repo._execute(
        "INSERT INTO user_prompts (id, user_id, prompt_text, status) "
        "VALUES (?, ?, ?, 'pending')",
        (pid, "u1", text),
    )
    repo._commit()
    return pid


def _status(repo: Repository, pid: str) -> dict:
    return repo._fetchone(
        "SELECT status, topic_id, error FROM user_prompts WHERE id = ?", (pid,)
    )


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(str(Path(tmp) / "test.db"))
        repo._execute(_USER_PROMPTS_DDL)
        repo._commit()
        pipeline = Pipeline(
            repo=repo,
            llm=FakeLLMClient(combined_responder),
            images=StubImageClient(),
            embeddings=HashEmbeddingClient(),
            test_cadence=2,
        )
        yield repo, pipeline
        repo.close()


_OPTS = pc.GenerationOptions(
    num_modules=1, subtopics_per_module=2, levels=[Level.SUMMARY, Level.STANDARD]
)


def test_drain_processes_pending_prompt(env):
    repo, pipeline = env
    pid = _enqueue(repo, "Teach me stoicism")

    processed = pc.drain_once(repo, pipeline, _OPTS, batch_size=5)

    assert processed == 1
    row = _status(repo, pid)
    assert row["status"] == "ready"
    assert row["topic_id"] == "test_topic"  # from the fake curriculum responder
    assert row["error"] is None
    # Content actually landed in the posts table.
    assert repo.count_posts("test_topic") > 0


def test_drain_is_noop_on_empty_queue(env):
    repo, pipeline = env
    assert pc.drain_once(repo, pipeline, _OPTS, batch_size=5) == 0


def test_claim_marks_generating_and_is_not_reclaimed(env):
    repo, pipeline = env
    _enqueue(repo, "Topic A")

    first = repo.claim_pending_prompt()
    assert first is not None
    # Once claimed (status=generating), a second claim finds nothing.
    assert repo.claim_pending_prompt() is None
    assert _status(repo, first["id"])["status"] == "generating"


def test_generation_failure_marks_failed(env):
    repo, _pipeline = env
    pid = _enqueue(repo, "Boom")

    # A pipeline whose LLM always raises -> the prompt is marked failed, not lost.
    def boom(system, user):
        raise RuntimeError("llm exploded")

    failing = Pipeline(
        repo=repo,
        llm=FakeLLMClient(boom),
        images=StubImageClient(),
        embeddings=HashEmbeddingClient(),
        test_cadence=2,
    )

    processed = pc.drain_once(repo, failing, _OPTS, batch_size=5)
    assert processed == 1
    row = _status(repo, pid)
    assert row["status"] == "failed"
    assert "llm exploded" in row["error"]
