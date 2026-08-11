#!/usr/bin/env bash

set -e

REPO="mrsixw/gh-snitch"
BINARY_NAME="gh-snitch"
INSTALL_DIR="${HOME}/.local/bin"
EXECUTABLE_PATH="${INSTALL_DIR}/${BINARY_NAME}"
MAN_DIR="${HOME}/.local/share/man/man1"
BASH_COMPLETION_DIR="${HOME}/.local/share/bash-completion/completions"
ZSH_COMPLETION_DIR="${HOME}/.local/share/zsh/site-functions"
FISH_COMPLETION_DIR="${HOME}/.config/fish/completions"

# Setup colors
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}🕵️ Deploying operative...${RESET}"

# Find the latest release
echo -e "${YELLOW}Locating latest intelligence package...${RESET}"
LATEST_RELEASE_JSON=$(curl -s "https://api.github.com/repos/${REPO}/releases/latest")
LATEST_RELEASE_URL=$(echo "${LATEST_RELEASE_JSON}" | grep -o "https://github.com/${REPO}/releases/download/[^/ ]*/${BINARY_NAME}" | head -n 1)

if [ -z "${LATEST_RELEASE_URL}" ]; then
    echo -e "${BOLD}\033[31m❌ Failed to locate latest release for ${REPO}.${RESET}"
    exit 1
fi

echo -e "${GREEN}Package located! Downloading...${RESET}"

# The man page and completion scripts sit beside the binary in the same release,
# so derive their base URL from the asset URL already resolved above rather than
# making a second API call.
RELEASE_BASE_URL="${LATEST_RELEASE_URL%/*}"

# Create install directory if it doesn't exist
mkdir -p "${INSTALL_DIR}"

# Download the binary
curl -sL "${LATEST_RELEASE_URL}" -o "${EXECUTABLE_PATH}"
chmod +x "${EXECUTABLE_PATH}"

echo -e "${BOLD}${GREEN}✅ Operative deployed to ${EXECUTABLE_PATH}!${RESET}"

# Run version check
echo -ne "${BLUE}Deployed version: ${RESET}"
"${EXECUTABLE_PATH}" --version

# Initialize default config
echo -e "${YELLOW}Establishing handler config...${RESET}"
"${EXECUTABLE_PATH}" --init-config

# Man page and completions are best-effort: a release predating them, or a
# partial mirror, should not fail an otherwise working install.
echo -e "${YELLOW}Filing the field manual...${RESET}"
mkdir -p "${MAN_DIR}"
if curl -sfL "${RELEASE_BASE_URL}/${BINARY_NAME}.1.gz" -o "${MAN_DIR}/${BINARY_NAME}.1.gz"; then
    echo -e "${GREEN}📖 Man page installed. Run: ${BOLD}man ${BINARY_NAME}${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not install man page (non-fatal).${RESET}"
fi

echo -e "${YELLOW}Installing shell completions...${RESET}"
mkdir -p "${BASH_COMPLETION_DIR}"
if curl -sfL "${RELEASE_BASE_URL}/${BINARY_NAME}.bash" -o "${BASH_COMPLETION_DIR}/${BINARY_NAME}"; then
    echo -e "${GREEN}✅ Bash completion installed.${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not install bash completion (non-fatal).${RESET}"
fi

mkdir -p "${ZSH_COMPLETION_DIR}"
if curl -sfL "${RELEASE_BASE_URL}/_${BINARY_NAME}" -o "${ZSH_COMPLETION_DIR}/_${BINARY_NAME}"; then
    echo -e "${GREEN}✅ Zsh completion installed.${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not install zsh completion (non-fatal).${RESET}"
fi

mkdir -p "${FISH_COMPLETION_DIR}"
if curl -sfL "${RELEASE_BASE_URL}/${BINARY_NAME}.fish" -o "${FISH_COMPLETION_DIR}/${BINARY_NAME}.fish"; then
    echo -e "${GREEN}✅ Fish completion installed.${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not install fish completion (non-fatal).${RESET}"
fi

# Dropping the completion files into place is only half the job — bash and zsh
# both need a line in the user's rc file before they will load them. Print the
# snippet for the shell they are actually using rather than all three.
# Print only: this script is normally run piped through curl, where prompting is
# unreliable, so it never edits rc files on the user's behalf.
echo -e "\n${BOLD}To finish enabling completions:${RESET}"
case "${SHELL##*/}" in
    *bash*)
        echo -e "Add this to your ${BOLD}~/.bashrc${RESET}:"
        echo -e "  ${BOLD}source \"${BASH_COMPLETION_DIR}/${BINARY_NAME}\"${RESET}"
        echo -e "(If you already have the ${BOLD}bash-completion${RESET} package installed, it will be picked up automatically and you can skip this.)"
        echo -e "Then restart your shell."
        ;;
    *zsh*)
        echo -e "Add this to your ${BOLD}~/.zshrc${RESET}, above any existing ${BOLD}compinit${RESET} call:"
        echo -e "  ${BOLD}fpath=(\"${ZSH_COMPLETION_DIR}\" \$fpath)${RESET}"
        echo -e "If you don't already initialise completions (Oh My Zsh and friends do), add this too:"
        echo -e "  ${BOLD}autoload -Uz compinit && compinit${RESET}"
        echo -e "Then restart your shell."
        ;;
    *fish*)
        echo -e "${GREEN}Nothing to do — fish loads completions from ${FISH_COMPLETION_DIR} automatically.${RESET}"
        echo -e "New shells will pick them up."
        ;;
    *)
        echo -e "bash — add to ${BOLD}~/.bashrc${RESET}:"
        echo -e "  ${BOLD}source \"${BASH_COMPLETION_DIR}/${BINARY_NAME}\"${RESET}"
        echo -e "zsh  — add to ${BOLD}~/.zshrc${RESET}, above any existing ${BOLD}compinit${RESET} call:"
        echo -e "  ${BOLD}fpath=(\"${ZSH_COMPLETION_DIR}\" \$fpath)${RESET}"
        echo -e "  ${BOLD}autoload -Uz compinit && compinit${RESET}  ${RESET}# only if you don't already initialise completions"
        echo -e "fish — nothing to do, they load automatically."
        echo -e "Then restart your shell."
        ;;
esac
echo -e "You can also load them ad hoc with ${BOLD}eval \"\$(${BINARY_NAME} completions <shell>)\"${RESET}."

# Check if INSTALL_DIR is in PATH
if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    echo -e "\n${BOLD}${YELLOW}⚠️  Warning: ${INSTALL_DIR} is not in your PATH.${RESET}"
    echo -e "To use ${BINARY_NAME} globally, add this to your ~/.bashrc or ~/.zshrc:"
    echo -e "  ${BOLD}export PATH=\"${INSTALL_DIR}:\$PATH\"${RESET}"
fi

echo -e "\n${BOLD}Begin surveillance:${RESET}"
echo -e "  ${BINARY_NAME} --help"
