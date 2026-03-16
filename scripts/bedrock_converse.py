"""Bedrock converse API client with retry and token-aware truncation.

Demonstrates the modern Bedrock converse() API pattern with exponential
backoff, inference configuration, and middle-out document truncation for
context window management.

Ported from aws-samples/intelligent-document-processing-with-amazon-bedrock,
adapted to project conventions.
"""

import ast
import functools
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import click
from botocore.config import Config
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("bedrock-converse")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

BEDROCK_MODEL_TOKEN_LIMITS: Dict[str, int] = {
    "anthropic.claude-3-haiku": 200_000,
    "anthropic.claude-3-5-haiku": 200_000,
    "anthropic.claude-3-sonnet": 200_000,
    "anthropic.claude-3-5-sonnet": 200_000,
    "anthropic.claude-3-opus": 200_000,
    "anthropic.claude-sonnet-4": 200_000,
    "anthropic.claude-opus-4": 200_000,
    "amazon.nova-lite": 300_000,
    "amazon.nova-pro": 300_000,
    "amazon.nova-premier": 1_000_000,
    "amazon.titan-text-express": 8_192,
    "amazon.titan-text-lite": 4_096,
    "meta.llama3": 8_000,
    "mistral.mistral-large": 128_000,
}


class InferenceConfig(BaseModel):
    """Bedrock converse inference parameters."""

    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, gt=0)


class ConversationMessage(BaseModel):
    """A single message in a Bedrock conversation."""

    role: str = Field(description="Either 'user' or 'assistant'")
    content: str


class ConverseResponse(BaseModel):
    """Parsed response from a Bedrock converse call."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""
    model_id: str = ""


class ExtractionAttribute(BaseModel):
    """An attribute to extract from a document."""

    name: str
    description: str
    type: str = Field(default="auto", description="auto, character, number, true/false")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class BedrockConverseClient:
    """Thin wrapper around Bedrock converse API with retry logic."""

    def __init__(self, region: str = "us-east-1", max_retries: int = 5):
        bedrock_config = Config(
            connect_timeout=120,
            read_timeout=120,
            retries={"max_attempts": max_retries},
        )
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=bedrock_config,
        )
        self.region = region

    def converse(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        system_prompt: str = "",
        inference_config: Optional[InferenceConfig] = None,
    ) -> ConverseResponse:
        """Invoke Bedrock converse API with retry on throttling."""
        if inference_config is None:
            inference_config = InferenceConfig()

        kwargs: Dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {
                "temperature": inference_config.temperature,
                "topP": inference_config.top_p,
                "maxTokens": inference_config.max_tokens,
            },
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        response = self._invoke_with_backoff(kwargs)
        return self._parse_response(response, model_id)

    def _invoke_with_backoff(
        self,
        kwargs: Dict[str, Any],
        max_attempts: int = 5,
    ) -> Dict[str, Any]:
        """Exponential backoff with jitter for throttling errors."""
        for attempt in range(max_attempts):
            try:
                return self.client.converse(**kwargs)
            except ClientError as error:
                error_code = error.response["Error"]["Code"]
                if error_code == "ThrottlingException" and attempt < max_attempts - 1:
                    wait_time = (2**attempt) + (time.time() % 1)
                    logger.warning(
                        "Throttled on attempt %d, waiting %.1fs",
                        attempt + 1,
                        wait_time,
                    )
                    time.sleep(wait_time)
                else:
                    raise
        raise RuntimeError("Exhausted retry attempts")

    def _parse_response(
        self,
        response: Dict[str, Any],
        model_id: str,
    ) -> ConverseResponse:
        """Extract text and usage from Bedrock converse response."""
        content_blocks = response["output"]["message"]["content"]
        text_blocks = [block for block in content_blocks if "text" in block]
        if len(text_blocks) != 1:
            logger.warning(
                "Expected 1 text block, got %d; using first", len(text_blocks)
            )
        text = text_blocks[0]["text"].strip() if text_blocks else ""

        usage = response.get("usage", {})
        return ConverseResponse(
            text=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            stop_reason=response.get("stopReason", ""),
            model_id=model_id,
        )


# ---------------------------------------------------------------------------
# Token estimation and truncation
# ---------------------------------------------------------------------------


def estimate_token_count(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return len(text) // 4


def get_max_input_tokens(model_id: str) -> int:
    """Look up context window size for a model, stripping region prefixes."""
    normalized_model_id = (
        model_id.removeprefix("us.").removeprefix("eu.").removeprefix("ap.")
    )
    for prefix, limit in BEDROCK_MODEL_TOKEN_LIMITS.items():
        if normalized_model_id.startswith(prefix):
            return limit
    logger.warning("Unknown model %s, defaulting to 100k tokens", model_id)
    return 100_000


def truncate_document(
    document: str,
    prompt_token_count: int,
    model_id: str,
    context_ratio: float = 0.75,
) -> str:
    """Truncate document from the middle to fit within model context window.

    Preserves the beginning and end of the document, which typically contain
    the most important context (headers, signatures, conclusions).
    """
    max_tokens = int(get_max_input_tokens(model_id) * context_ratio)
    available_tokens = max_tokens - prompt_token_count
    document_tokens = estimate_token_count(document)

    if document_tokens <= available_tokens:
        return document

    words = document.split(" ")
    midpoint = len(words) // 2
    tokens_to_cut = (document_tokens - available_tokens) // 2

    # Approximate words-to-tokens ratio
    words_to_cut = max(1, int(tokens_to_cut * len(words) / document_tokens))

    truncated_document = (
        " ".join(words[: midpoint - words_to_cut])
        + "\n...\n"
        + " ".join(words[midpoint + words_to_cut :])
    )

    logger.info(
        "Truncated document from %d to %d estimated tokens",
        document_tokens,
        estimate_token_count(truncated_document),
    )
    return truncated_document


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_json_from_response(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, handling <json></json> tags."""
    try:
        json_text = text.split("<json>", 1)[1].rsplit("</json>", 1)[0].strip()
    except (IndexError, ValueError):
        json_text = text.strip()

    json_text = re.sub(r"\n\n+", ",", json_text)

    if not json_text.startswith(("{", "[")):
        json_text = "{" + json_text
    if not json_text.endswith(("}", "]")):
        json_text = json_text + "}"

    json_text = json_text.replace("}}", "}").replace("{{", "{")

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return ast.literal_eval(json_text)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=4)
def load_prompt_template(template_name: str) -> str:
    """Load a prompt template from resources/prompts/."""
    prompts_directory = Path(__file__).parent.parent / "resources" / "prompts"
    template_path = prompts_directory / template_name
    return template_path.read_text(encoding="utf-8").strip()


