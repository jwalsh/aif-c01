import os
import click
import fnmatch
from pathlib import Path
from functools import lru_cache
import anthropic
from typing import List, Tuple

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
        "poetry.lock", "Pipfile.lock", "package-lock.json",
        "yarn.lock", "pnpm-lock.yaml",
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
        ".env", ".envrc", "id_rsa", "id_dsa", ".pem", ".key", "password", "secret",
    ]
    return any(pattern in Path(file_path).name.lower() for pattern in sensitive_patterns)

def get_relevant_files(project_path: Path) -> List[Path]:
    """Get all relevant files in the project directory."""
    gitignore_patterns = get_gitignore_patterns(project_path)
    relevant_files = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for file in files:
            file_path = Path(root) / file
            if (
                not is_ignored(str(file_path), gitignore_patterns)
                and not is_binary_file(file_path)
                and not is_sensitive_file(str(file_path))
            ):
                relevant_files.append(file_path)

    readme_path = project_path / "README.org"
    if readme_path.exists() and readme_path not in relevant_files:
        relevant_files.append(readme_path)

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

def generate_archive(project_path: Path, relevant_files: List[Path]) -> str:
    """Generate a custom archive format containing all relevant files."""
    archive_content = "# Project Archive\n\n"

    for file_path in relevant_files:
        relative_path = file_path.relative_to(project_path)
        file_type = get_file_type(file_path)
        content = read_file_content(file_path)

        archive_content += f"### BEGIN FILE {relative_path} ({file_type})\n"
        archive_content += content
        archive_content += f"\n### END FILE {relative_path}\n\n"

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

    return prompt

def send_to_claude(prompt: str) -> str:
    """Send the generated prompt to Claude and get the response."""
    client = anthropic.Anthropic()
    response = client.beta.prompt_caching.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": "You are an AI assistant tasked with analyzing project structure and alignment between README and Makefile. Your goal is to provide insightful commentary and suggestions for improvement.",
            },
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[{"role": "user", "content": "Please analyze the project structure and alignment between README and Makefile as described in the prompt."}],
    )
    return response.content[0].text

@click.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=str(Path.cwd()),
)
@click.option(
    "--use-claude", is_flag=True, default=False, help="Use Claude to analyze the prompt"
)
def main(project_path: str, use_claude: bool):
    """Generate a prompt for an LLM to check README and Makefile alignment."""
    project_path = Path(project_path)
    project_name = project_path.name
    output_path = project_path.parent / f"{project_name}_review.txt"

    relevant_files = get_relevant_files(project_path)
    archive_content = generate_archive(project_path, relevant_files)
    prompt = generate_prompt(archive_content)

    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(prompt)

    click.echo(f"Prompt generated and saved to {output_path}")

    if use_claude:
        click.echo("Sending prompt to Claude for analysis...")
        claude_response = send_to_claude(prompt)
        claude_output_path = output_path.with_name(f"{project_name}_claude_analysis.txt")
        with claude_output_path.open("w", encoding="utf-8") as claude_file:
            claude_file.write(claude_response)
        click.echo(f"Claude's analysis saved to {claude_output_path}")

if __name__ == "__main__":
    main()
