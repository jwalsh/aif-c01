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
docker-cleanup:
	@echo "Cleaning up Docker resources..."
	docker system prune -f
	docker volume prune -f

localstack-down:
	@echo "Stopping LocalStack..."
	docker-compose down -v

python-cleanup:
	@echo "Cleaning up Python environment..."
	poetry env remove --all

clean: docker-cleanup localstack-down python-cleanup
	@echo "Cleaning up project..."
	rm -rf target
	rm -rf .lein-*
	rm -rf .nrepl-port
	rm -rf .rebel_readline_history
	rm -rf *.log

clean-temp:
	@echo "Cleaning up temporary files..."
	find . -type f -name "*.tmp" -delete
	find . -type f -name "*.swp" -delete

reset-config:
	@echo "Resetting configuration..."
	git checkout -- .envrc
	direnv allow

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

set-proxy:
	@echo "Setting proxy configuration..."
	@export HTTP_PROXY="http://http.docker.internal:3128"
	@export HTTPS_PROXY="http://http.docker.internal:3128"
	@export NO_PROXY="hubproxy.docker.internal"

unset-proxy:
	@echo "Unsetting proxy configuration..."
	@unset HTTP_PROXY
	@unset HTTPS_PROXY
	@unset NO_PROXY

# Start LocalStack
localstack-up:
	@echo "Starting LocalStack..."
	@docker-compose up -d localstack

# Start Emacs with the project-specific configuration
emacs:
	@echo "Starting Emacs..."
	@emacs -q -l .emacs.d/init.el

# Squid access logs
access-logs:
	@tail -f /opt/homebrew/var/logs/access.log

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