def build_extraction_prompt(
    document: str,
    attributes: List[ExtractionAttribute],
    instructions: str = "",
) -> str:
    """Build a document extraction prompt from template and parameters."""
    template = load_prompt_template("document_extraction_user.txt")

    attributes_text = ""
    for index, attribute in enumerate(attributes, 1):
        line = f"{index}. {attribute.name}: {attribute.description}"
        if attribute.type.lower() != "auto":
            line += f" (must be {attribute.type.lower()})"
        attributes_text += line + "\n"

    prompt = template.format(document=document, attributes=attributes_text.strip())

    if instructions.strip():
        prompt += (
            "\n\nYou must follow these additional instructions:\n"
            f"<instructions>\n{instructions}\n</instructions>"
        )

    return prompt


# ---------------------------------------------------------------------------
# High-level extraction
# ---------------------------------------------------------------------------


def extract_attributes(
    client: BedrockConverseClient,
    model_id: str,
    document: str,
    attributes: List[ExtractionAttribute],
    instructions: str = "",
    inference_config: Optional[InferenceConfig] = None,
) -> Dict[str, Any]:
    """Extract structured attributes from a document via Bedrock converse."""
    system_prompt = load_prompt_template("document_extraction_system.txt")
    user_prompt = build_extraction_prompt(document, attributes, instructions)

    prompt_tokens = estimate_token_count(system_prompt + user_prompt)
    truncated_document = truncate_document(document, prompt_tokens, model_id)

    if truncated_document != document:
        user_prompt = build_extraction_prompt(
            truncated_document, attributes, instructions
        )

    messages = [{"role": "user", "content": [{"text": user_prompt}]}]

    response = client.converse(
        model_id=model_id,
        messages=messages,
        system_prompt=system_prompt,
        inference_config=inference_config,
    )

    logger.info(
        "Converse response: %d input tokens, %d output tokens, stop=%s",
        response.input_tokens,
        response.output_tokens,
        response.stop_reason,
    )

    return parse_json_from_response(response.text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Bedrock converse API utilities for document processing."""
    pass


@cli.command()
@click.option("--model-id", default="us.anthropic.claude-3-haiku-20240307-v1:0")
@click.option("--region", default="us-east-1")
@click.option("--temperature", default=0.0, type=float)
@click.option("--max-tokens", default=2048, type=int)
@click.argument("prompt")
def invoke(
    model_id: str,
    region: str,
    temperature: float,
    max_tokens: int,
    prompt: str,
) -> None:
    """Send a single prompt to Bedrock via the converse API."""
    client = BedrockConverseClient(region=region)
    inference_config = InferenceConfig(temperature=temperature, max_tokens=max_tokens)
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    response = client.converse(
        model_id=model_id,
        messages=messages,
        inference_config=inference_config,
    )
    click.echo(response.text)
    click.echo(
        f"\n---\nTokens: {response.input_tokens} in / {response.output_tokens} out",
        err=True,
    )


@cli.command()
@click.option("--model-id", default="us.anthropic.claude-3-haiku-20240307-v1:0")
@click.option("--region", default="us-east-1")
@click.option("--temperature", default=0.0, type=float)
@click.option("--instructions", default="", help="Additional extraction instructions")
@click.argument("document_path", type=click.Path(exists=True))
@click.argument("attributes_json")
def extract(
    model_id: str,
    region: str,
    temperature: float,
    instructions: str,
    document_path: str,
    attributes_json: str,
) -> None:
    """Extract structured attributes from a document.

    DOCUMENT_PATH is the path to a text file.
    ATTRIBUTES_JSON is a JSON array of attribute definitions, e.g.:

      '[{"name": "customer_name", "description": "name of the customer"}]'
    """
    document_text = Path(document_path).read_text(encoding="utf-8")
    raw_attributes = json.loads(attributes_json)
    attributes = [ExtractionAttribute(**attr) for attr in raw_attributes]

    client = BedrockConverseClient(region=region)
    inference_config = InferenceConfig(temperature=temperature)

    result = extract_attributes(
        client=client,
        model_id=model_id,
        document=document_text,
        attributes=attributes,
        instructions=instructions,
        inference_config=inference_config,
    )
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.argument("model_id", default="us.anthropic.claude-3-haiku-20240307-v1:0")
def token_limit(model_id: str) -> None:
    """Show the context window size for a model."""
    limit = get_max_input_tokens(model_id)
    click.echo(f"{model_id}: {limit:,} tokens")


if __name__ == "__main__":
    cli()
