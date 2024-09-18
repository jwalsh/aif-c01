import json
import time
from pathlib import Path
import os
import uuid
import asyncio
import csv
import io

import boto3
import click
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field
from functools import lru_cache
from typing import List

class VocabularyTerm(BaseModel):
    phrase: str
    sounds_like: str = None
    ipa: str = None
    display_as: str = None

class StoryConfig(BaseModel):
    max_tokens: int = Field(default=500, ge=1, le=1000)
    temperature: float = Field(default=0.7, ge=0, le=1)
    top_p: float = Field(default=0.9, ge=0, le=1)

@lru_cache(maxsize=1)
def get_client(service_name):
    return boto3.client(service_name)

def ensure_bucket_exists(bucket_name: str) -> None:
    s3 = get_client('s3')
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError:
        try:
            s3.create_bucket(Bucket=bucket_name)
            click.echo(f"Created bucket: {bucket_name}")
        except ClientError as e:
            click.echo(f"Error creating bucket: {e}")
            raise

def read_custom_vocabulary(file_path: Path) -> List[VocabularyTerm]:
    with file_path.open('r') as file:
        reader = csv.DictReader(file)
        vocab_terms = []
        for row in reader:
            term = VocabularyTerm(
                phrase=row['Phrase'],
                sounds_like=row.get('SoundsLike'),
                ipa=row.get('IPA'),
                display_as=row.get('DisplayAs') or row['Phrase']  # Use Phrase if DisplayAs is empty
            )
            vocab_terms.append(term)
    return vocab_terms

def create_processed_csv(vocab_terms: List[VocabularyTerm], bucket: str) -> str:
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=['Phrase', 'SoundsLike', 'IPA', 'DisplayAs'])
    writer.writeheader()
    for term in vocab_terms:
        writer.writerow({
            'Phrase': term.phrase,
            'SoundsLike': term.sounds_like or '',
            'IPA': term.ipa or '',
            'DisplayAs': term.display_as
        })
    
    s3 = get_client('s3')
    file_name = f'processed_vocabulary_{int(time.time())}.csv'
    s3.put_object(Bucket=bucket, Key=file_name, Body=csv_buffer.getvalue())
    click.echo(f"Processed CSV uploaded to s3://{bucket}/{file_name}")
    return file_name

def generate_story_with_bedrock(terms: list[str], config: StoryConfig) -> str:
    client = get_client('bedrock-runtime')
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
    client = get_client('polly')
    response = client.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId='Joanna'
    )
    
    with output_file.open('wb') as file:
        file.write(response['AudioStream'].read())

async def create_custom_vocabulary(vocabulary_name: str, vocab_terms: List[VocabularyTerm]) -> None:
    client = get_client('transcribe')
    
    phrases = []
    for term in vocab_terms:
        phrase_entry = {
            'Phrase': term.phrase,
            'DisplayAs': term.display_as
        }
        if term.sounds_like:
            phrase_entry['SoundsLike'] = term.sounds_like.split('-')
        if term.ipa:
            phrase_entry['IPA'] = term.ipa
        phrases.append(phrase_entry)
    
    try:
        response = client.create_vocabulary(
            VocabularyName=vocabulary_name,
            LanguageCode='en-US',
            Phrases=phrases
        )
        click.echo(f"Custom vocabulary creation initiated: {response['VocabularyName']}")
        
        while True:
            status = client.get_vocabulary(VocabularyName=vocabulary_name)
            if status['VocabularyState'] in ['READY', 'FAILED']:
                break
            await asyncio.sleep(5)
        
        if status['VocabularyState'] == 'READY':
            click.echo(f"Custom vocabulary '{vocabulary_name}' is ready for use.")
        else:
            click.echo(f"Custom vocabulary creation failed: {status['FailureReason']}")
    except ClientError as e:
        click.echo(f"Error creating custom vocabulary: {e}")
        raise

def send_sms_notification(phone_number: str, message: str):
    sns = get_client('sns')
    try:
        response = sns.publish(
            PhoneNumber=phone_number,
            Message=message
        )
        click.echo(f"SMS sent successfully. Message ID: {response['MessageId']}")
    except ClientError as e:
        click.echo(f"Error sending SMS: {e}")

