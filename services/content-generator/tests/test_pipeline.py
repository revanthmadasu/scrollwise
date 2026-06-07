"""End-to-end test of the pipeline with a fake LLM client."""

import tempfile
from pathlib import Path

import pytest

from generators.embedding_client import HashEmbeddingClient
from generators.image_client import StubImageClient
from generators.models import ContentType, Level
from generators.pipeline import Pipeline
from storage.repository import Repository
from tests.fakes import FakeLLMClient, combined_responder


@pytest.fixture
def pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        repo = Repository(db_path)
        llm = FakeLLMClient(combined_responder)
        p = Pipeline(
            repo=repo,
            llm=llm,
            images=StubImageClient(),
            embeddings=HashEmbeddingClient(),
            test_cadence=2,
        )
        yield p, repo
        repo.close()


def test_end_to_end_generates_curriculum_posts_and_tests(pipeline):
    p, repo = pipeline
    curriculum = p.run(
        topic_title="Anything",
        num_modules=1,
        subtopics_per_module=2,
        levels=[Level.SUMMARY, Level.STANDARD],
    )

    assert curriculum.topic_id == "test_topic"
    assert len(curriculum.modules) == 1

    all_posts = repo.all_posts_for_topic("test_topic")

    # 2 subtopics * 2 levels = 4 content posts, plus 1 test post (end of module / cadence=2)
    content_posts = [x for x in all_posts if x.content_type != ContentType.TEST]
    test_posts = [x for x in all_posts if x.content_type == ContentType.TEST]

    assert len(content_posts) == 4
    assert len(test_posts) >= 1
    assert all(t.blocking for t in test_posts)


def test_each_post_has_embedding(pipeline):
    p, repo = pipeline
    p.run(topic_title="X", num_modules=1, subtopics_per_module=1, levels=[Level.STANDARD])
    posts = repo.all_posts_for_topic("test_topic")
    assert all(post.embedding is not None and len(post.embedding) == 1024 for post in posts)


def test_offsets_are_unique_and_ordered(pipeline):
    p, repo = pipeline
    p.run(
        topic_title="X",
        num_modules=1,
        subtopics_per_module=2,
        levels=[Level.SUMMARY, Level.STANDARD, Level.DEEP],
    )
    posts = repo.all_posts_for_topic("test_topic")
    offsets = [(x.offset_module, x.offset_subtopic, x.offset_seq) for x in posts]
    # No duplicate full-offset tuples
    assert len(offsets) == len(set(offsets))
    # Already sorted by query
    assert offsets == sorted(offsets)
