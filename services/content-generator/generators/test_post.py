"""Generates test posts (MCQs) that gate progression through a module."""

from __future__ import annotations

import uuid

from generators._logging import get_logger
from generators.embedding_client import EmbeddingClient
from generators.llm_client import LLMClient, parse_json_response
from generators.models import ContentType, Level, Module, Post, Subtopic, TestType
from prompts.templates import TEST_SYSTEM, TEST_USER

logger = get_logger(__name__)


class TestGenerator:
    def __init__(self, llm: LLMClient, embeddings: EmbeddingClient):
        self.llm = llm
        self.embeddings = embeddings

    def generate(
        self,
        topic_id: str,
        topic_title: str,
        module: Module,
        module_index: int,
        covered_subtopics: list[Subtopic],
        offset_subtopic: int,
    ) -> Post:
        subtopics_summary = "\n".join(
            f"- {s.title}: {s.description}" for s in covered_subtopics
        )

        user_prompt = TEST_USER.format(
            topic_title=topic_title,
            module_title=module.title,
            subtopics_summary=subtopics_summary,
        )

        response = self.llm.complete(
            system=TEST_SYSTEM,
            user=user_prompt,
            max_tokens=512,
            temperature=0.5,
        )

        data = parse_json_response(response)

        question = data["question"]
        options = data["options"]
        correct = int(data["correct_index"])
        explanation = data["explanation"]

        # Light validation
        if not 0 <= correct < len(options):
            raise ValueError(f"correct_index {correct} out of range for {len(options)} options")

        embedding = self.embeddings.embed(f"TEST: {question}")

        post = Post(
            post_id=str(uuid.uuid4()),
            topic_id=topic_id,
            module_id=module.module_id,
            subtopic_id=f"{module.module_id}__test",
            offset_module=module_index,
            offset_subtopic=offset_subtopic,
            offset_seq=0,
            # Tests are level-agnostic — same test for all levels
            level=Level.STANDARD,
            content_type=ContentType.TEST,
            title=f"Check: {module.title}",
            body=question,
            test_type=TestType.MCQ,
            question=question,
            options=options,
            correct_index=correct,
            explanation=explanation,
            blocking=True,
            estimated_duration_sec=20,
            prerequisites=[s.subtopic_id for s in covered_subtopics],
            embedding=embedding,
            model_version=self.llm.model_version,
        )

        logger.info(
            "test_generated",
            extra={
                "post_id": post.post_id,
                "module_id": module.module_id,
                "covered": len(covered_subtopics),
            },
        )
        return post
