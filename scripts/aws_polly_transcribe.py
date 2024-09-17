#!/usr/bin/env python3
"""
Transcribe Evaluator: Generate, synthesize, and transcribe stories to evaluate Amazon Transcribe.

This script uses a custom vocabulary to generate a story with AWS Bedrock,
converts it to speech with Amazon Polly, and then transcribes it back to text
using Amazon Transcribe. It creates a unique S3 bucket for the evaluation process.
"""

import json
import time
from pathlib import Path
from typing import List, Optional
import os
import uuid

import boto3
import click
import csv
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field
from functools import lru_cache
from itertools import chain

class VocabularyTerm(BaseModel):
    """Represents a term in the custom vocabulary."""
    phrase: str
    sounds_like: Optional[str] = None
    ipa: Optional[str] = None
    display_as: str
    notes: Optional[str] = None

class StoryConfig(BaseModel):
    """Configuration for story generation."""
    max_tokens: int = Field(default=500, ge=1, le=1000)
    temperature: float = Field(default=0.7, ge=0, le=1)
    top_p: float = Field(default=0.9, ge=0, le=1)

@lru_cache(maxsize=1)
def get_bedrock_client():
    """Get a cached Bedrock client."""
    return boto3.client('bedrock-runtime')

@lru_cache(maxsize=1)
def get_polly_client():
    """Get a cached Polly client."""
    return boto3.client('polly')

@lru_cache(maxsize=1)
def get_transcribe_client():
    """Get a cached Transcribe client."""
    return boto3.client('transcribe')

@lru_cache(maxsize=1)
def get_s3_client():
    """Get a cached S3 client."""
    return boto3.client('s3')

def create_unique_bucket(base_name: str) -> str:
    """
    Create a unique S3 bucket for the evaluation.

    Args:
        base_name (str): Base name for the bucket.

    Returns:
        str: Name of the created bucket.
    """
    s3 = get_s3_client()
    bucket_name = f"{base_name}-{uuid.uuid4().hex[:8]}"
    try:
        s3.create_bucket(Bucket=bucket_name)
        click.echo(f"Created bucket: {bucket_name}")
    except ClientError as e:
        click.echo(f"Error creating bucket: {e}")
        raise
    return bucket_name

def clean_up_bucket(bucket_name: str):
    """
    Remove all objects from the bucket and delete it.

    Args:
        bucket_name (str): Name of the bucket to clean up.
    """
    s3 = get_s3_client()
    try:
        bucket = boto3.resource('s3').Bucket(bucket_name)
        bucket.objects.all().delete()
        bucket.delete()
        click.echo(f"Deleted bucket: {bucket_name}")
    except ClientError as e:
        click.echo(f"Error deleting bucket: {e}")

def read_custom_vocabulary(file_path: Path) -> List[VocabularyTerm]:
    """
    Read the custom vocabulary from a CSV file.

    Args:
        file_path (Path): Path to the CSV file.

    Returns:
        List[VocabularyTerm]: List of vocabulary terms.
    """
    with file_path.open('r') as csvfile:
        reader = csv.DictReader(csvfile)
        return [VocabularyTerm(**row) for row in reader]

def generate_story_with_bedrock(terms: List[str], config: StoryConfig) -> str:
    """
    Generate a story using AWS Bedrock with the given terms.

    Args:
        terms (List[str]): List of terms to include in the story.
        config (StoryConfig): Configuration for story generation.

    Returns:
        str: Generated story.
    """
    client = get_bedrock_client()
    prompt = (
        f"Write a short story (two paragraphs) using as many of the following terms "
        f"as possible: {', '.join(terms)}. The story should be about a tech "
        f"professional facing a challenging situation."
    )
    
    body = json.dumps({
        "prompt": prompt,
        "max_tokens_to_sample": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
    })
    
    response = client.invoke_model(modelId="anthropic.claude-v2", body=body)
    response_body = json.loads(response['body'].read())
    return response_body['completion']

def synthesize_speech(text: str, output_file: Path) -> None:
    """
    Synthesize speech from text using Amazon Polly.

    Args:
        text (str): Text to synthesize.
        output_file (Path): Path to save the audio file.
    """
    client = get_polly_client()
    response = client.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId='Joanna'
    )
    
    with output_file.open('wb') as file:
        file.write(response['AudioStream'].read())

def transcribe_audio(file_name: str, bucket: str) -> str:
    """
    Transcribe audio using Amazon Transcribe.

    Args:
        file_name (str): Name of the audio file in S3.
        bucket (str): S3 bucket name.

    Returns:
        str: Transcribed text.
    """
    client = get_transcribe_client()
    job_name = f"Transcription-Job-{int(time.time())}"
    job_uri = f"s3://{bucket}/{file_name}"
    
    client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': job_uri},
        MediaFormat='mp3',
        LanguageCode='en-US'
    )
    
    while True:
        status = client.get_transcription_job(TranscriptionJobName=job_name)
        if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
            break
        time.sleep(5)
    
    if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
        response = get_s3_client().get_object(Bucket=bucket, Key=f"{job_name}.json")
        transcript = json.loads(response['Body'].read().decode('utf-8'))
        return transcript['results']['transcripts'][0]['transcript']
    else:
        raise Exception("Transcription failed")

@click.command()
@click.option('--vocabulary-file', type=click.Path(exists=True), default='resources/aws-transcribe-custom-vocabulary.csv',
              help='Path to the custom vocabulary CSV file')
@click.option('--output-dir', type=click.Path(), default='output',
              help='Directory to store output files')
def main(vocabulary_file: str, output_dir: str):
    """
    Main function to orchestrate the story generation, synthesis, and transcription process.
    """
    vocabulary_path = Path(vocabulary_file)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Create a unique S3 bucket
    user = os.environ.get('USER', 'user')
    bucket_name = create_unique_bucket(f"transcribe-eval-{user}")

    try:
        # Read custom vocabulary
        vocab_terms = read_custom_vocabulary(vocabulary_path)
        display_terms = list(set(chain.from_iterable(term.display_as.split() for term in vocab_terms)))

        # Generate story
        story_config = StoryConfig()
        story = generate_story_with_bedrock(display_terms, story_config)
        story_file = output_path / 'generated_story.txt'
        story_file.write_text(story)
        click.echo(f"Original story saved to {story_file}")

        # Synthesize speech
        audio_file = output_path / 'story_audio.mp3'
        synthesize_speech(story, audio_file)
        click.echo(f"Audio file saved to {audio_file}")

        # Upload audio to S3
        s3_client = get_s3_client()
        s3_client.upload_file(str(audio_file), bucket_name, audio_file.name)

        # Transcribe audio
        try:
            transcript = transcribe_audio(audio_file.name, bucket_name)
            transcript_file = output_path / 'transcribed_story.txt'
            transcript_file.write_text(transcript)
            click.echo(f"Transcribed story saved to {transcript_file}")
        except Exception as e:
            click.echo(f"Transcription failed: {str(e)}")

    finally:
        # Clean up the S3 bucket
        clean_up_bucket(bucket_name)

if __name__ == "__main__":
    main()
