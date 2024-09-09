import os
import click
import fnmatch
from pathlib import Path
from functools import lru_cache
import anthropic
import openai
# import boto3
from typing import List, Tuple
import difflib
import requests
import json
import importlib
import subprocess
import sys

# Try to import optional dependencies
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

def install_dependencies():
    """Install missing dependencies."""
    dependencies = [
        "anthropic",
        "openai",
        "google-generativeai",
        "boto3",
        "requests",
    ]
    for dep in dependencies:
        try:
            importlib.import_module(dep.replace("-", "_"))
        except ImportError:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
    
    print("All dependencies installed. Please restart the script.")
    sys.exit(0)

def is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary."""
    try:
        with file_path.open("rb") as file:
            return b"\0" in file.read(1024)
    except IOError:
        return False

@lru_cache(maxsize=1)
def get_gitignore_patterns(project_path: Path) -> Tuple[str, ...]:
    """Get gitignore patterns from the .gitignore file."""
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        return tuple()

    with gitignore_path.open("r", encoding="utf-8", errors="ignore") as gitignore_file:
        return tuple(
            line.strip()
            for line in gitignore_file
            if line.strip() and not line.startswith("#")
        )

@lru_cache(maxsize=1024)
def is_ignored(file_path: str, gitignore_patterns: Tuple[str, ...]) -> bool:
    """Check if a file should be ignored based on various criteria."""
    path = Path(file_path)

    if path.name == "README.org":
        return False

    if path.name.startswith("."):
        return True

    lockfiles = [
        "poetry.lock",
        "Pipfile.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ]
    if path.name in lockfiles:
        return True

    if path.name == "output":
        return True

    return any(fnmatch.fnmatch(file_path, pattern) for pattern in gitignore_patterns)

@lru_cache(maxsize=1024)
def is_sensitive_file(file_path: str) -> bool:
    """Check if a file is potentially sensitive."""
    sensitive_patterns = [
        ".env",
        ".envrc",
        "id_rsa",
        "id_dsa",
        ".pem",
        ".key",
        "password",
        "secret",
    ]
    return any(
        pattern in Path(file_path).name.lower() for pattern in sensitive_patterns
    )

def get_relevant_files(project_path: Path) -> List[Tuple[Path, int]]:
    """Get all relevant files in the project directory with priority."""
    gitignore_patterns = get_gitignore_patterns(project_path)
    relevant_files = []

    priority_extensions = ['.org', '.md', '.py', '.js', '.ts', '.go', '.rs', '.java', '.c', '.cpp', '.h', '.hpp']
    priority_names = ['README', 'Makefile']

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for file in files:
            file_path = Path(root) / file
            if (
                not is_ignored(str(file_path), gitignore_patterns)
                and not is_binary_file(file_path)
                and not is_sensitive_file(str(file_path))
            ):
                priority = 0
                if file_path.suffix in priority_extensions:
                    priority = priority_extensions.index(file_path.suffix) + 1
                elif file_path.stem in priority_names:
                    priority = len(priority_extensions) + priority_names.index(file_path.stem) + 1
                else:
                    priority = len(priority_extensions) + len(priority_names) + 1
                
                relevant_files.append((file_path, priority))

    # Sort files by priority (lower number means higher priority)
    relevant_files.sort(key=lambda x: x[1])

    return relevant_files

@lru_cache(maxsize=1024)
def read_file_content(file_path: Path) -> str:
    """Read file content with error handling and multiple encoding attempts."""
    encodings = ["utf-8", "latin-1", "ascii"]
    for encoding in encodings:
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return f"[Unable to read file: {file_path}]"

@lru_cache(maxsize=1024)
def get_file_type(file_path: Path) -> str:
    """Determine the file type based on its extension."""
    extension = file_path.suffix.lower()
    if extension == ".py":
        return "PYTHON"
    elif extension == ".org":
        return "ORG"
    elif file_path.name == "Makefile":
        return "MAKEFILE"
    elif extension == ".sh":
        return "BASH"
    else:
        return "OTHER"

def generate_archive(project_path: Path, relevant_files: List[Tuple[Path, int]]) -> str:
    """Generate a custom archive format containing all relevant files with content limiting."""
    archive_content = "# Project Archive\n\n"
    total_chars = 0
    char_limit = 150000  # Adjust this value to control the total content size

    for file_path, _ in relevant_files:
        relative_path = file_path.relative_to(project_path)
        file_type = get_file_type(file_path)
        content = read_file_content(file_path)

        # Limit content for large files
        if len(content) > 1000:  # Adjust this threshold as needed
            content = content[:1000] + "\n... (content truncated) ...\n" + content[-1000:]

        file_content = f"### BEGIN FILE {relative_path} ({file_type})\n{content}\n### END FILE {relative_path}\n\n"
        
        if total_chars + len(file_content) > char_limit:
            archive_content += "... (remaining files omitted due to size constraints) ..."
            break

        archive_content += file_content
        total_chars += len(file_content)

    return archive_content

def generate_prompt(archive_content: str) -> str:
    """Generate a prompt for the LLM to check README and Makefile alignment."""
    prompt = "Based on the following project structure and file contents, please review the README and Makefile to ensure they are aligned with the project:\n\n"
    prompt += archive_content
    prompt += "\nPlease analyze the contents of these files and provide suggestions to improve the alignment between the README and Makefile. Consider the following aspects:\n"
    prompt += "1. Are all important files and directories mentioned in the README?\n"
    prompt += "2. Do the build and run instructions in the README match the Makefile targets?\n"
    prompt += "3. Are there any discrepancies between the project structure and what's described in the README?\n"
    prompt += "4. Are there any Makefile targets that are not documented in the README?\n"
    prompt += "5. Are there any features or dependencies mentioned in the README that are not reflected in the Makefile?\n"
    prompt += "\nProvide your suggestions in the form of a patch that can be applied to the README and Makefile."

    return prompt

def send_to_claude(prompt: str) -> str:
    """Send the generated prompt to Claude and get the response."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    return response.content[0].text

