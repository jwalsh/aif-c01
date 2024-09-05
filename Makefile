.PHONY: help setup poetry-shell deps init switch-profile-lcl switch-profile-dev aws-audit aws-cleanup aws-manage run test lint lint-fix lint-fix-scripts lint-fix-clojure lint-fix-all uberjar localstack-up localstack-down clean clean-temp reset-config set-proxy unset-proxy emacs access-logs all

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

# Audit AWS resources
aws-audit:
	@echo "Auditing AWS resources..."
	poetry run python scripts/aws_resource_manager.py

# Audit and clean up AWS resources
aws-cleanup:
	@echo "Auditing and cleaning up AWS resources..."
	poetry run python scripts/aws_resource_manager.py --clean

# Audit and manage AWS resources
aws-manage: aws-audit
	@echo "AWS resources audited. To clean up resources, run 'make aws-cleanup'"

# Start the Clojure REPL with rebel-readline
run: poetry-shell
	@echo "Starting the Clojure REPL with rebel-readline..."
	@lein with-profile +$(AWS_PROFILE) rebel

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

# Lint and fix Python and Shell scripts
lint-fix-scripts:
	@echo "Linting and fixing Python scripts..."
	-poetry run flake8 scripts/ || true
	poetry run black scripts/
	@echo "Linting and fixing Shell scripts..."
	-find scripts/ -name "*.sh" -exec shellcheck {} + || true
	find scripts/ -name "*.sh" -exec shfmt -w {} +

# Lint and fix Clojure code
lint-fix-clojure:
	@echo "Linting and fixing Clojure code..."
	lein lint-fix

# Lint and fix all code
lint-fix-all: lint-fix-scripts lint-fix-clojure
	@echo "All linting and fixing completed."

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
	docker-compose down -v

# Clean up the project
clean: docker-cleanup localstack-down python-cleanup
	@echo "Cleaning up project..."
	rm -rf target
	rm -rf .lein-*
	rm -rf .nrepl-port
	rm -rf .rebel_readline_history
	rm -rf *.log

# Clean up temporary files
clean-temp:
	@echo "Cleaning up temporary files..."
	find . -type f -name "*.tmp" -delete
	find . -type f -name "*.swp" -delete

# Reset configuration
reset-config:
	@echo "Resetting configuration..."
	git checkout -- .envrc
	direnv allow

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

# All-in-one setup (kept for backwards compatibility)
all: setup

# Helper targets (not directly called by users)
docker-cleanup:
	@echo "Cleaning up Docker resources..."
	docker system prune -f
	docker volume prune -f

python-cleanup:
	@echo "Cleaning up Python environment..."
	poetry env remove --all
