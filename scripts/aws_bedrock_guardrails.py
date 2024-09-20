import click
import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field
from typing import List, Optional
import json

class GuardrailFilter(BaseModel):
    type: str
    inputStrength: str
    outputStrength: str

class Guardrail(BaseModel):
    id: str
    arn: str
    status: str
    name: str
    version: str
    createdAt: str
    updatedAt: str

class GuardrailDetail(BaseModel):
    name: str
    guardrailId: str
    guardrailArn: str
    version: str
    status: str
    contentPolicy: dict
    createdAt: str
    updatedAt: str

class BedrockClient:
    def __init__(self):
        self.client = boto3.client('bedrock')

    def list_guardrails(self):
        try:
            response = self.client.list_guardrails()
            return [Guardrail(**g) for g in response.get('guardrails', [])]
        except ClientError as e:
            click.echo(f"Error listing guardrails: {e}", err=True)
            return []

    def get_guardrail(self, guardrail_id):
        try:
            response = self.client.get_guardrail(guardrailIdentifier=guardrail_id)
            return GuardrailDetail(**response)
        except ClientError as e:
            click.echo(f"Error getting guardrail: {e}", err=True)
            return None

@click.group()
def cli():
    pass

@cli.command()
def list_guardrails():
    """List all guardrails"""
    client = BedrockClient()
    guardrails = client.list_guardrails()
    click.echo(json.dumps([g.dict() for g in guardrails], indent=2))

@cli.command()
@click.option('--guardrail-id', required=True, help='ID of the guardrail to retrieve')
def get_guardrail(guardrail_id):
    """Get details of a specific guardrail"""
    client = BedrockClient()
    guardrail = client.get_guardrail(guardrail_id)
    if guardrail:
        click.echo(json.dumps(guardrail.dict(), indent=2))

if __name__ == '__main__':
    cli()
