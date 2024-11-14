#!/usr/bin/env bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}INFO:${NC} $1"; }
log_success() { echo -e "${GREEN}SUCCESS:${NC} $1"; }
log_error() { echo -e "${RED}ERROR:${NC} $1"; }

PROJECT_ROOT="${1:-$(pwd)}"
cd "$PROJECT_ROOT"

setup_git_config() {
    local config_file=".gitconfig.local"
    
    if [[ ! -f "$config_file" ]]; then
        log_info "Setting up Git configuration..."
        cat > "$config_file" << 'EOF'
[alias]
    # Basic shortcuts
    st = status -sb
    ci = commit
    co = checkout
    br = branch
    cp = cherry-pick
    
    # Logging
    lg = log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
    ll = log --pretty=format:"%C(yellow)%h%Cred%d\\ %Creset%s%Cblue\\ [%cn]" --decorate --numstat
    hist = log --pretty=format:"%h %ad | %s%d [%an]" --graph --date=short
    
    # Branch management
    bd = branch -d
    bD = branch -D
    
    # Commits
    amend = commit --amend
    unstage = reset HEAD --
    undo = reset --soft HEAD^
    
    # Stashing
    sl = stash list
    sa = stash apply
    ss = stash save
    sp = stash pop
    
    # Working with remotes
    f = fetch --all --prune
    p = push
    pl = pull
    
    # Show changes
    df = diff
    dc = diff --cached
    
    # List aliases
    aliases = config --get-regexp alias
    
    # Show current branch
    cb = rev-parse --abbrev-ref HEAD
    
    # Sync with remote, rebase local changes
    sync = !git pull --rebase && git push
    
    # Clean up local branches
    cleanup = "!git branch --merged | grep -v '\\*' | xargs -n 1 git branch -d"
    
    # Show recent branches
    recent = "!git branch --sort=committerdate | tail -10"
EOF
        git config --local include.path ../.gitconfig.local
        log_success "Created $config_file"
    fi
}

setup_direnv() {
    local config_file=".envrc"
    
    if [[ ! -f "$config_file" ]]; then
        log_info "Setting up direnv configuration..."
        cat > "$config_file" << 'EOF'
# Allow loading of environment
use nix

# Load .env file if it exists
if [ -f .env ]; then
  source_env .env
fi

# Python virtual environment
layout python3

# Project-specific environment variables
export PYTHONPATH=$PWD/src:$PYTHONPATH
export PATH=$PWD/scripts:$PATH

# AWS LocalStack configuration
export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"

# Poetry configuration
export POETRY_VIRTUALENVS_IN_PROJECT=true
EOF
        direnv allow .
        log_success "Created $config_file"
    fi
}

setup_directories() {
    local dirs=("src" "scripts" ".nix-shell/cache" ".nix-shell/tmp")
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_info "Creating directory: $dir"
            mkdir -p "$dir"
            log_success "Created $dir"
        fi
    done
}

main() {
    log_info "Setting up development environment..."
    
    setup_directories
    setup_git_config
    setup_direnv
    
    log_success "Development environment setup complete!"
}

main
