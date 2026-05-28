"""Pluggable LLM client.

Default backend is the Anthropic API. To swap in a self-hosted OpenAI-compatible
server (vLLM, Ollama, LM Studio, TGI), set:

    LLM_BACKEND=openai_compatible
    LLM_BASE_URL=http://localhost:8000/v1
    LLM_API_KEY=anything
    LLM_MODEL=meta-llama/Llama-3.1-70B-Instruct

To use Amazon Bedrock (AWS-native, IAM auth, no separate API key):

    LLM_BACKEND=bedrock
    LLM_MODEL=anthropic.claude-opus-4-5        # or any Bedrock model ID
    AWS_REGION=us-east-1                        # defaults to us-east-1

The interface is a single `complete()` method that takes a system prompt and a
user prompt and returns the text response. JSON parsing is the caller's job.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

from generators._logging import get_logger

logger = get_logger(__name__)


class LLMClient(Protocol):
    model_version: str

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        ...


class AnthropicLLMClient:
    """Default backend: Anthropic API."""

    def __init__(self, model: str = "claude-opus-4-7"):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model
        self.model_version = f"anthropic:{model}"

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Extract text from response blocks
        out: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                out.append(block.text)
        return "".join(out)


class OpenAICompatibleLLMClient:
    """For self-hosted vLLM, Ollama, etc.

    Requires `pip install openai`.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str = "no-key-needed",
    ):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai package not installed. pip install openai"
            ) from e

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.model_version = f"openai_compat:{model}@{base_url}"

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


class BedrockLLMClient:
    """Amazon Bedrock backend. Uses IAM credentials — no separate API key needed.

    Supports any Bedrock model that accepts the Converse API (Claude, Llama,
    Mistral, Titan, etc.). Requires `pip install boto3`.

    Auth is resolved by boto3 in the standard order: env vars
    (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), ~/.aws/credentials, or the
    ECS/EC2 instance role — the last one is the right choice in production.
    """

    def __init__(
        self,
        model: str = "anthropic.claude-opus-4-5",
        region: str | None = None,
    ):
        try:
            import boto3
        except ImportError as e:
            raise RuntimeError("boto3 not installed. pip install boto3") from e

        self.model = model
        self.model_version = f"bedrock:{model}"
        region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        response = self.client.converse(
            modelId=self.model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        return response["output"]["message"]["content"][0]["text"]


def get_llm_client() -> LLMClient:
    """Factory. Reads LLM_BACKEND env var."""
    backend = os.environ.get("LLM_BACKEND", "anthropic")
    model = os.environ.get("LLM_MODEL", "claude-opus-4-7")

    if backend == "anthropic":
        return AnthropicLLMClient(model=model)
    elif backend == "bedrock":
        bedrock_model = os.environ.get("LLM_MODEL", "anthropic.claude-opus-4-5")
        return BedrockLLMClient(model=bedrock_model)
    elif backend == "openai_compatible":
        base_url = os.environ["LLM_BASE_URL"]
        api_key = os.environ.get("LLM_API_KEY", "no-key-needed")
        return OpenAICompatibleLLMClient(
            model=model, base_url=base_url, api_key=api_key
        )
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {backend}")


def parse_json_response(text: str) -> dict:
    """Robustly extract JSON from an LLM response.

    Handles common patterns: ```json fenced blocks, leading prose, trailing text.
    """
    text = text.strip()
    # Strip fenced code blocks
    if text.startswith("```"):
        # Find the first newline after the opening fence
        first_nl = text.find("\n")
        if first_nl >= 0:
            text = text[first_nl + 1:]
        # Strip the closing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Find the first { and last } to slice out the JSON
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        logger.error("json_parse_failed", extra={"snippet": text[:500]})
        raise ValueError(f"Could not parse JSON: {e}") from e
