# Makefile for AIF-C01 course (Student-focused with advanced features)

# Variables
ORG_FILES := $(wildcard doc/README/includes/*.org)
MERMAID_ORG_FILES := $(wildcard doc/README/includes/*.org)
EXPORT_DIR := doc/export

# Default target
.DEFAULT_GOAL := help

# Phony targets
.PHONY: all help setup run test aws-practice localstack-up localstack-down \
        switch-profile-lcl switch-profile-dev study-resources clean lint \
        tangle generate-diagrams export-org install-emacs-packages deps \
        aws-audit aws-cleanup

# Auto-generated help target
help:
	@echo "Available commands for AIF-C01 course:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

all: setup study-resources ## Set up the environment and generate study resources

setup: ## Set up the project environment
	@echo "Setting up the project environment..."
	@lein deps
	@poetry install
	@make install-emacs-packages
	@echo "Environment setup complete. You're ready to start learning!"

run: ## Run the main application
	@echo "Running the main application..."
	@lein run

test: ## Run test suite
	@echo "Running tests..."
	@lein test

lint: ## Run linters
	@echo "Running linters..."
	@lein eastwood
	@lein cljfmt check
	@flake8 scripts
	@black --check scripts

lint-fix: ## Fix linting issues
	@echo "Fixing linting issues..."
	@lein cljfmt fix
	@black scripts

aws-practice: ## Practice with AWS resources (audit and optionally clean up)
	@echo "Starting AWS resource practice session..."
	@echo "This will list your AWS resources related to the course."
	@echo "To clean up resources, run 'make aws-practice-cleanup' instead."
	@python scripts/aws_resource_manager.py

aws-practice-cleanup: ## Clean up AWS resources used in practice
	@echo "Cleaning up AWS resources..."
	@echo "This will attempt to remove resources created during practice."
	@echo "S3 buckets will not be deleted for safety reasons."
	@python scripts/aws_resource_manager.py --clean

localstack-up: ## Start LocalStack for local AWS development
	@echo "Starting LocalStack..."
	@docker-compose up -d localstack

localstack-down: ## Stop LocalStack
	@echo "Stopping LocalStack..."
	@docker-compose down

switch-profile-lcl: ## Switch to LocalStack profile
	@echo "Switching to LocalStack profile..."
	@source scripts/switch_profile.sh lcl

switch-profile-dev: ## Switch to AWS dev profile
	@echo "Switching to AWS dev profile..."
	@source scripts/switch_profile.sh dev

study-resources: ## Generate study resources
	@echo "Generating study resources..."
	@emacs --batch --eval "(progn \
		(require 'org) \
		(find-file \"doc/README/index.org\") \
		(org-babel-execute-buffer) \
		(org-odt-export-to-odt))"
	@echo "Study resources generated. Check doc/README/index.odt"

tangle: ## Tangle code blocks from org files
	@echo "Tangling code blocks..."
	@for file in $(ORG_FILES); do \
		emacs --batch --eval "(progn \
			(require 'org) \
			(org-babel-tangle-file \"$$file\"))"; \
	done
	@echo "Tangling complete."

generate-diagrams: ## Generate diagrams from org files
	@echo "Generating diagrams..."
	@for file in $(MERMAID_ORG_FILES); do \
		emacs --batch --eval "(progn \
			(require 'org) \
			(find-file \"$$file\") \
			(org-babel-execute-buffer) \
			(save-buffer) \
			(kill-buffer))"; \
	done
	@echo "Diagram generation complete."

export-org: $(EXPORT_DIR) ## Export org files to HTML
	@echo "Exporting org files to HTML..."
	@for file in $(ORG_FILES); do \
		basename=$$(basename $$file .org); \
		emacs --batch --eval "(progn \
			(require 'ox-html) \
			(find-file \"$$file\") \
			(org-html-export-to-html nil nil nil t) \
			(rename-file \"$$basename.html\" \"$(EXPORT_DIR)/$$basename.html\" t))"; \
	done
	@echo "Org export complete. HTML files are in $(EXPORT_DIR) directory."

$(EXPORT_DIR):
	mkdir -p $(EXPORT_DIR)

clean: ## Clean up generated files
	@echo "Cleaning up generated files..."
	@rm -f doc/README/index.odt
	@rm -f *.png
	@rm -f $(EXPORT_DIR)/*.html
	@echo "Cleanup complete."

install-emacs-packages: ## Install required Emacs packages
	@echo "Installing Emacs packages..."
	@emacs --batch --eval "(progn \
		(require 'package) \
		(add-to-list 'package-archives '(\"melpa\" . \"https://melpa.org/packages/\") t) \
		(package-initialize) \
		(package-refresh-contents) \
		(package-install 'org) \
		(package-install 'htmlize))"

deps: ## Update project dependencies
	@echo "Updating project dependencies..."
	@lein deps
	@poetry update

aws-audit: ## Audit AWS resources (for advanced users)
	@echo "Auditing AWS resources..."
	@python scripts/aws_resource_manager.py audit

aws-cleanup: ## Clean up AWS resources (for advanced users)
	@echo "Cleaning up AWS resources..."
	@python scripts/aws_resource_manager.py cleanup

aws-rekognition: ## Count people 
	cat resources/rekognition-example.json | jq '.Labels[] | select(.Name == "Person") | .Instances | length'

aws-polly: ## Create a story from 
	python scripts/aws_polly_transcribe.py

