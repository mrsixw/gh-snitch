#!/usr/bin/env bats
#
# 🕵️ install.sh — the published `curl | bash` install path.
#
# install.sh ships mode 644 and is documented as `curl ... | bash`, so the tests
# drive it through `bash` exactly as a user would.
#
# HOME is redirected into the test's temporary directory, so every path the
# installer writes to lands there and nothing touches the developer's machine.

setup() {
  load 'helpers/common'
  common_setup

  # curl does two jobs: query the release API, and fetch the assets. The
  # installer resolves the download URL by grepping the API's JSON, so the
  # stub returns realistic JSON rather than a canned URL.
  stub curl <<'STUB'
url=""; out=""; prev=""
for arg in "$@"; do
  [[ "${prev}" == "-o" ]] && out="${arg}"
  [[ "${arg}" == http* ]] && url="${arg}"
  prev="${arg}"
done

case "${url}" in
  *api.github.com*)
    # `curl -s` without -f prints nothing useful on an HTTP error, so an empty
    # body is what a rate-limited or offline run actually sees.
    [[ -n "${API_FAILS:-}" ]] && exit 0
    if [[ -n "${NO_ASSET:-}" ]]; then
      printf '{"tag_name": "v1.2.3", "assets": []}\n'
    else
      printf '{"tag_name": "v1.2.3", "assets": [{"browser_download_url": "https://github.com/mrsixw/gh-snitch/releases/download/v1.2.3/gh-snitch"}]}\n'
    fi
    exit 0 ;;
  *.1.gz)
    [[ -n "${MAN_FAILS:-}" ]] && exit 22
    printf 'man page\n' > "${out}"; exit 0 ;;
  *.bash|*.fish|*/_*)
    [[ -n "${COMPLETIONS_FAIL:-}" ]] && exit 22
    printf 'completion\n' > "${out}"; exit 0 ;;
  *)
    [[ -n "${BINARY_FAILS:-}" ]] && exit 22
    {
      printf '#!/usr/bin/env bash\n'
      printf 'printf "%%s\\n" "$*" >> "%s/binary.log"\n' "${STUB_LOG}"
      printf 'if [[ "$1" == "--version" ]]; then printf "%%s, version 1.2.3\\n" "%s"; fi\n' "${BINARY_NAME}"
      printf 'exit 0\n'
    } > "${out}"
    exit 0 ;;
esac
STUB
}

binary_calls() { cat "${STUB_LOG}/binary.log" 2>/dev/null || true; }

# ---------------------------------------------------------------------------
# 🔎 Resolving the release
# ---------------------------------------------------------------------------

@test "downloads the asset URL it found in the release JSON" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_called curl "https://github.com/mrsixw/gh-snitch/releases/download/v1.2.3/${BINARY_NAME}"
}

@test "derives the man and completion URLs from the asset URL, not a second API call" {
  # One API call, one tag. Asking twice could straddle a release and mix
  # versions.
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_called curl "/releases/download/v1.2.3/${BINARY_NAME}.1.gz"
  [ "$(calls curl | grep -c 'api.github.com')" -eq 1 ]
}

@test "fails when the release carries no matching asset" {
  export NO_ASSET=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "Failed to locate latest release"
  [ ! -e "${FAKE_HOME}/.local/bin/${BINARY_NAME}" ]
}

@test "fails when the release API answers with nothing" {
  # `curl -s` has no -f, so an HTTP error is an empty body rather than a
  # non-zero exit. The grep then finds no URL, which is what stops the install.
  export API_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "Failed to locate latest release"
}

# ---------------------------------------------------------------------------
# 📦 The install itself
# ---------------------------------------------------------------------------

@test "installs the binary, executable, under ~/.local/bin" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  [ -x "${FAKE_HOME}/.local/bin/${BINARY_NAME}" ]
}

@test "reports the deployed version and establishes a config" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "version 1.2.3"
  printf '%s\n' "$(binary_calls)" | grep -qx -- "--init-config"
}

@test "installs the man page and all three completions" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  [ -f "${FAKE_HOME}/.local/share/man/man1/${BINARY_NAME}.1.gz" ]
  [ -f "${FAKE_HOME}/.local/share/bash-completion/completions/${BINARY_NAME}" ]
  [ -f "${FAKE_HOME}/.local/share/zsh/site-functions/_${BINARY_NAME}" ]
  [ -f "${FAKE_HOME}/.config/fish/completions/${BINARY_NAME}.fish" ]
}

@test "a failed binary download is not caught at the download step" {
  # Documents current behaviour rather than endorsing it. `curl -sL` has no -f
  # and no failure check, so a 404 writes the error body to the executable
  # path; the run only fails later, when that file is run. See #155.
  export BINARY_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -ne 0 ]
  refute_output_contains "Operative deployed"
}

@test "treats a missing man page as non-fatal" {
  export MAN_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "Could not install man page"
  [ -x "${FAKE_HOME}/.local/bin/${BINARY_NAME}" ]
}

@test "treats missing completions as non-fatal" {
  export COMPLETIONS_FAIL=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "Could not install bash completion"
  assert_output_contains "Could not install zsh completion"
  assert_output_contains "Could not install fish completion"
}

# ---------------------------------------------------------------------------
# 🐚 Completion instructions
# ---------------------------------------------------------------------------

@test "prints zsh instructions to a zsh user" {
  SHELL=/bin/zsh run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "Add this to your ~/.zshrc"
  assert_output_contains "fpath="
  refute_output_contains "~/.bashrc:"
}

@test "prints bash instructions to a bash user" {
  SHELL=/bin/bash run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "Add this to your ~/.bashrc:"
  refute_output_contains "compinit"
}

@test "tells a fish user there is nothing to do" {
  SHELL=/usr/bin/fish run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "Nothing to do"
}

@test "falls back to all three when the shell is unrecognised" {
  SHELL=/bin/ksh run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "bash — add to"
  assert_output_contains "zsh  — add to"
  assert_output_contains "fish — nothing to do"
}

@test "warns when the install directory is not on PATH" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "is not in your PATH"
}

@test "stays quiet about PATH when the install directory is already on it" {
  PATH="${FAKE_HOME}/.local/bin:${PATH}" run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  refute_output_contains "is not in your PATH"
}
