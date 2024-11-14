{ pkgs ? import <nixpkgs> {} }:

let
  # Python packages needed for AI/ML development
  pythonPackages = ps: with ps; [
    # Core ML/AI packages
    anthropic
    boto3
    pydantic
    openai

    # Development tools
    pytest
    black
    flake8
  ];

  # Define Python environment
  python = pkgs.python311.withPackages pythonPackages;

  # Core development tools
  commonTools = with pkgs; [
    # Python environment
    python
    poetry

    # Core shell tools
    bash-completion
    direnv
    fzf
    jq

    # Version control
    git

    # Build tools
    gnumake

    # Editor
    emacs29

    # AWS tools
    awscli2
    localstack

    # Clojure development
    clojure
    leiningen
    clojure-lsp
    babashka
  ];

  # Darwin-specific packages
  darwinPackages = with pkgs.darwin; [
    apple_sdk.frameworks.Security
    apple_sdk.frameworks.CoreServices
    apple_sdk.frameworks.CoreFoundation
    apple_sdk.frameworks.Foundation
  ];

in
pkgs.mkShell {
  buildInputs = commonTools ++ (if pkgs.stdenv.isDarwin then darwinPackages else []);

  shellHook = ''
    # Source bash completion for better CLI experience
    source ${pkgs.bash-completion}/etc/profile.d/bash-completion.sh
    if [ -f ${pkgs.git}/share/git/contrib/completion/git-completion.bash ]; then
      source ${pkgs.git}/share/git/contrib/completion/git-completion.bash
    fi

    # Set up environment paths
    export PATH="$PWD/scripts:$PATH"
    export PYTHONPATH="$PWD/src:$PYTHONPATH"

    # Darwin-specific configurations
    if [ "$(uname)" = "Darwin" ]; then
      export NIX_LDFLAGS="-F${pkgs.darwin.apple_sdk.frameworks.CoreFoundation}/Library/Frameworks -framework CoreFoundation $NIX_LDFLAGS"
    fi

    # Project environment info
    echo "AIF-C01 development environment loaded."
    if command -v python >/dev/null; then
      echo "Python: $(python --version)"
    fi
    if command -v clojure >/dev/null; then
      echo "Clojure: $(clojure --version)"
    fi
    if command -v emacs >/dev/null; then
      echo "Emacs: $(emacs --version | head -n1)"
    fi
  '';
}