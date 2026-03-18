#!/usr/bin/env bash

set -e

REPO="mrsixw/gh-snitch"
BINARY_NAME="gh-snitch"
INSTALL_DIR="${HOME}/.local/bin"
EXECUTABLE_PATH="${INSTALL_DIR}/${BINARY_NAME}"

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

# Check if INSTALL_DIR is in PATH
if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    echo -e "\n${BOLD}${YELLOW}⚠️  Warning: ${INSTALL_DIR} is not in your PATH.${RESET}"
    echo -e "To use ${BINARY_NAME} globally, add this to your ~/.bashrc or ~/.zshrc:"
    echo -e "  ${BOLD}export PATH=\"${INSTALL_DIR}:\$PATH\"${RESET}"
fi

echo -e "\n${BOLD}Begin surveillance:${RESET}"
echo -e "  ${BINARY_NAME} --help"
