"""Domain models. Anything that crosses an API or DB boundary goes here."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Level(int, Enum):
    """Granularity level for a post."""

    SUMMARY = 1   # one-liner, 5s read
    STANDARD = 2  # paragraphs, 30s read
    DEEP = 3      # long-form, 2min read


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE_POST = "image_post"
    CAROUSEL = "carousel"
    VIDEO = "video"
    TEST = "test"


class TestType(str, Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"


class Subtopic(BaseModel):
    """A leaf in the curriculum tree. The unit of teaching."""

    subtopic_id: str
    title: str
    description: str
    learning_objective: str
    prerequisites: list[str] = Field(default_factory=list)


class Module(BaseModel):
    """A group of related subtopics."""

    module_id: str
    title: str
    description: str
    subtopics: list[Subtopic]


class Curriculum(BaseModel):
    """The full curriculum for a topic. Generated once, then filled with posts."""

    topic_id: str
    title: str
    description: str
    modules: list[Module]
    # High-level interest category. Set by the caller; matches
    # interest_categories.category_id in the API DB so the feed can group topics.
    category_id: Optional[str] = None


class Offset(BaseModel):
    """The 4-tuple that locates a post in the curriculum.

    The feed service uses this to track per-user progress. Ordering is
    lexicographic on the tuple.
    """

    topic: str        # topic_id
    module: int       # module index within the topic (0-based)
    subtopic: int     # subtopic index within the module (0-based)
    seq: int          # sequence within a subtopic (which level, ordering of carousel items, etc.)

    def as_tuple(self) -> tuple[str, int, int, int]:
        return (self.topic, self.module, self.subtopic, self.seq)


class Post(BaseModel):
    """A single post in the feed.

    All three levels of a subtopic produce separate Post rows. So do tests.
    """

    post_id: str
    topic_id: str
    module_id: str
    subtopic_id: str

    # Curriculum offset
    offset_module: int
    offset_subtopic: int
    offset_seq: int = 0

    # Content
    level: Level
    content_type: ContentType
    title: str
    body: str
    image_prompts: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)  # raw AI backgrounds
    # Rendered cards (background + overlaid post text), one per carousel page.
    post_image_urls: list[str] = Field(default_factory=list)
    video_url: Optional[str] = None

    # Test fields (only set when content_type == TEST)
    test_type: Optional[TestType] = None
    question: Optional[str] = None
    options: Optional[list[str]] = None
    correct_index: Optional[int] = None
    explanation: Optional[str] = None
    blocking: bool = False

    # Pacing
    estimated_duration_sec: int = 30
    prerequisites: list[str] = Field(default_factory=list)

    # Vector for dedup
    embedding: Optional[list[float]] = None

    # Bookkeeping
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = ""

    def offset(self) -> Offset:
        return Offset(
            topic=self.topic_id,
            module=self.offset_module,
            subtopic=self.offset_subtopic,
            seq=self.offset_seq,
        )
