"""Generates a curriculum (topic -> modules -> subtopics) from a topic name."""

from __future__ import annotations

from generators._logging import get_logger
from generators.llm_client import LLMClient, parse_json_response
from generators.models import Curriculum
from prompts.templates import CURRICULUM_SYSTEM, CURRICULUM_USER

logger = get_logger(__name__)


class CurriculumGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(
        self,
        topic_title: str,
        num_modules: int = 3,
        subtopics_per_module: int = 4,
    ) -> Curriculum:
        logger.info(
            "generating_curriculum",
            extra={
                "topic": topic_title,
                "modules": num_modules,
                "subtopics_per_module": subtopics_per_module,
            },
        )

        user_prompt = CURRICULUM_USER.format(
            topic_title=topic_title,
            num_modules=num_modules,
            subtopics_per_module=subtopics_per_module,
        )

        response = self.llm.complete(
            system=CURRICULUM_SYSTEM,
            user=user_prompt,
            max_tokens=4096,
            temperature=0.5,
        )

        data = parse_json_response(response)
        curriculum = Curriculum.model_validate(data)

        logger.info(
            "curriculum_generated",
            extra={
                "topic_id": curriculum.topic_id,
                "module_count": len(curriculum.modules),
                "subtopic_count": sum(len(m.subtopics) for m in curriculum.modules),
            },
        )
        return curriculum
