#!/usr/bin/env bats
#
# 🔭 utils/report_next_version.sh — says, before a merge, what version the
#    next release would carry.
#
# In the sibling breakfast repo a commit marked itself breaking with a bang
# after its conventional type, which is correct Conventional Commits and also
# an instruction to git-mkver to bump the major version. 0.107.1 shipped as
# 1.0.0, and nobody saw it until the release had gone out. This script exists
# so that consequence is visible on the pull request, so the tests care most
# about whether a major jump is called out loudly enough to notice.

setup() {
  load 'helpers/common'
  common_setup

  # Two collaborators, both stubbed. `python utils/read_version.py` reports the
  # current version out of pyproject.toml; `git mkver next` computes the one a
  # release would carry. The real mkver is a Linux/i386-only download, so it
  # never runs in these tests.
  stub python <<'STUB'
# Default only when unset: a test that exports an empty version wants the
# stub to print nothing, which ":-" would quietly replace with the default.
printf '%s\n' "${CURRENT_VERSION-0.38.8}"
STUB

  stub git <<'STUB'
if [[ "$1" == "mkver" ]]; then
  [[ -n "${MKVER_FAILS:-}" ]] && { printf 'mkver: bad config\n' >&2; exit 1; }
  printf '%s\n' "${MKVER_NEXT:-0.38.9}"
  exit 0
fi
exit 0
STUB
}

@test "reports the current version and the one the next release would carry" {
  export CURRENT_VERSION=0.38.8
  export MKVER_NEXT=0.39.0

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "0.38.8"
  assert_output_contains "0.39.0"
}

@test "a major jump is called out, not just printed" {
  export MKVER_NEXT=1.0.0

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "MAJOR"
}

@test "the major warning names what causes it, so the fix is obvious" {
  export MKVER_NEXT=1.0.0

  run "${REPO_ROOT}/utils/report_next_version.sh"

  assert_output_contains "BREAKING CHANGE"
  assert_output_contains "!"
}

@test "a minor bump is not announced as a major one" {
  export MKVER_NEXT=0.39.0

  run "${REPO_ROOT}/utils/report_next_version.sh"

  refute_output_contains "MAJOR"
}

@test "a patch bump is not announced as a major one" {
  export MKVER_NEXT=0.38.9

  run "${REPO_ROOT}/utils/report_next_version.sh"

  refute_output_contains "MAJOR"
}

@test "build metadata on mkver's answer is not mistaken for a version" {
  # Off a release branch, includeBuildMetaData is on and mkver appends
  # +branch.hash. The reported version must be the core, not the whole string.
  export MKVER_NEXT=1.0.0+HEAD.abc1234

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "1.0.0"
  refute_output_contains "abc1234"
  assert_output_contains "MAJOR"
}

@test "a pre-release suffix is handled too" {
  export MKVER_NEXT=1.0.0-RC1

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -eq 0 ]
  assert_output_contains "MAJOR"
}

@test "it fails loudly when mkver cannot answer" {
  # An unparsable mkver.conf must redden the pull request, which is the whole
  # point of running this before the release job ever sees it.
  export MKVER_FAILS=1

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -ne 0 ]
  assert_output_contains "could not"
}

@test "it fails when the current version cannot be read rather than inventing one" {
  stub python <<'STUB'
printf 'no version here\n' >&2
exit 1
STUB

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -ne 0 ]
}

@test "an empty version is a failure, not an empty report" {
  export CURRENT_VERSION=""

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -ne 0 ]
}

@test "it writes the report to the step summary when Actions provides one" {
  export MKVER_NEXT=1.0.0
  summary="${BATS_TEST_TMPDIR}/summary.md"
  export GITHUB_STEP_SUMMARY="${summary}"

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -eq 0 ]
  [ -f "${summary}" ]
  grep -q "1.0.0" "${summary}"
  grep -q "MAJOR" "${summary}"
}

@test "it does not need a step summary to work" {
  export MKVER_NEXT=0.39.0
  unset GITHUB_STEP_SUMMARY

  run "${REPO_ROOT}/utils/report_next_version.sh"

  [ "$status" -eq 0 ]
}
