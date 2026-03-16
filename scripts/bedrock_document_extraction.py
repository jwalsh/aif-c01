"""Bedrock document extraction pipeline with few-shot prompting.

Higher-level CLI and library for extracting structured data from documents
stored in S3, using Bedrock converse API and Step Functions orchestration.

Ported from aws-samples/intelligent-document-processing-with-amazon-bedrock,
adapted to project conventions.
"""

import json
import time
from typing import Any, Dict, List, Optional

import boto3
import click
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from bedrock_converse import (
    BedrockConverseClient,
    ExtractionAttribute,
    InferenceConfig,
    build_extraction_prompt,
    extract_attributes,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class FewShotExample(BaseModel):
    """A few-shot example for document extraction."""

    input: str = Field(description="Example document text")
    output: Dict[str, Any] = Field(description="Expected extraction result")


class ExtractionRequest(BaseModel):
    """Parameters for a document extraction request."""

    documents: List[str] = Field(description="S3 keys for documents to process")
    attributes: List[ExtractionAttribute]
    instructions: str = ""
    few_shots: List[FewShotExample] = Field(default_factory=list)
    model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0"
    temperature: float = 0.0
    parsing_mode: str = Field(
        default="Amazon Textract",
        description="Amazon Textract, Amazon Bedrock LLM, or Bedrock Data Automation",
    )


class ExtractionResult(BaseModel):
    """Result from extracting attributes from a single document."""

    file_key: str
    attributes: Dict[str, Any]
    raw_response: str = ""


# ---------------------------------------------------------------------------
# Few-shot prompt builder
# ---------------------------------------------------------------------------


FEW_SHOT_TEMPLATE = """<example>
<document>
{input_text}
</document>

Attributes to be extracted:
<attributes>
{{attributes}}
</attributes>

Output:
{output_text}
</example>
"""


def build_few_shot_prompt(
    document: str,
    attributes: List[ExtractionAttribute],
    few_shots: List[FewShotExample],
    instructions: str = "",
) -> str:
    """Build a prompt with few-shot examples prepended."""
    base_prompt = build_extraction_prompt(document, attributes, instructions)

    if not few_shots:
        return base_prompt

    examples_text = ""
    for example in few_shots:
        examples_text += FEW_SHOT_TEMPLATE.format(
            input_text=example.input,
            output_text=json.dumps(example.output, indent=2),
        )

    return examples_text + "\n" + base_prompt


# ---------------------------------------------------------------------------
# S3 document loader
# ---------------------------------------------------------------------------


class DocumentLoader:
    """Load documents from S3 for extraction."""

    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client("s3", region_name=region)

    def load_text(self, file_key: str) -> str:
        """Load a text document from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response["Body"].read().decode("utf-8")
        except ClientError as error:
            click.echo(f"Error loading {file_key}: {error}", err=True)
            raise

    def store_result(self, file_key: str, result: Dict[str, Any]) -> str:
        """Store extraction results back to S3."""
        output_key = f"attributes/{file_key.rsplit('.', 1)[0]}.json"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=output_key,
            Body=json.dumps(result, indent=2),
            ContentType="application/json",
        )
        return output_key


# ---------------------------------------------------------------------------
# Step Functions orchestration
# ---------------------------------------------------------------------------


class ExtractionPipeline:
    """Orchestrate document extraction via Step Functions or direct Bedrock."""

    def __init__(
        self,
        region: str = "us-east-1",
        bucket_name: Optional[str] = None,
        state_machine_arn: Optional[str] = None,
    ):
        self.region = region
        self.bucket_name = bucket_name
        self.state_machine_arn = state_machine_arn
        self.bedrock_client = BedrockConverseClient(region=region)
        if bucket_name:
            self.document_loader = DocumentLoader(bucket_name, region)
        else:
            self.document_loader = None

    def extract_from_text(
        self,
        document: str,
        attributes: List[ExtractionAttribute],
        model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0",
        instructions: str = "",
        few_shots: Optional[List[FewShotExample]] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Extract attributes directly from text via Bedrock converse."""
        inference_config = InferenceConfig(temperature=temperature)
        return extract_attributes(
            client=self.bedrock_client,
            model_id=model_id,
            document=document,
            attributes=attributes,
            instructions=instructions,
            inference_config=inference_config,
        )

    def extract_via_step_functions(
        self,
        request: ExtractionRequest,
    ) -> List[ExtractionResult]:
        """Submit extraction job to Step Functions and poll for results."""
        if not self.state_machine_arn:
            raise ValueError("state_machine_arn required for Step Functions mode")

        sfn_client = boto3.client("stepfunctions", region_name=self.region)

        event = json.dumps(
            {
                "attributes": [attr.model_dump() for attr in request.attributes],
                "documents": request.documents,
                "instructions": request.instructions,
                "few_shots": [shot.model_dump() for shot in request.few_shots],
                "model_params": {
                    "model_id": request.model_id,
                    "output_length": 2000,
                    "temperature": request.temperature,
                },
                "parsing_mode": request.parsing_mode,
            }
        )

        execution_response = sfn_client.start_execution(
            stateMachineArn=self.state_machine_arn,
            input=event,
        )
        execution_arn = execution_response["executionArn"]
        click.echo(f"Started execution: {execution_arn}", err=True)

        while True:
            time.sleep(2)
            status_response = sfn_client.describe_execution(executionArn=execution_arn)
            status = status_response["status"]

            if status == "FAILED":
                error_detail = status_response.get("error", "Unknown error")
                raise RuntimeError(f"Step Function execution failed: {error_detail}")

            if status == "SUCCEEDED":
                outputs = json.loads(status_response["output"])
                return [
                    ExtractionResult(
                        file_key=output["llm_answer"]["file_key"],
                        attributes=output["llm_answer"]["answer"],
                    )
                    for output in outputs
                ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Document extraction pipeline using Bedrock and Step Functions."""
    pass


@cli.command()
@click.option("--model-id", default="us.anthropic.claude-3-haiku-20240307-v1:0")
@click.option("--region", default="us-east-1")
@click.option("--temperature", default=0.0, type=float)
@click.option("--instructions", default="", help="Additional extraction instructions")
@click.argument("document_path", type=click.Path(exists=True))
@click.argument("attributes_json")
def extract_local(
    model_id: str,
    region: str,
    temperature: float,
    instructions: str,
    document_path: str,
    attributes_json: str,
) -> None:
    """Extract attributes from a local text file.

    ATTRIBUTES_JSON is a JSON array, e.g.:

      '[{"name": "customer_name", "description": "name of the customer"}]'
    """
    from pathlib import Path

    document_text = Path(document_path).read_text(encoding="utf-8")
    raw_attributes = json.loads(attributes_json)
    attributes = [ExtractionAttribute(**attr) for attr in raw_attributes]

    pipeline = ExtractionPipeline(region=region)
    result = pipeline.extract_from_text(
        document=document_text,
        attributes=attributes,
        model_id=model_id,
        instructions=instructions,
        temperature=temperature,
    )
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.option("--model-id", default="us.anthropic.claude-3-haiku-20240307-v1:0")
@click.option("--region", default="us-east-1")
@click.option("--bucket", required=True, envvar="BUCKET_NAME")
@click.option("--state-machine-arn", required=True, envvar="STATE_MACHINE_ARN")
@click.option("--parsing-mode", default="Amazon Textract")
@click.option("--temperature", default=0.0, type=float)
@click.option("--instructions", default="")
@click.argument("document_keys", nargs=-1, required=True)
@click.argument("attributes_json")
def extract_s3(
    model_id: str,
    region: str,
    bucket: str,
    state_machine_arn: str,
    parsing_mode: str,
    temperature: float,
    instructions: str,
    document_keys: tuple,
    attributes_json: str,
) -> None:
    """Extract attributes from S3 documents via Step Functions.

    DOCUMENT_KEYS are one or more S3 keys.
    ATTRIBUTES_JSON is the last argument, a JSON array of attribute definitions.
    """
    raw_attributes = json.loads(attributes_json)
    attributes = [ExtractionAttribute(**attr) for attr in raw_attributes]

    request = ExtractionRequest(
        documents=list(document_keys),
        attributes=attributes,
        model_id=model_id,
        temperature=temperature,
        instructions=instructions,
        parsing_mode=parsing_mode,
    )

    pipeline = ExtractionPipeline(
        region=region,
        bucket_name=bucket,
        state_machine_arn=state_machine_arn,
    )
    results = pipeline.extract_via_step_functions(request)

    output = [result.model_dump(exclude={"raw_response"}) for result in results]
    click.echo(json.dumps(output, indent=2))


@cli.command()
def list_models() -> None:
    """List supported Bedrock model IDs for extraction."""
    from bedrock_converse import BEDROCK_MODEL_TOKEN_LIMITS

    for model_prefix, token_limit in sorted(BEDROCK_MODEL_TOKEN_LIMITS.items()):
        click.echo(f"  {model_prefix:<40} {token_limit:>10,} tokens")


if __name__ == "__main__":
    cli()
