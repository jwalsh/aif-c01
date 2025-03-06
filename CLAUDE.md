# CLAUDE.md - AIF-C01 Repository Guide

## Build Commands
- Setup: `make setup` - Install dependencies and set up environment
- Run application: `lein run` or `make run`
- Test: `lein test` or `make test`
- Single test: `lein test aif-c01.core-test` (namespace) or `lein test :only aif-c01.core-test/test-name`
- Lint: `make lint` (runs Clojure and Python linters)
- Format all code: `make format` (runs all formatters)

## Code Style
Use formatters instead of manual styling - config files provided:

### Clojure
- Format: `make format-clojure` (uses cljfmt with .cljfmt.edn)
- Static analysis: `lein eastwood` and `lein kibit`
- Naming: kebab-case for everything (namespaces, functions, variables)

### Python
- Format: `make format-python` (uses Black with pyproject.toml config)
- Lint: Flake8 (config in pyproject.toml)
- Type annotations required on public functions

### Shell Scripts
- Lint: `make format-shell` (uses shellcheck with .shellcheckrc)
- Use `#!/bin/bash` shebang and `set -e` for error handling
- Quote all variables and use `"${array[@]}"` for arrays

## Git Workflow
- Commit style: `type(scope): description` (Conventional Commits)
  - Examples: `feat(rag):`, `fix(aws):`, `chore:`, `refactor:`
- ALWAYS use `git commit --no-gpg-sign` (GPG signing breaks tooling)
- Keep commits focused on single logical changes

## Development Workflow
- Use `make help` to see all available commands
- LocalStack: `make localstack-up/down` for local AWS testing
- AWS profiles: `make switch-profile-lcl/dev` to switch contexts