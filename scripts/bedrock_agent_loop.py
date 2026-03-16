"""Bedrock agentic loop with tool use.

Demonstrates the core agent pattern: converse API call -> check stop reason ->
execute tools -> feed results back -> repeat until end_turn. This is the
fundamental building block for Bedrock Agents and Strands Agents.

Ported from aws-samples/sample-agentic-ai-demos and
aws-samples/sample-why-agents-fail, adapted to project conventions.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

import boto3
import click
from botocore.config import Config
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("bedrock-agent")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class ToolDefinition(BaseModel):
    """Schema for a tool that the agent can invoke."""

    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    """Registry mapping tool names to callables and their Bedrock schemas."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a tool with its handler and schema."""
        self._tools[name] = handler
        self._schemas[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
        )

    def get_handler(self, name: str) -> Callable:
        """Look up a tool handler by name."""
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def to_bedrock_config(self) -> Dict[str, Any]:
        """Convert registry to Bedrock toolConfig format."""
        tool_specs = []
        for tool_definition in self._schemas.values():
            spec: Dict[str, Any] = {
                "toolSpec": {
                    "name": tool_definition.name,
                    "description": tool_definition.description,
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": tool_definition.parameters,
                        }
                    },
                }
            }
            tool_specs.append(spec)
        return {"tools": tool_specs}

    @property
    def tool_names(self) -> List[str]:
        return list(self._tools.keys())


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


class AgentLoop:
    """Bedrock converse agent loop with tool use.

    Implements the standard agentic pattern:
      1. Send messages to model
      2. If stop_reason is tool_use, execute tools
      3. Append tool results to message history
      4. Repeat until end_turn or max iterations
    """

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        system_prompt: str = "",
        max_iterations: int = 10,
    ) -> None:
        bedrock_config = Config(
            connect_timeout=120,
            read_timeout=120,
            retries={"max_attempts": 3},
        )
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=bedrock_config,
        )
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.registry = ToolRegistry()
        self.messages: List[Dict[str, Any]] = []

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a tool the agent can invoke."""
        self.registry.register(name, handler, description, parameters)

    def run(self, user_input: str) -> str:
        """Execute the agent loop for a user input, returning final text."""
        self.messages.append({"role": "user", "content": [{"text": user_input}]})

        for iteration in range(self.max_iterations):
            logger.info("Iteration %d", iteration + 1)

            kwargs: Dict[str, Any] = {
                "modelId": self.model_id,
                "messages": self.messages,
                "inferenceConfig": {
                    "temperature": 0.0,
                    "maxTokens": 4096,
                },
            }
            if self.system_prompt:
                kwargs["system"] = [{"text": self.system_prompt}]
            if self.registry.tool_names:
                kwargs["toolConfig"] = self.registry.to_bedrock_config()

            try:
                response = self.client.converse(**kwargs)
            except ClientError as error:
                logger.error("Bedrock error: %s", error)
                return f"Error: {error}"

            stop_reason = response.get("stopReason", "end_turn")
            assistant_message = response["output"]["message"]
            self.messages.append(assistant_message)

            if stop_reason in ("end_turn", "stop_sequence"):
                return self._extract_text(assistant_message)

            if stop_reason == "tool_use":
                tool_results = self._execute_tools(assistant_message)
                self.messages.append({"role": "user", "content": tool_results})
                continue

            if stop_reason == "max_tokens":
                logger.warning("Max tokens reached, requesting continuation")
                self.messages.append(
                    {"role": "user", "content": [{"text": "Continue."}]}
                )
                continue

        logger.warning("Max iterations (%d) reached", self.max_iterations)
        return self._extract_text(self.messages[-1])

    def _execute_tools(self, assistant_message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all tool_use blocks in an assistant message."""
        results = []
        for content_block in assistant_message.get("content", []):
            if "toolUse" not in content_block:
                continue

            tool_use = content_block["toolUse"]
            tool_name = tool_use["name"]
            tool_input = tool_use.get("input", {})
            tool_use_id = tool_use["toolUseId"]

            logger.info("Calling tool: %s(%s)", tool_name, tool_input)

            try:
                handler = self.registry.get_handler(tool_name)
                tool_output = handler(**tool_input)
                results.append(
                    {
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"text": str(tool_output)}],
                        }
                    }
                )
            except Exception as tool_error:
                logger.error("Tool %s failed: %s", tool_name, tool_error)
                results.append(
                    {
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"text": f"Error: {tool_error}"}],
                            "status": "error",
                        }
                    }
                )
        return results

    def _extract_text(self, message: Dict[str, Any]) -> str:
        """Extract text content from a message."""
        text_parts = []
        for content_block in message.get("content", []):
            if "text" in content_block:
                text_parts.append(content_block["text"])
        return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Built-in example tools
# ---------------------------------------------------------------------------


def tool_get_weather(city: str) -> str:
    """Get current weather for a city (stub for demonstration)."""
    weather_data = {
        "seattle": "62F, cloudy",
        "new york": "75F, sunny",
        "london": "55F, rainy",
        "tokyo": "80F, humid",
    }
    return weather_data.get(city.lower(), f"No weather data for {city}")


def tool_calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    allowed_chars = set("0123456789+-*/.() ")
    if not all(character in allowed_chars for character in expression):
        return "Error: expression contains invalid characters"
    try:
        result = eval(expression)  # noqa: S307
        return str(result)
    except Exception as evaluation_error:
        return f"Error: {evaluation_error}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--model-id", default="us.anthropic.claude-3-haiku-20240307-v1:0")
@click.option("--region", default="us-east-1")
@click.option("--max-iterations", default=10, type=int)
@click.argument("prompt")
def main(model_id: str, region: str, max_iterations: int, prompt: str) -> None:
    """Run a Bedrock agent loop with example tools.

    Demonstrates the converse API tool-use cycle: the model decides which
    tools to call, results are fed back, and the loop continues until
    the model produces a final answer.
    """
    agent = AgentLoop(
        model_id=model_id,
        region=region,
        system_prompt="You are a helpful assistant with access to tools.",
        max_iterations=max_iterations,
    )

    agent.register_tool(
        name="get_weather",
        handler=tool_get_weather,
        description="Get current weather for a city",
        parameters={
            "city": {"type": "string", "description": "City name"},
        },
    )

    agent.register_tool(
        name="calculate",
        handler=tool_calculate,
        description="Evaluate a mathematical expression",
        parameters={
            "expression": {
                "type": "string",
                "description": "Math expression to evaluate",
            },
        },
    )

    result = agent.run(prompt)
    click.echo(result)


if __name__ == "__main__":
    main()