def send_to_openai(prompt: str) -> str:
    """Send the generated prompt to OpenAI and get the response."""
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI assistant tasked with analyzing project structure and alignment between README and Makefile."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content

def send_to_gemini(prompt: str) -> str:
    """Send the generated prompt to Gemini and get the response."""
    if not GEMINI_AVAILABLE:
        raise ImportError("Google Generative AI library is not installed. Run the script with --install-dependencies to install it.")
    
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return response.text

def send_to_bedrock(prompt: str) -> str:
    """Send the generated prompt to Amazon Bedrock and get the response."""
    bedrock = boto3.client(service_name='bedrock-runtime')
    response = bedrock.invoke_model(
        modelId='anthropic.claude-v2',
        body=json.dumps({
            "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
            "max_tokens_to_sample": 4096
        })
    )
    return json.loads(response['body'].read())['completion']

def send_to_ollama(prompt: str, model: str = "llama2") -> str:
    """Send the generated prompt to Ollama and get the response."""
    url = "http://localhost:11434/api/generate"
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()['response']
    else:
        raise Exception(f"Error from Ollama: {response.text}")

def generate_patch(original_content: str, updated_content: str) -> str:
    """Generate a patch from the original content to the updated content."""
    original_lines = original_content.splitlines(keepends=True)
    updated_lines = updated_content.splitlines(keepends=True)
    
    diff = difflib.unified_diff(original_lines, updated_lines, fromfile="original", tofile="updated", n=3)
    return ''.join(diff)

@click.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=str(Path.cwd()),
)
@click.option(
    "--use-llm", type=click.Choice(['claude', 'openai', 'gemini', 'bedrock', 'ollama']), help="Use an LLM to analyze the prompt"
)
@click.option(
    "--ollama-model", default="llama2", help="Specify the Ollama model to use (default: llama2)"
)
@click.option(
    "--install-dependencies", is_flag=True, help="Install missing dependencies"
)
def main(project_path: str, use_llm: str, ollama_model: str, install_dependencies: bool):
    """Generate a prompt for an LLM to check README and Makefile alignment."""
    if install_dependencies:
        install_dependencies()
    
    project_path = Path(project_path)
    project_name = project_path.name
    output_path = project_path.parent / f"{project_name}_review.txt"

    relevant_files = get_relevant_files(project_path)
    archive_content = generate_archive(project_path, relevant_files)
    prompt = generate_prompt(archive_content)

    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(prompt)

    click.echo(f"Prompt generated and saved to {output_path}")

    if use_llm:
        click.echo(f"Sending prompt to {use_llm.capitalize()} for analysis...")
        try:
            if use_llm == 'claude':
                llm_response = send_to_claude(prompt)
            elif use_llm == 'openai':
                llm_response = send_to_openai(prompt)
            elif use_llm == 'gemini':
                llm_response = send_to_gemini(prompt)
            elif use_llm == 'bedrock':
                llm_response = send_to_bedrock(prompt)
            elif use_llm == 'ollama':
                llm_response = send_to_ollama(prompt, ollama_model)
        
            # Generate patch
            readme_path = project_path / "README.org"
            makefile_path = project_path / "Makefile"
            
            original_readme = read_file_content(readme_path)
            original_makefile = read_file_content(makefile_path)
            
            # Assuming the LLM response contains updated content for both files
            updated_readme, updated_makefile = parse_llm_response(llm_response)
            
            readme_patch = generate_patch(original_readme, updated_readme)
            makefile_patch = generate_patch(original_makefile, updated_makefile)
            
            patch_output_path = output_path.with_name(f"{project_name}_{use_llm}_patch.diff")
            with patch_output_path.open("w", encoding="utf-8") as patch_file:
                patch_file.write(readme_patch)
                patch_file.write(makefile_patch)
            
            click.echo(f"{use_llm.capitalize()}'s analysis saved as a patch to {patch_output_path}")
        except ImportError as e:
            click.echo(f"Error: {str(e)}")
            click.echo("Run the script with --install-dependencies to install missing libraries.")
        except Exception as e:
            click.echo(f"An error occurred: {str(e)}")

def parse_llm_response(response: str) -> Tuple[str, str]:
    """Parse the LLM response to extract updated README and Makefile content."""
    # This is a simplified implementation. You may need to adjust it based on the actual format of the LLM response.
    parts = response.split("### Updated Makefile")
    updated_readme = parts[0].replace("### Updated README", "").strip()
    updated_makefile = parts[1].strip() if len(parts) > 1 else ""
    return updated_readme, updated_makefile

if __name__ == "__main__":
    main()
