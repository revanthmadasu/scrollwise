"""End-to-end pipeline: topic -> curriculum -> posts -> tests -> DB."""

from __future__ import annotations

from dataclasses import dataclass

from generators._logging import get_logger
from generators.canonicalizer import TopicCanonicalizer
from generators.curriculum import CurriculumGenerator
from generators.embedding_client import EmbeddingClient
from generators.image_client import ImageClient
from generators.llm_client import LLMClient
from generators.models import Curriculum, Level, Post
from generators.post import PostGenerator
from generators.post_image_renderer import PostImageRenderer
from generators.test_post import TestGenerator
from storage.repository import CurriculumKeyConflict, Repository

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """Outcome of a pipeline run. `reused` is True when an equivalent topic
    already existed and was reused instead of generated (the dedup hit)."""

    curriculum: Curriculum
    reused: bool


class Pipeline:
    """Orchestrates curriculum + post + test generation for a topic.

    Test cadence: insert a test post after every N subtopics in a module.
    """

    def __init__(
        self,
        repo: Repository,
        llm: LLMClient,
        images: ImageClient,
        embeddings: EmbeddingClient,
        test_cadence: int = 3,
        renderer: PostImageRenderer | None = None,
    ):
        self.repo = repo
        self.canonicalizer = TopicCanonicalizer(llm)
        self.curriculum_gen = CurriculumGenerator(llm)
        self.post_gen = PostGenerator(llm, images, embeddings, renderer=renderer)
        self.test_gen = TestGenerator(llm, embeddings)
        self.test_cadence = test_cadence

    def run(
        self,
        topic_title: str,
        num_modules: int = 3,
        subtopics_per_module: int = 4,
        levels: list[Level] | None = None,
        skip_curriculum_if_exists: bool = True,
    ) -> PipelineResult:
        """Generate a curriculum (or reuse an existing equivalent) and fill it
        with posts. Returns a PipelineResult; `reused` is True on a dedup hit."""

        if levels is None:
            levels = [Level.SUMMARY, Level.STANDARD, Level.DEEP]

        # 1. Canonicalize the request to a normalized key for topic-level dedup.
        canonical_title, canonical_key = self.canonicalizer.canonicalize(topic_title)

        # 2. Reuse an existing equivalent topic if one exists.
        if skip_curriculum_if_exists:
            existing = self.repo.find_curriculum_by_canonical_key(canonical_key)
            if existing is not None:
                logger.info(
                    "curriculum_reused",
                    extra={"topic_id": existing.topic_id, "canonical_key": canonical_key},
                )
                return PipelineResult(curriculum=existing, reused=True)

        # 3. Miss -> generate. The canonical_key UNIQUE index guards against a
        #    concurrent worker that also missed the lookup: its save loses the
        #    race with CurriculumKeyConflict, and we reuse the winner's topic.
        curriculum = self.curriculum_gen.generate(
            topic_title=canonical_title,
            num_modules=num_modules,
            subtopics_per_module=subtopics_per_module,
        )
        curriculum.canonical_key = canonical_key
        try:
            self.repo.save_curriculum(curriculum)
        except CurriculumKeyConflict:
            existing = self.repo.find_curriculum_by_canonical_key(canonical_key)
            if existing is not None:
                logger.info(
                    "curriculum_reused_after_race",
                    extra={"topic_id": existing.topic_id, "canonical_key": canonical_key},
                )
                return PipelineResult(curriculum=existing, reused=True)
            raise

        # 2. Posts and tests
        all_posts: list[Post] = []
        failures = 0

        for module_idx, module in enumerate(curriculum.modules):
            since_last_test = 0
            offset_subtopic_cursor = 0

            for subtopic_idx, subtopic in enumerate(module.subtopics):
                # Generate one post per level for this subtopic
                for level in levels:
                    if self.repo.has_post_at_offset(
                        curriculum.topic_id, module_idx, offset_subtopic_cursor, int(level)
                    ):
                        logger.info(
                            "post_skipped",
                            extra={
                                "subtopic_id": subtopic.subtopic_id,
                                "level": int(level),
                                "offset": (module_idx, offset_subtopic_cursor, int(level)),
                            },
                        )
                        continue
                    try:
                        post = self.post_gen.generate_for_subtopic(
                            topic_id=curriculum.topic_id,
                            topic_title=curriculum.title,
                            module=module,
                            module_index=module_idx,
                            subtopic=subtopic,
                            subtopic_index=offset_subtopic_cursor,
                            level=level,
                        )
                    except Exception:  # noqa: BLE001 — isolate one bad post, keep the run going
                        failures += 1
                        logger.error(
                            "post_failed",
                            extra={
                                "subtopic_id": subtopic.subtopic_id,
                                "level": int(level),
                            },
                            exc_info=True,
                        )
                        continue
                    # Use seq to disambiguate the three levels at the same offset
                    post.offset_seq = int(level)
                    self.repo.save_post(post)
                    all_posts.append(post)

                since_last_test += 1
                offset_subtopic_cursor += 1

                # Insert a test post if we've hit the cadence, OR at the end of the module
                is_last = subtopic_idx == len(module.subtopics) - 1
                if since_last_test >= self.test_cadence or is_last:
                    # Find which subtopics this test covers (everything since the last test)
                    covered_from = max(0, subtopic_idx - since_last_test + 1)
                    covered = module.subtopics[covered_from:subtopic_idx + 1]

                    if not self.repo.has_post_at_offset(
                        curriculum.topic_id, module_idx, offset_subtopic_cursor, 0
                    ):
                        try:
                            test_post = self.test_gen.generate(
                                topic_id=curriculum.topic_id,
                                topic_title=curriculum.title,
                                module=module,
                                module_index=module_idx,
                                covered_subtopics=covered,
                                offset_subtopic=offset_subtopic_cursor,
                            )
                            self.repo.save_post(test_post)
                            all_posts.append(test_post)
                        except Exception:  # noqa: BLE001 — isolate one bad test
                            failures += 1
                            logger.error(
                                "test_failed",
                                extra={"module_id": module.module_id},
                                exc_info=True,
                            )
                    offset_subtopic_cursor += 1
                    since_last_test = 0

        logger.info(
            "pipeline_complete",
            extra={
                "topic_id": curriculum.topic_id,
                "post_count": len(all_posts),
                "failures": failures,
            },
        )
        return PipelineResult(curriculum=curriculum, reused=False)
