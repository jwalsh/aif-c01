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

    # Exclude generated files
    generated_files = [
        "README.md",
        "workflow.png",
        "project_architecture.png",
    ]
    if path.name in generated_files:
        return True

    if path.is_relative_to(Path("export")):
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

    priority_extensions = [
        ".org",
        ".md",
        ".py",
        ".js",
        ".ts",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
    ]
    priority_names = ["README", "Makefile"]

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
                    priority = (
                        len(priority_extensions)
                        + priority_names.index(file_path.stem)
                        + 1
                    )
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
            content = (
                content[:1000] + "\n... (content truncated) ...\n" + content[-1000:]
            )

        file_content = f"### BEGIN FILE {relative_path} ({file_type})\n{content}\n### END FILE {relative_path}\n\n"

        if total_chars + len(file_content) > char_limit:
            archive_content += (
                "... (remaining files omitted due to size constraints) ..."
            )
            break

        archive_content += file_content
        total_chars += len(file_content)

    return archive_content


def generate_prompt(archive_content: str) -> str:
    """Generate a prompt for the LLM to check README and Makefile alignment with emphasis on literate programming and best practices."""
    prompt = """Based on the following project structure and file contents, please review the README and Makefile to ensure they are aligned with the project and follow best practices.

"""
    prompt += """

Please analyze the contents of these files and provide suggestions to improve the alignment between the README and Makefile, emphasizing the following aspects:

1. Literate Programming:
   - Encourage the use of org-mode for literate programming.
   - Suggest using babel for code execution within org files.
   - Recommend tangling code blocks to generate source files.

2. README Content:
   - Ensure all important files and directories are mentioned.
   - Verify that build and run instructions match the Makefile targets.
   - Check for discrepancies between the project structure and README descriptions.
   - Suggest adding sections on development workflow, testing, and contribution guidelines.

3. Makefile Targets:
   - Verify the presence of standard targets: run, test, lint, clean, install, etc.
   - Ensure all Makefile targets are documented in the README.
   - Suggest adding targets for common developer tasks and onboarding.

4. Python Best Practices:
   - Encourage the use of type hints (typing module) in all Python files.
   - Suggest using click for command-line interfaces where appropriate.
   - Recommend adding docstrings to all functions and classes.
   - Propose using itertools for efficient iteration where applicable.
   - Suggest incorporating pydantic for data validation and settings management.
   - Recommend using functools for higher-order functions and caching.

5. General Improvements:
   - Identify any features or dependencies mentioned in the README that are not reflected in the Makefile or code.
   - Suggest ways to improve project organization and maintainability.
   - Recommend adding or improving documentation for key components.

Please provide your suggestions in the form of a patch that can be applied to the README and Makefile. Additionally, if there are significant changes needed in Python files to align with the best practices mentioned, include those suggestions as well.

Emphasize the importance of literate programming with org-mode, babel, and tangle as a best practice for documentation and code organization. Also, stress the significance of having standard Makefile commands for a smooth developer onboarding experience and efficient workflow.

Archive Content: 
"""
    prompt += archive_content

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
            {
                "role": "system",
                "content": "You are an AI assistant tasked with analyzing project structure and alignment between README and Makefile.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def send_to_gemini(prompt: str) -> str:
    """Send the generated prompt to Gemini and get the response."""
    if not GEMINI_AVAILABLE:
        raise ImportError(
            "Google Generative AI library is not installed. Run the script with --install-dependencies to install it."
        )

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text


def send_to_bedrock(prompt: str) -> str:
    """Send the generated prompt to Amazon Bedrock and get the response."""
    bedrock = boto3.client(service_name="bedrock-runtime")
    response = bedrock.invoke_model(
        modelId="anthropic.claude-v2",
        body=json.dumps(
            {
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": 4096,
            }
        ),
    )
    return json.loads(response["body"].read())["completion"]


def send_to_ollama(prompt: str, model: str = "llama2") -> str:
    """Send the generated prompt to Ollama and get the response."""
    url = "http://localhost:11434/api/generate"
    data = {"model": model, "prompt": prompt, "stream": False}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()["response"]
    else:
        raise Exception(f"Error from Ollama: {response.text}")


def generate_patch(original_content: str, updated_content: str) -> str:
    """Generate a patch from the original content to the updated content."""
    original_lines = original_content.splitlines(keepends=True)
    updated_lines = updated_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines, updated_lines, fromfile="original", tofile="updated", n=3
    )
    return "".join(diff)


