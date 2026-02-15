#!/usr/bin/env bash

# install mise if not already installed to local path
if ! command -v ~/.local/bin/mise &>/dev/null; then
    echo "mise is not installed. Would you like to install it now? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        curl https://mise.run | sh
        echo ""
        echo "Load mise into your path (add to your ~/.zshrc profile to always be available): "
        echo '   echo 'eval "$(~/.local/bin/mise activate zsh)"' >> ~/.zshrc'
        # Load mise into the current script shell instead of zsh
        eval "$(~/.local/bin/mise activate bash)"
    else
        echo "Skipping mise installation."
        exit 1
    fi
else
    eval "$(~/.local/bin/mise activate bash)"
fi
mise trust
mise install -y
