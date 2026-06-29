"""LLM fill pass for templates that need structured content.

When a selected template requires fields the deterministic adapter can't supply
(stats, steps, options, a headline figure, …), this reshapes the already-written
post into the template's field-spec — grounded strictly in the generated text,
not a fresh generation. Output is validated/clamped against the field-spec.
"""

from __future__ import annotations

from generators._logging import get_logger
from generators.llm_client import LLMClient, parse_json_response
from generators.templating import TemplateSpec, describe_fields, validate_inputs
from prompts.templates import TEMPLATE_FILL_SYSTEM, TEMPLATE_FILL_USER

logger = get_logger(__name__)


class TemplateFiller:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def fill(self, spec: TemplateSpec, *, title: str, body: str) -> dict:
        """Produce template_inputs conforming to ``spec`` from the post content.

        Raises on an unparseable response so the caller can fall back to the
        deterministic inputs (or leave the post untemplated).
        """
        user = TEMPLATE_FILL_USER.format(
            title=title, body=body, schema=describe_fields(spec)
        )
        raw = self.llm.complete(
            system=TEMPLATE_FILL_SYSTEM,
            user=user,
            max_tokens=700,
            temperature=0.4,
        )
        data = parse_json_response(raw)
        inputs = validate_inputs(spec, data)
        logger.info(
            "template_filled",
            extra={"template_id": spec.template_id, "fields": list(inputs.keys())},
        )
        return inputs
