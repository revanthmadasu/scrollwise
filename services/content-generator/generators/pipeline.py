"""End-to-end pipeline: topic -> curriculum -> posts -> tests -> DB."""

from __future__ import annotations

import os
import uuid
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
from generators.template_fill import TemplateFiller
from generators.templating import (
    build_inputs,
    needs_fill,
    select_template,
    specs_from_rows,
    validate_inputs,
)
from generators.test_post import TestGenerator
from storage.repository import CurriculumKeyConflict, Repository

logger = get_logger(__name__)

# Truthy/falsy spellings accepted for boolean env flags, so ops can write
# whichever reads naturally in a .env or systemd unit.
_FALSY = {"0", "false", "no", "off", ""}


def image_posts_enabled_from_env() -> bool:
    """Feature flag: may non-templated posts generate background images?

    Image-based posts are the legacy rendering path — an AI background with the
    post text overlaid. They are the most expensive thing the pipeline does
    (image-backend calls + S3), and the feed is moving to data-driven templates,
    so this defaults OFF: a post that doesn't match a template is produced as
    plain text instead of hitting the image backend. Templated posts skip images
    regardless of this flag.

    Set IMAGE_POSTS_ENABLED to a truthy value (1/true/yes/on) to re-enable the
    legacy image-background path.
    """
    return os.environ.get("IMAGE_POSTS_ENABLED", "false").strip().lower() not in _FALSY


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
        image_posts_enabled: bool = False,
    ):
        self.repo = repo
        self.canonicalizer = TopicCanonicalizer(llm)
        self.curriculum_gen = CurriculumGenerator(llm)
        self.post_gen = PostGenerator(llm, images, embeddings, renderer=renderer)
        self.test_gen = TestGenerator(llm, embeddings)
        self.test_cadence = test_cadence
        # Feature flag (see image_posts_enabled_from_env). When False, posts that
        # don't match a template are emitted as plain text rather than generating
        # an image background. Templated posts skip images either way.
        self.image_posts_enabled = image_posts_enabled
        logger.info(
            "pipeline_init",
            extra={
                "test_cadence": test_cadence,
                "image_posts_enabled": image_posts_enabled,
            },
        )
        # Approved-template catalog for data-driven rendering, loaded once.
        # Empty when the API hasn't approved any (or the table isn't present) —
        # posts then carry no template and render the legacy way.
        self.template_catalog = specs_from_rows(self.repo.list_approved_templates())
        # Reshapes generated content into a template's field-spec when it needs
        # structured fields (stats/steps/…) the deterministic adapter can't fill.
        self.filler = TemplateFiller(llm)

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
        # Recently-used template ids in this topic, to vary the feed's look.
        recent_templates: list[str] = []

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
                    post_id = str(uuid.uuid4())
                    try:
                        text = self.post_gen.generate_text(
                            topic_title=curriculum.title,
                            module=module,
                            subtopic=subtopic,
                            level=level,
                        )
                        # Select a template up front, so a template-rendered post
                        # skips background image generation entirely (it draws its
                        # own background). Only non-templated posts hit the image
                        # backend — and only when the image-posts flag is on.
                        spec = self._select_template(text, level, recent_templates, post_id)
                        post = self.post_gen.build_post(
                            text,
                            post_id=post_id,
                            topic_id=curriculum.topic_id,
                            module=module,
                            module_index=module_idx,
                            subtopic=subtopic,
                            subtopic_index=offset_subtopic_cursor,
                            level=level,
                            make_images=spec is None and self.image_posts_enabled,
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
                    if spec is not None:
                        self._apply_template(post, spec, recent_templates)
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

    def _select_template(self, text, level: Level, recent: list[str], post_id: str):
        """Choose an approved template before image generation, or None.

        Selection runs on the text alone (content_type 'text', no image) so a
        templated post can skip the image backend — templates draw their own
        background. Image-only templates simply don't match here, by design.
        """
        if not self.template_catalog:
            return None
        return select_template(
            content_type="text",
            level=int(level),
            body_len=len(text.body or ""),
            has_image=False,
            catalog=self.template_catalog,
            recent=recent,
            post_id=post_id,
            can_fill=self.filler is not None,
        )

    def _apply_template(self, post: Post, spec, recent: list[str]) -> None:
        """Adapt the post's content into the selected template's inputs, running
        the LLM fill pass when the template needs structured fields. On a failed
        fill the post is left untemplated (renders as plain text)."""
        deterministic = build_inputs(spec, title=post.title, body=post.body, image_url=None)
        inputs = deterministic
        if needs_fill(spec):
            try:
                filled = self.filler.fill(spec, title=post.title, body=post.body)
                # title/body stay authoritative; the fill supplies the structural
                # fields (stats, steps, options, …).
                inputs = validate_inputs(spec, {**filled, **deterministic})
            except Exception:  # noqa: BLE001 — a bad fill leaves the post untemplated
                logger.error(
                    "template_fill_failed",
                    extra={"post_id": post.post_id, "template_id": spec.template_id},
                    exc_info=True,
                )
                return

        post.template_id = spec.template_id
        post.template_inputs = inputs
        recent.append(spec.template_id)
        del recent[:-3]  # keep only the last 3
