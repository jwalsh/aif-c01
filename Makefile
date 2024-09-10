.PHONY: help setup poetry-shell deps init switch-profile-lcl switch-profile-dev aws-audit aws-cleanup aws-manage run test lint lint-fix lint-fix-scripts lint-fix-clojure lint-fix-all uberjar localstack-up localstack-down clean clean-temp reset-config set-proxy unset-proxy emacs access-logs all dev

# Default AWS profile
AWS_PROFILE ?= dev

# Default target: show help
.DEFAULT_GOAL := help

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

# Set up the AIF-C01 project
setup:
	@echo "Setting up the AIF-C01 project..."
	@./scripts/setup.sh

# Create and activate Poetry virtual environment
poetry-shell:
	@echo "Creating and activating Poetry virtual environment..."
	@poetry shell

# Install dependencies
deps:
	@echo "Installing dependencies..."
	@poetry install
	@lein deps

# Initialize the project
init: setup deps

# Switch to LocalStack profile
switch-profile-lcl:
	@echo "Switching to LocalStack profile..."
	@source scripts/switch_profile.sh lcl

# Switch to AWS dev profile
switch-profile-dev:
	@echo "Switching to AWS dev profile..."
	@source scripts/switch_profile.sh dev

# Audit AWS resources
aws-audit:
	@echo "Auditing AWS resources..."
	@python scripts/aws_resource_manager.py audit

# Clean up AWS resources
aws-cleanup:
	@echo "Cleaning up AWS resources..."
	@python scripts/aws_resource_manager.py cleanup

# Manage AWS resources
aws-manage:
	@echo "Managing AWS resources..."
	@python scripts/aws_resource_manager.py manage

# Run the project
run:
	@echo "Running the project..."
	@lein run

# Run tests
test:
	@echo "Running tests..."
	@lein test

# Lint the project
lint:
	@echo "Linting the project..."
	@lein lint
	@poetry run flake8

# Fix linting issues
lint-fix:
	@echo "Fixing linting issues..."
	@make lint-fix-scripts
	@make lint-fix-clojure
	@make lint-fix-python

# Fix linting issues in shell scripts
lint-fix-scripts:
	@echo "Fixing linting issues in shell scripts..."
	@shfmt -w scripts/*.sh

# Fix linting issues in Clojure files
lint-fix-clojure:
	@echo "Fixing linting issues in Clojure files..."
	@lein cljfmt fix

# Fix linting issues in Python files
lint-fix-python:
	@echo "Fixing linting issues in Python files..."
	@poetry run black .

# Fix all linting issues
lint-fix-all: lint-fix-scripts lint-fix-clojure lint-fix-python

# Build uberjar
uberjar:
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

# Clean up temporary files
clean-temp:
	@echo "Cleaning up temporary files..."
	@find . -type f -name "*.tmp" -delete
	@find . -type f -name "*.log" -delete

# Clean up build artifacts
clean: clean-temp
	@echo "Cleaning up build artifacts..."
	@lein clean
	@rm -rf target

# Reset configuration
reset-config:
	@echo "Resetting configuration..."
	@git checkout -- .envrc
	@direnv allow

# Set proxy configuration
set-proxy:
	@echo "Setting proxy configuration..."
	@export HTTP_PROXY="http://http.docker.internal:3128"
	@export HTTPS_PROXY="http://http.docker.internal:3128"
	@export NO_PROXY="hubproxy.docker.internal"

# Unset proxy configuration
unset-proxy:
	@echo "Unsetting proxy configuration..."
	@unset HTTP_PROXY
	@unset HTTPS_PROXY
	@unset NO_PROXY

# Start Emacs with the project-specific configuration
emacs:
	@echo "Starting Emacs..."
	@emacs -q -l .emacs.d/init.el

# View Squid access logs
access-logs:
	@tail -f /opt/homebrew/var/logs/access.log

# Start development environment
dev: localstack-up
	@echo "Starting development environment..."
	@lein repl

# All-in-one setup (kept for backwards compatibility)
all: setup

# Helper targets (not directly called by users)
docker-cleanup:
	@echo "Cleaning up Docker resources..."
	@docker system prune -f
	@docker volume prune -f

python-cleanup:
	@echo "Cleaning up Python environment..."
	@poetry env remove --all