import os
from pathlib import Path
import click


def create_empty_patch_file(project_path: Path) -> str:
    """Create an empty patch file for the project at the same level as the project directory."""
    project_name = project_path.name
    patch_file_name = f"{project_name}_project_alignment.patch"
    patch_file_path = project_path.parent / patch_file_name

    with patch_file_path.open("w") as f:
        f.write("# This is an empty patch file for project alignment\n")
        f.write(f"# You can apply this patch using: patch -p0 < {patch_file_name}\n")

    return str(patch_file_path)


@click.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=str(Path.cwd()),
)
@click.option(
    "--use-llm",
    type=click.Choice(["claude", "openai", "gemini", "bedrock", "ollama"]),
    help="Use an LLM to analyze the prompt",
)
@click.option(
    "--ollama-model",
    default="llama2",
    help="Specify the Ollama model to use (default: llama2)",
)
@click.option(
    "--install-dependencies", is_flag=True, help="Install missing dependencies"
)
@click.option("--create-empty-patch", is_flag=True, help="Create an empty patch file")
@click.option(
    "--batch-mode", is_flag=True, help="Run in batch mode for multiple projects"
)
def main(
    project_path: str,
    use_llm: str,
    ollama_model: str,
    install_dependencies: bool,
    create_empty_patch: bool,
    batch_mode: bool,
):
    """Generate a prompt for an LLM to check README and Makefile alignment or create an empty patch file."""
    if install_dependencies:
        install_dependencies()

    project_path = Path(project_path).resolve()  # Resolve to absolute path
    project_name = project_path.name

    if batch_mode:
        click.echo(f"\n{'='*50}\nProcessing project: {project_name}\n{'='*50}")

    if create_empty_patch:
        try:
            patch_file_path = create_empty_patch_file(project_path)
            click.echo(f"Empty patch file created at: {patch_file_path}")
        except Exception as e:
            click.echo(f"Error creating empty patch file: {str(e)}", err=True)
        return

    output_path = project_path.parent / f"{project_name}_review.txt"

    try:
        relevant_files = get_relevant_files(project_path)
        archive_content = generate_archive(project_path, relevant_files)
        prompt = generate_prompt(archive_content)

        with output_path.open("w", encoding="utf-8") as output_file:
            output_file.write(prompt)

        click.echo(f"Prompt generated and saved to {output_path}")

        if use_llm:
            click.echo(f"Sending prompt to {use_llm.capitalize()} for analysis...")
            try:
                if use_llm == "claude":
                    llm_response = send_to_claude(prompt)
                elif use_llm == "openai":
                    llm_response = send_to_openai(prompt)
                elif use_llm == "gemini":
                    llm_response = send_to_gemini(prompt)
                elif use_llm == "bedrock":
                    llm_response = send_to_bedrock(prompt)
                elif use_llm == "ollama":
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

                patch_output_path = (
                    project_path.parent / f"{project_name}_{use_llm}_patch.diff"
                )
                with patch_output_path.open("w", encoding="utf-8") as patch_file:
                    patch_file.write(readme_patch)
                    patch_file.write(makefile_patch)

                click.echo(
                    f"{use_llm.capitalize()}'s analysis saved as a patch to {patch_output_path}"
                )
            except ImportError as e:
                click.echo(f"Error: {str(e)}", err=True)
                click.echo(
                    "Run the script with --install-dependencies to install missing libraries."
                )
            except Exception as e:
                click.echo(
                    f"An error occurred while processing the LLM response: {str(e)}",
                    err=True,
                )
    except Exception as e:
        click.echo(f"An error occurred during project analysis: {str(e)}", err=True)

    if batch_mode:
        click.echo(f"\nCompleted processing for project: {project_name}\n{'='*50}\n")


if __name__ == "__main__":
    main()
