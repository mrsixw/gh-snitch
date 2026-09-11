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

  # curl has one job now: fetch the assets from the API-free
  # /releases/latest/download/ path. A missing asset is a 404 on the download
  # itself, which is what BINARY_FAILS simulates.
  stub curl <<'STUB'
url=""; out=""; prev=""
for arg in "$@"; do
  [[ "${prev}" == "-o" ]] && out="${arg}"
  [[ "${arg}" == http* ]] && url="${arg}"
  prev="${arg}"
done

case "${url}" in
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
# 🐍 Interpreter preflight
# ---------------------------------------------------------------------------

@test "refuses to install when python3 is absent" {
  # PATH holds only the stubs, so `command -v python3` finds nothing. The
  # preflight runs before mkdir or curl, so nothing else is needed for the
  # script to get that far.
  PATH="${STUB_BIN}" run /bin/bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "python3 was not found"
  assert_output_contains "3.11"
}

@test "refuses to install when python3 is too old" {
  stub python3 <<'STUB'
[[ "$1" == "--version" ]] && { printf 'Python 3.9.18\n'; exit 0; }
exit 1
STUB

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "3.11 or newer"
  assert_output_contains "Python 3.9.18"
}

@test "downloads nothing when the interpreter check fails" {
  # The point of checking first: no half-finished install, and no binary left
  # shadowing a working one on PATH.
  PATH="${STUB_BIN}" run /bin/bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  [ ! -e "${FAKE_HOME}/.local/bin/${BINARY_NAME}" ]
  [ "$(calls curl | wc -l | tr -d ' ')" -eq 0 ]
}

@test "the required version matches the one pyproject declares" {
  # The floor is written into install.sh by hand; pyproject is what actually
  # decides it. Drift between them would mislead every user who hits the check.
  declared="$(sed -n 's/^requires-python *= *">=\([0-9.]*\)"/\1/p' "${REPO_ROOT}/pyproject.toml")"
  [ -n "${declared}" ]
  grep -q "${declared} or newer" "${REPO_ROOT}/install.sh"
  grep -q "sys.version_info >= (${declared%%.*}, ${declared##*.})" "${REPO_ROOT}/install.sh"
}

# ---------------------------------------------------------------------------
# 🔎 Resolving the release
# ---------------------------------------------------------------------------

@test "downloads the binary from the API-free latest-release path" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_called curl "https://github.com/mrsixw/gh-snitch/releases/latest/download/${BINARY_NAME}"
}

@test "never calls the GitHub API" {
  # The whole point: the unauthenticated API allows 60 requests per hour per IP,
  # and a user who spent them could not install at all.
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  [ "$(calls curl | grep -c 'api.github.com')" -eq 0 ]
}

@test "fetches the man page and completions from the same latest-release path" {
  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 0 ]
  assert_called curl "/releases/latest/download/${BINARY_NAME}.1.gz"
}

@test "fails when the release carries no matching asset" {
  # No API lookup to fail early any more: a release without the asset is a 404
  # on the download, which the download guard turns into a clear failure.
  export BINARY_FAILS=1

  run bash "${REPO_ROOT}/install.sh"

  [ "$status" -eq 1 ]
  assert_output_contains "Failed to download binary"
  [ ! -e "${FAKE_HOME}/.local/bin/${BINARY_NAME}" ]
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
