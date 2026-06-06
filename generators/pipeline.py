"""End-to-end pipeline: topic -> curriculum -> posts -> tests -> DB."""

from __future__ import annotations

from generators._logging import get_logger
from generators.curriculum import CurriculumGenerator
from generators.embedding_client import EmbeddingClient
from generators.image_client import ImageClient
from generators.llm_client import LLMClient
from generators.models import Curriculum, Level, Post
from generators.post import PostGenerator
from generators.post_image_renderer import PostImageRenderer
from generators.test_post import TestGenerator
from storage.repository import Repository

logger = get_logger(__name__)


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
    ) -> Curriculum:
        """Generate a curriculum (or reuse existing) and fill it with posts."""

        if levels is None:
            levels = [Level.SUMMARY, Level.STANDARD, Level.DEEP]

        # 1. Curriculum
        curriculum = None
        if skip_curriculum_if_exists:
            curriculum = self.repo.find_curriculum_by_title(topic_title)
            if curriculum:
                logger.info(
                    "curriculum_reused",
                    extra={"topic_id": curriculum.topic_id},
                )

        if curriculum is None:
            curriculum = self.curriculum_gen.generate(
                topic_title=topic_title,
                num_modules=num_modules,
                subtopics_per_module=subtopics_per_module,
            )
            self.repo.save_curriculum(curriculum)

        # 2. Posts and tests
        all_posts: list[Post] = []

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
                    post = self.post_gen.generate_for_subtopic(
                        topic_id=curriculum.topic_id,
                        topic_title=curriculum.title,
                        module=module,
                        module_index=module_idx,
                        subtopic=subtopic,
                        subtopic_index=offset_subtopic_cursor,
                        level=level,
                    )
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
                    offset_subtopic_cursor += 1
                    since_last_test = 0

        logger.info(
            "pipeline_complete",
            extra={
                "topic_id": curriculum.topic_id,
                "post_count": len(all_posts),
            },
        )
        return curriculum
