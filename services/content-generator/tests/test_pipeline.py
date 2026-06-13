"""End-to-end test of the pipeline with a fake LLM client."""

import tempfile
from pathlib import Path

import pytest

from generators.embedding_client import HashEmbeddingClient
from generators.image_client import StubImageClient
from generators.models import ContentType, Curriculum, Level
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
    result = p.run(
        topic_title="Anything",
        num_modules=1,
        subtopics_per_module=2,
        levels=[Level.SUMMARY, Level.STANDARD],
    )

    assert result.reused is False
    curriculum = result.curriculum
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


def test_canonical_key_is_stored(pipeline):
    p, repo = pipeline
    p.run(topic_title="anything", num_modules=1, subtopics_per_module=1, levels=[Level.STANDARD])
    # The fake canonicalizer always returns "Test Topic" -> "test topic".
    assert repo.load_curriculum("test_topic").canonical_key == "test topic"


def test_second_prompt_for_same_topic_is_reused(pipeline):
    p, repo = pipeline
    first = p.run(topic_title="Teach me WWII", num_modules=1, subtopics_per_module=1, levels=[Level.STANDARD])
    assert first.reused is False
    posts_after_first = repo.count_posts("test_topic")

    # Different phrasing, same canonical key -> reuse, no new generation.
    second = p.run(topic_title="the second world war", num_modules=1, subtopics_per_module=1, levels=[Level.STANDARD])
    assert second.reused is True
    assert second.curriculum.topic_id == "test_topic"
    assert repo.count_posts("test_topic") == posts_after_first
    assert len(repo.topic_ids()) == 1


def test_pipeline_recovers_from_canonical_key_race(pipeline):
    p, repo = pipeline
    # Simulate a concurrent worker that already won the race for this key under
    # a different topic_id.
    winner = Curriculum(
        topic_id="winner_topic",
        title="Test Topic",
        description="d",
        modules=[],
        canonical_key="test topic",
    )
    repo.save_curriculum(winner)

    # skip_curriculum_if_exists=False forces generation; the save then loses the
    # race to `winner` (same key, different topic_id) and must reuse it.
    result = p.run(
        topic_title="anything",
        num_modules=1,
        subtopics_per_module=1,
        levels=[Level.STANDARD],
        skip_curriculum_if_exists=False,
    )
    assert result.reused is True
    assert result.curriculum.topic_id == "winner_topic"
    assert len(repo.topic_ids()) == 1


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
