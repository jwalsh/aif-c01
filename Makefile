.PHONY: all setup run clean deps test lint lint-fix uberjar help localstack-up localstack-down switch-profile-lcl switch-profile-dev poetry-shell emacs

# Default AWS profile
AWS_PROFILE ?= dev

all: setup

# Set up the AIF-C01 project
setup:
	@echo "Setting up the AIF-C01 project..."
	@./scripts/setup.sh

# Create and activate Poetry virtual environment
poetry-shell:
	@echo "Creating and activating Poetry virtual environment..."
	@poetry shell

# Install project dependencies
deps: poetry-shell
	@echo "Installing project dependencies..."
	@poetry install
	@poetry run pip install awscli
	@lein deps

# Initialize the project environment
init: deps
	@echo "Initializing project environment..."
	@lein run -m user

# Switch to LocalStack profile
switch-profile-lcl:
	@echo "Switching to LocalStack profile..."
	@. ./scripts/switch_profile.sh lcl

# Switch to AWS dev profile
switch-profile-dev:
	@echo "Switching to AWS dev profile..."
	@. ./scripts/switch_profile.sh dev

# Start the Clojure REPL with rebel-readline
run: poetry-shell
	@echo "Starting the Clojure REPL with rebel-readline..."
	@lein with-profile +$(AWS_PROFILE) rebel

# Clean up the project
clean:
	@echo "Cleaning up the project..."
	@lein clean
	@rm -rf target
	@poetry env remove --all

# Run tests
test: poetry-shell
	@echo "Running tests..."
	@lein test

# Run linter
lint: poetry-shell
	@echo "Running linter..."
	@lein lint

# Fix linting issues
lint-fix: poetry-shell
	@echo "Fixing linting issues..."
	@lein lint-fix

# Build uberjar
uberjar: poetry-shell
	@echo "Building uberjar..."
	@lein uberjar

# Start LocalStack
localstack-up:
	@echo "Starting LocalStack..."
	@docker-compose up -d localstack

# Stop LocalStack
localstack-down:
	@echo "Stopping LocalStack..."
	@docker-compose down

# Start Emacs with the project-specific configuration
emacs:
	@echo "Starting Emacs..."
	@emacs -q -l .emacs.d/init.el

# Show help
help:
	@echo "Available commands:"
	@awk '/^[a-zA-Z0-9_-]+:/ { \
		helpMessage = match(lastLine, /^# (.*)/); \
		if (helpMessage) { \
			helpCommand = substr($$1, 0, index($$1, ":")-1); \
			helpMessage = substr(lastLine, RSTART + 2, RLENGTH); \
			printf "  %-20s %s\n", helpCommand, helpMessage; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)