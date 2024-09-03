#!/bin/bash

# Exit on error
set -e

echo "Setting up AIF-C01 project environment for macOS..."

# Check if Homebrew is installed, install if it's not
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Update Homebrew and upgrade any already-installed formulae
brew update && brew upgrade

# Install essential tools
echo "Installing essential tools..."
brew install \
    leiningen \
    clojure \
    openjdk \
    python \
    poetry \
    fzf \
    ripgrep \
    jq \
    zsh \
    zsh-completions \
    zsh-syntax-highlighting \
    zsh-autosuggestions

# Install oh-my-zsh if not already installed
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "Installing oh-my-zsh..."
    sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# Install Clojure LSP
echo "Installing Clojure LSP..."
brew install clojure-lsp/brew/clojure-lsp-native

# Install Clojure tools
echo "Installing Clojure tools..."
brew install borkdude/brew/babashka
brew install borkdude/brew/clj-kondo

# Set up fzf
echo "Setting up fzf..."
$(brew --prefix)/opt/fzf/install --all

# Add useful Zsh plugins
echo "Adding useful Zsh plugins..."
sed -i '' 's/plugins=(git)/plugins=(git fzf ripgrep zsh-autosuggestions zsh-syntax-highlighting)/' ~/.zshrc

# Set up key bindings for fuzzy search
echo "Setting up key bindings for fuzzy search..."
echo '# fzf key bindings' >> ~/.zshrc
echo '[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh' >> ~/.zshrc

echo "Setup complete! Please restart your terminal or run 'source ~/.zshrc' to apply changes."