async def transcribe_audio(file_name: str, input_bucket: str, output_bucket: str, vocabulary_name: str, phone_number: str) -> str:
    client = get_client('transcribe')
    sqs = get_client('sqs')
    
    queue_name = f'aif-c01-transcribe-job-queue-{uuid.uuid4().hex[:8]}'
    queue_url = sqs.create_queue(QueueName=queue_name)['QueueUrl']
    
    job_name = f"aif-c01-Transcription-Job-{int(time.time())}"
    job_uri = f"s3://{input_bucket}/{file_name}"
    
    try:
        client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_uri},
            MediaFormat='mp3',
            LanguageCode='en-US',
            Settings={'VocabularyName': vocabulary_name},
            OutputBucketName=output_bucket,
            OutputKey=f"{job_name}-output.json"
        )
        
        while True:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20
            )
            
            if 'Messages' in response:
                message = json.loads(response['Messages'][0]['Body'])
                if message['detail']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=response['Messages'][0]['ReceiptHandle']
                    )
                    break
            
            await asyncio.sleep(5)
        
        if message['detail']['TranscriptionJobStatus'] == 'COMPLETED':
            s3 = get_client('s3')
            response = s3.get_object(Bucket=output_bucket, Key=f"{job_name}-output.json")
            transcript = json.loads(response['Body'].read().decode('utf-8'))
            send_sms_notification(phone_number, "Transcription job completed successfully.")
            return transcript['results']['transcripts'][0]['transcript']
        else:
            send_sms_notification(phone_number, "Transcription job failed.")
            raise Exception("Transcription failed")
    finally:
        sqs.delete_queue(QueueUrl=queue_url)

@click.command()
@click.option('--vocabulary-file', type=click.Path(exists=True), default='resources/aws-transcribe-custom-vocabulary.csv',
              help='Path to the custom vocabulary CSV file')
@click.option('--output-dir', type=click.Path(), default='output',
              help='Directory to store output files')
@click.option('--phone-number', type=str, default='+12064287778',
              help='Phone number to receive SMS notifications')
@click.option('--input-bucket', type=str, default='aif-c01-input',
              help='Name of the S3 bucket for input files')
@click.option('--output-bucket', type=str, default='aif-c01-output',
              help='Name of the S3 bucket for output files')
@click.option('--confirm-upload', is_flag=True, help='Only confirm bucket upload')
def cli(vocabulary_file: str, output_dir: str, phone_number: str, input_bucket: str, output_bucket: str, confirm_upload: bool):
    asyncio.run(main(vocabulary_file, output_dir, phone_number, input_bucket, output_bucket, confirm_upload))

async def main(vocabulary_file: str, output_dir: str, phone_number: str, input_bucket: str, output_bucket: str, confirm_upload: bool):
    vocabulary_path = Path(vocabulary_file)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    ensure_bucket_exists(input_bucket)
    ensure_bucket_exists(output_bucket)

    if confirm_upload:
        click.echo(f"Input bucket '{input_bucket}' and output bucket '{output_bucket}' are ready for use.")
        return

    try:
        vocab_terms = read_custom_vocabulary(vocabulary_path)
        
        # Create and upload processed CSV
        processed_csv_file = create_processed_csv(vocab_terms, output_bucket)
        click.echo(f"Processed CSV file uploaded to S3: s3://{output_bucket}/{processed_csv_file}")
        
        display_terms = [term.display_as for term in vocab_terms if term.display_as]

        vocabulary_name = f"aif-c01-custom-vocab-{uuid.uuid4().hex[:8]}"
        await create_custom_vocabulary(vocabulary_name, vocab_terms)

        story_config = StoryConfig()
        story = generate_story_with_bedrock(display_terms, story_config)
        story_file = output_path / 'aif-c01-generated_story.txt'
        story_file.write_text(story)
        click.echo(f"Original story saved to {story_file}")

        audio_file = output_path / 'aif-c01-story_audio.mp3'
        synthesize_speech(story, audio_file)
        click.echo(f"Audio file saved to {audio_file}")

        s3_client = get_client('s3')
        s3_client.upload_file(str(audio_file), input_bucket, audio_file.name)
        click.echo(f"Audio file uploaded to {input_bucket}/{audio_file.name}")

        transcript = await transcribe_audio(audio_file.name, input_bucket, output_bucket, vocabulary_name, phone_number)
        transcript_file = output_path / 'aif-c01-transcribed_story.txt'
        transcript_file.write_text(transcript)
        click.echo(f"Transcribed story saved to {transcript_file}")

    except Exception as e:
        click.echo(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    cli()
