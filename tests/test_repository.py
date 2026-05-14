import tempfile
import uuid
from pathlib import Path

import pytest

from generators.models import (
    ContentType,
    Curriculum,
    Level,
    Module,
    Post,
    Subtopic,
    TestType,
)
from storage.repository import Repository


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        r = Repository(db_path)
        yield r
        r.close()


def make_curriculum():
    return Curriculum(
        topic_id="test_t",
        title="Test",
        description="A test topic",
        modules=[
            Module(
                module_id="m1",
                title="Module 1",
                description="...",
                subtopics=[
                    Subtopic(
                        subtopic_id="s1",
                        title="Sub 1",
                        description="...",
                        learning_objective="...",
                    )
                ],
            )
        ],
    )


def make_post(level=Level.STANDARD, content_type=ContentType.TEXT, blocking=False, **overrides):
    base = dict(
        post_id=str(uuid.uuid4()),
        topic_id="test_t",
        module_id="m1",
        subtopic_id="s1",
        offset_module=0,
        offset_subtopic=0,
        offset_seq=int(level),
        level=level,
        content_type=content_type,
        title="A title",
        body="A body",
        blocking=blocking,
        embedding=[0.1] * 1024,
    )
    base.update(overrides)
    return Post(**base)


def test_save_and_load_curriculum(repo):
    c = make_curriculum()
    repo.save_curriculum(c)
    loaded = repo.load_curriculum("test_t")
    assert loaded is not None
    assert loaded.topic_id == "test_t"
    assert len(loaded.modules) == 1


def test_save_and_list_posts(repo):
    p = make_post()
    repo.save_post(p)
    posts = repo.list_posts("test_t")
    assert len(posts) == 1
    assert posts[0].post_id == p.post_id
    assert posts[0].embedding == [0.1] * 1024


def test_list_posts_by_level(repo):
    repo.save_post(make_post(level=Level.SUMMARY))
    repo.save_post(make_post(level=Level.STANDARD))
    repo.save_post(make_post(level=Level.DEEP))
    only_standard = repo.list_posts("test_t", level=Level.STANDARD)
    # Should include level 2 + any test posts (none here)
    assert len(only_standard) == 1
    assert only_standard[0].level == Level.STANDARD


def test_list_includes_tests_regardless_of_level(repo):
    repo.save_post(make_post(level=Level.STANDARD))
    test_post = make_post(
        content_type=ContentType.TEST,
        test_type=TestType.MCQ,
        question="Q?",
        options=["a", "b"],
        correct_index=0,
        explanation="because",
        blocking=True,
    )
    repo.save_post(test_post)
    # Asking for level 1 should still include the test
    summary_view = repo.list_posts("test_t", level=Level.SUMMARY)
    test_posts = [p for p in summary_view if p.content_type == ContentType.TEST]
    assert len(test_posts) == 1


def test_posts_ordered_by_offset(repo):
    repo.save_post(make_post(offset_module=0, offset_subtopic=1, offset_seq=0))
    repo.save_post(make_post(offset_module=0, offset_subtopic=0, offset_seq=2))
    repo.save_post(make_post(offset_module=0, offset_subtopic=0, offset_seq=1))
    posts = repo.list_posts("test_t")
    offsets = [(p.offset_module, p.offset_subtopic, p.offset_seq) for p in posts]
    assert offsets == [(0, 0, 1), (0, 0, 2), (0, 1, 0)]
