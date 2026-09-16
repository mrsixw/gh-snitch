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

# How to get Python, worded for the platform actually running this. A macOS
# user told to run apt-get has been pointed somewhere their machine cannot
# follow, which is worse than offering nothing: it reads like the installer
# knows, and it does not. No version is pinned in the suggestion so the floor
# below stays the single place the requirement is written down.
python_install_hint() {
    case "$(uname -s 2>/dev/null)" in
        Darwin)
            printf 'Install it with: brew install python'
            ;;
        Linux)
            if command -v apt-get >/dev/null 2>&1; then
                printf 'Install it with: sudo apt-get install python3'
            elif command -v dnf >/dev/null 2>&1; then
                printf 'Install it with: sudo dnf install python3'
            elif command -v yum >/dev/null 2>&1; then
                printf 'Install it with: sudo yum install python3'
            else
                printf "Install python3 with your distribution's package manager."
            fi
            ;;
        *)
            printf 'Download Python from https://www.python.org/downloads/'
            ;;
    esac
}

# gh-snitch ships as a Python zipapp, so python3 must be on PATH at runtime and
# recent enough to run it. Check before downloading: otherwise the install
# reports success, leaves a binary on PATH, and the first sign of trouble is a
# bare "env: python3: No such file or directory" — or, on an old interpreter, a
# SyntaxError from inside the zipapp. Neither names the real problem.
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${BOLD}\033[31m❌ gh-snitch needs Python 3.11 or newer, but python3 was not found.${RESET}"
    echo -e "   $(python_install_hint)"
    echo -e "   Then re-run this installer."
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    echo -e "${BOLD}\033[31m❌ gh-snitch needs Python 3.11 or newer, but found: $(python3 --version 2>&1).${RESET}"
    echo -e "   $(python_install_hint)"
    echo -e "   Then re-run this installer."
    exit 1
fi

# Find the latest release
echo -e "${YELLOW}Locating latest intelligence package...${RESET}"
# GitHub redirects this path to the newest release's asset, so there is no API
# call and therefore no 60-per-hour unauthenticated rate limit to exhaust. That
# limit is easy to burn through by retrying a failing install, and once spent it
# blocked the install outright — no message could fix that, only not needing the
# call. A missing asset now surfaces as a 404 on the download itself.
RELEASE_BASE_URL="https://github.com/${REPO}/releases/latest/download"
LATEST_RELEASE_URL="${RELEASE_BASE_URL}/${BINARY_NAME}"

echo -e "${GREEN}Package located! Downloading...${RESET}"

# Create install directory if it doesn't exist
mkdir -p "${INSTALL_DIR}"

# Download the binary. -f so a 404 is a failure rather than an error page
# written to disk; the file is removed on failure because curl opens it before
# it knows the request succeeded, and a junk file here shadows any previously
# working copy on PATH.
if ! curl -sfL "${LATEST_RELEASE_URL}" -o "${EXECUTABLE_PATH}"; then
    rm -f "${EXECUTABLE_PATH}"
    echo -e "${BOLD}\033[31m❌ Failed to download binary from ${LATEST_RELEASE_URL}.${RESET}"
    exit 1
fi
chmod +x "${EXECUTABLE_PATH}"

echo -e "${BOLD}${GREEN}✅ Operative deployed to ${EXECUTABLE_PATH}!${RESET}"

# Run version check
echo -ne "${BLUE}Deployed version: ${RESET}"
"${EXECUTABLE_PATH}" --version

# Initialize default config, but never touch one that already exists.
#
# --init-config prompts before overwriting, and this script is documented as
# `curl ... | bash`, where stdin is the pipe rather than a terminal. The prompt
# therefore reads EOF, Click aborts with a non-zero status, and `set -e` kills
# the installer — after the binary is in place but before the man page and
# completions are installed. Every upgrade hit that.
#
# Mirrors get_config_dir() in src/ghsnitch/xdg.py: $XDG_CONFIG_HOME is honoured
# only when absolute, per the XDG spec.
case "${XDG_CONFIG_HOME:-}" in
    /*) CONFIG_PATH="${XDG_CONFIG_HOME}/gh-snitch/config.toml" ;;
    *)  CONFIG_PATH="${HOME}/.config/gh-snitch/config.toml" ;;
esac

echo -e "${YELLOW}Establishing handler config...${RESET}"
if [ -e "${CONFIG_PATH}" ]; then
    echo -e "${GREEN}🗂️  Existing dossier left untouched at ${CONFIG_PATH}.${RESET}"
else
    "${EXECUTABLE_PATH}" --init-config
fi

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

# Resolve a path to its real location, following symlinked directories, so a
# ~/.local/bin that is itself a symlink does not read as a different install.
# Only the directory is resolved: the binary we install may legitimately be a
# symlink, and replacing the link is what an install is supposed to do.
resolve_path() {
    local target="${1}" dir base
    dir="$(dirname "${target}")"
    base="$(basename "${target}")"
    if [ -d "${dir}" ]; then
        dir="$(cd -P "${dir}" 2>/dev/null && pwd)" || dir="$(dirname "${target}")"
    fi
    printf '%s/%s' "${dir}" "${base}"
}

# Having ${INSTALL_DIR} on PATH is not the same as winning on PATH. A stale copy
# earlier in the search order silently takes every invocation, and the installer
# above has just reported complete success — so the user runs an old binary and
# blames the features that appear to be missing: `completions` reports "No such
# command", `update` rewrites a copy they never invoke. Check what the shell
# would actually resolve, not merely where we put the file.
#
# `hash -r` first: this shell ran ${EXECUTABLE_PATH} by absolute path earlier,
# and a cached lookup here would describe bash's memory rather than PATH.
SHADOW_STATUS=0
hash -r 2>/dev/null || true
RESOLVED_PATH="$(command -v "${BINARY_NAME}" 2>/dev/null || true)"
if [ -n "${RESOLVED_PATH}" ] \
    && [ "$(resolve_path "${RESOLVED_PATH}")" != "$(resolve_path "${EXECUTABLE_PATH}")" ]; then
    echo -e "\n${BOLD}\033[31m❌ Another ${BINARY_NAME} shadows this install.${RESET}"
    echo -e "   ${BOLD}Installed:${RESET} ${EXECUTABLE_PATH}"
    echo -e "   ${BOLD}Shadowed by:${RESET} ${RESOLVED_PATH}  ${YELLOW}← this is what runs${RESET}"
    echo -e "\nThe rogue copy wins because it comes first in your PATH. Until it is"
    echo -e "removed or your PATH is reordered, ${BINARY_NAME} will keep running the"
    echo -e "old binary — which is how a missing ${BOLD}completions${RESET} command, or"
    echo -e "an ${BOLD}update${RESET} that never seems to take effect usually shows up."
    echo -e "\nRemove it with:"
    echo -e "  ${BOLD}rm \"${RESOLVED_PATH}\"${RESET}"
    echo -e "then re-run this installer to confirm."
    SHADOW_STATUS=1
fi

# Suppressed when shadowed: pointing the user at `gh-snitch --help` directly
# below a warning that `gh-snitch` runs something else would be telling them to
# invoke the very binary we just said is the wrong one.
if [ "${SHADOW_STATUS}" -eq 0 ]; then
    echo -e "\n${BOLD}Begin surveillance:${RESET}"
    echo -e "  ${BINARY_NAME} --help"
fi

# Non-zero when shadowed: the install did put the binary in place, but the
# command the user is about to type still is not it. Reporting success there is
# the bug this exits for.
exit ${SHADOW_STATUS}
