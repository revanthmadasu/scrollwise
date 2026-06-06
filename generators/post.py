"""Generates posts for a subtopic at a given granularity level."""

from __future__ import annotations

import uuid

from generators._logging import get_logger
from generators.embedding_client import EmbeddingClient
from generators.image_client import ImageClient
from generators.llm_client import LLMClient, parse_json_response
from generators.models import ContentType, Level, Module, Post, Subtopic
from generators.post_image_renderer import PostImageRenderer
from prompts.templates import LEVEL_DESCRIPTIONS, POST_SYSTEM, POST_USER

logger = get_logger(__name__)

# Rough read-time mapping
DURATION_BY_LEVEL = {
    Level.SUMMARY: 5,
    Level.STANDARD: 30,
    Level.DEEP: 120,
}


class PostGenerator:
    def __init__(
        self,
        llm: LLMClient,
        images: ImageClient,
        embeddings: EmbeddingClient,
        renderer: PostImageRenderer | None = None,
    ):
        self.llm = llm
        self.images = images
        self.embeddings = embeddings
        # Optional: composes post text over the background into feed cards.
        # When None (e.g. stub image backend), posts keep raw backgrounds only.
        self.renderer = renderer

    def generate_for_subtopic(
        self,
        topic_id: str,
        topic_title: str,
        module: Module,
        module_index: int,
        subtopic: Subtopic,
        subtopic_index: int,
        level: Level,
    ) -> Post:
        level_name, level_description, word_budget = LEVEL_DESCRIPTIONS[int(level)]

        user_prompt = POST_USER.format(
            topic_title=topic_title,
            module_title=module.title,
            subtopic_title=subtopic.title,
            subtopic_description=subtopic.description,
            learning_objective=subtopic.learning_objective,
            level_name=level_name,
            level_description=level_description,
            level_word_budget=word_budget,
        )

        # Higher temperature for longer-form content (more variation in voice)
        temperature = 0.6 if level == Level.SUMMARY else 0.75
        max_tokens = 512 if level == Level.SUMMARY else 1024 if level == Level.STANDARD else 4096

        response = self.llm.complete(
            system=POST_SYSTEM,
            user=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            data = parse_json_response(response)

        except ValueError as e:
            logger.error("Failed to parse LLM response", extra={"error": str(e), "response": response})
            raise

        # Generate background images from prompts
        image_prompts = data.get("image_prompts", [])
        image_urls = [self.images.generate(p) for p in image_prompts]

        # Compose the post text over the first background into feed card(s).
        # Long bodies paginate into multiple cards (a carousel).
        post_image_urls: list[str] = []
        if self.renderer and image_urls:
            post_image_urls = self.renderer.render_from_url(
                image_urls[0], data["title"], data["body"]
            )

        # Content type: prefer the rendered cards; fall back to raw backgrounds.
        cards = post_image_urls or image_urls
        content_type = ContentType.TEXT
        if len(cards) == 1:
            content_type = ContentType.IMAGE_POST
        elif len(cards) > 1:
            content_type = ContentType.CAROUSEL

        # Embed on title + body for dedup
        embedding = self.embeddings.embed(f"{data['title']}\n\n{data['body']}")

        post = Post(
            post_id=str(uuid.uuid4()),
            topic_id=topic_id,
            module_id=module.module_id,
            subtopic_id=subtopic.subtopic_id,
            offset_module=module_index,
            offset_subtopic=subtopic_index,
            offset_seq=0,
            level=level,
            content_type=content_type,
            title=data["title"],
            body=data["body"],
            image_prompts=image_prompts,
            image_urls=image_urls,
            post_image_urls=post_image_urls,
            estimated_duration_sec=DURATION_BY_LEVEL[level],
            prerequisites=subtopic.prerequisites,
            embedding=embedding,
            model_version=self.llm.model_version,
        )

        logger.info(
            "post_generated",
            extra={
                "post_id": post.post_id,
                "subtopic_id": subtopic.subtopic_id,
                "level": int(level),
                "body_chars": len(post.body),
                "images": len(image_urls),
                "cards": len(post_image_urls),
            },
        )
        return post
