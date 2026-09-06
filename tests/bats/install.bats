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
    # With -f, an HTTP error is a non-zero exit rather than a body to parse.
    [[ -n "${API_FAILS:-}" ]] && exit 22
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
    if [[ -n "${BINARY_FAILS:-}" ]]; then
      # curl opens (and truncates) the -o file before it knows the request
      # failed, so a failed download leaves a file behind unless the caller
      # removes it. The stub has to behave the same way or the test that
      # checks for leftovers proves nothing.
      printf '<html>404 Not Found</html>\n' > "${out}"
      exit 22
    fi
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

@test "fails when the release API is unreachable" {
  # Distinct from "the release has no matching asset": a rate-limited or
  # offline run is a different problem and deserves a different message.
  export API_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "Failed to fetch release info"
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

@test "fails when the binary download fails" {
  export BINARY_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "Failed to download binary"
  refute_output_contains "Operative deployed"
}

@test "leaves no file behind when the binary download fails" {
  # `curl -o` creates the file before it knows whether the request succeeded,
  # so an unguarded failure leaves junk at the install path — shadowing any
  # previously working copy on PATH.
  export BINARY_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ ! -e "${FAKE_HOME}/.local/bin/${BINARY_NAME}" ]
}

@test "does not run a binary it failed to download" {
  export BINARY_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  refute_output_contains "Deployed version"
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
