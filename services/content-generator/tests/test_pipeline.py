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


def test_pipeline_assigns_approved_template():
    """With an approved template in the catalog, generated posts carry it."""
    import json

    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(str(Path(tmp) / "t.db"))
        # Seed the API-owned catalog (same shared DB) with one approved template.
        repo._execute(
            "CREATE TABLE templates (template_id TEXT, name TEXT, vibe TEXT, status TEXT, "
            "version INTEGER, compatible_content_types TEXT, fields TEXT)"
        )
        repo._execute(
            "INSERT INTO templates VALUES (?,?,?,?,?,?,?)",
            ("cover", "Cover", "energetic", "approved", 1,
             json.dumps(["text", "image_post"]),
             json.dumps([{"name": "title", "type": "text", "required": True, "max": 60},
                         {"name": "body", "type": "rich", "max": 400}])),
        )
        repo._commit()

        p = Pipeline(
            repo=repo, llm=FakeLLMClient(combined_responder),
            images=StubImageClient(), embeddings=HashEmbeddingClient(), test_cadence=2,
        )
        p.run(topic_title="X", num_modules=1, subtopics_per_module=2,
              levels=[Level.SUMMARY, Level.STANDARD])

        posts = repo.all_posts_for_topic("test_topic")
        templated = [pp for pp in posts if pp.template_id]
        assert templated, "expected at least one post to be assigned a template"
        assert all(pp.template_id == "cover" for pp in templated)
        assert all(pp.template_inputs.get("title") for pp in templated)
        repo.close()


def test_pipeline_fills_structured_template():
    """A template that requires `stats` triggers the LLM fill pass."""
    import json

    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(str(Path(tmp) / "t.db"))
        repo._execute(
            "CREATE TABLE templates (template_id TEXT, name TEXT, vibe TEXT, status TEXT, "
            "version INTEGER, compatible_content_types TEXT, fields TEXT)"
        )
        repo._execute(
            "INSERT INTO templates VALUES (?,?,?,?,?,?,?)",
            ("infographic", "Infographic", "structured", "approved", 1,
             json.dumps(["text", "image_post"]),
             json.dumps([
                 {"name": "title", "type": "text", "required": True, "max": 70},
                 {"name": "stats", "type": "list", "required": True, "min": 1, "max": 3, "of": [
                     {"name": "label", "type": "text", "max": 24, "required": True},
                     {"name": "value", "type": "text", "max": 12, "required": True},
                 ]},
             ])),
        )
        repo._commit()

        p = Pipeline(
            repo=repo, llm=FakeLLMClient(combined_responder),
            images=StubImageClient(), embeddings=HashEmbeddingClient(), test_cadence=2,
        )
        p.run(topic_title="X", num_modules=1, subtopics_per_module=2,
              levels=[Level.SUMMARY, Level.STANDARD])

        templated = [pp for pp in repo.all_posts_for_topic("test_topic") if pp.template_id]
        assert templated, "expected the structured template to be assigned"
        stats = templated[0].template_inputs.get("stats")
        assert stats and stats[0]["label"] and stats[0]["value"]
        repo.close()


class _CountingImages:
    """Spy image client that records how many backgrounds it was asked to make."""

    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return "https://example.test/bg.png"


def _seed_text_template(repo):
    import json
    repo._execute(
        "CREATE TABLE templates (template_id TEXT, name TEXT, vibe TEXT, status TEXT, "
        "version INTEGER, compatible_content_types TEXT, fields TEXT)"
    )
    repo._execute(
        "INSERT INTO templates VALUES (?,?,?,?,?,?,?)",
        ("cover", "Cover", "energetic", "approved", 1, json.dumps(["text"]),
         json.dumps([{"name": "title", "type": "text", "required": True, "max": 60},
                     {"name": "body", "type": "rich", "max": 400}])),
    )
    repo._commit()


def test_templated_posts_skip_image_generation():
    """A post that gets a template must NOT call the image backend."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(str(Path(tmp) / "t.db"))
        _seed_text_template(repo)
        images = _CountingImages()
        p = Pipeline(
            repo=repo, llm=FakeLLMClient(combined_responder),
            images=images, embeddings=HashEmbeddingClient(), test_cadence=99,
        )
        p.run(topic_title="X", num_modules=1, subtopics_per_module=2,
              levels=[Level.SUMMARY, Level.STANDARD])

        templated = [pp for pp in repo.all_posts_for_topic("test_topic") if pp.template_id]
        assert templated, "expected posts to be templated"
        assert images.calls == 0, "templated posts should not generate backgrounds"
        assert all(pp.image_urls == [] for pp in templated)
        assert all(pp.content_type == ContentType.TEXT for pp in templated)
        repo.close()


def test_untemplated_posts_still_generate_images():
    """With no template catalog and the image-posts flag ON, posts fall back to
    background generation."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(str(Path(tmp) / "t.db"))  # no templates table
        images = _CountingImages()
        p = Pipeline(
            repo=repo, llm=FakeLLMClient(combined_responder),
            images=images, embeddings=HashEmbeddingClient(), test_cadence=99,
            image_posts_enabled=True,
        )
        p.run(topic_title="X", num_modules=1, subtopics_per_module=1,
              levels=[Level.SUMMARY])

        assert images.calls > 0, "non-templated posts should still generate backgrounds"
        repo.close()


def test_image_posts_flag_off_suppresses_backgrounds():
    """With the image-posts feature flag off, even untemplated posts stay text
    and never hit the image backend."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(str(Path(tmp) / "t.db"))  # no templates table
        images = _CountingImages()
        p = Pipeline(
            repo=repo, llm=FakeLLMClient(combined_responder),
            images=images, embeddings=HashEmbeddingClient(), test_cadence=99,
            image_posts_enabled=False,
        )
        p.run(topic_title="X", num_modules=1, subtopics_per_module=2,
              levels=[Level.SUMMARY])

        content = [pp for pp in repo.all_posts_for_topic("test_topic")
                   if pp.content_type != ContentType.TEST]
        assert content, "expected content posts to be generated"
        assert images.calls == 0, "flag off must suppress all background generation"
        assert all(pp.content_type == ContentType.TEXT for pp in content)
        assert all(pp.image_urls == [] for pp in content)
        repo.close()


def test_image_posts_enabled_from_env(monkeypatch):
    """The env flag parses truthy/falsy spellings; default is enabled."""
    from generators.pipeline import image_posts_enabled_from_env

    monkeypatch.delenv("IMAGE_POSTS_ENABLED", raising=False)
    assert image_posts_enabled_from_env() is False  # default OFF: template-only

    for falsy in ("0", "false", "False", "no", "off", ""):
        monkeypatch.setenv("IMAGE_POSTS_ENABLED", falsy)
        assert image_posts_enabled_from_env() is False, falsy

    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("IMAGE_POSTS_ENABLED", truthy)
        assert image_posts_enabled_from_env() is True, truthy
