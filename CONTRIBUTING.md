# Contributing to gh-snitch

## Development Setup

```bash
git clone https://github.com/mrsixw/gh-snitch.git
cd gh-snitch
uv sync --extra dev
```

## Common Commands

```bash
make test      # run pytest
make bats      # run the shell script tests
make lint      # ruff check + black --check + shellcheck + typos
make shellcheck# static analysis for every shell source
make spell     # spell check, the same one CI runs
make format    # auto-fix lint and formatting
make build     # build shiv binary to dist/gh-snitch
make smoketest # run built binary with --version
```

## Code Quality

- Use `ruff` (lint + import sorting) and `black` (formatting).
- Never use bare `except Exception`. Catch specific exceptions.
- Run `make test` and `make lint` before pushing.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: ...` — new feature
- `fix: ...` — bug fix
- `chore: ...` — maintenance
- `docs: ...` — documentation only
- `refactor: ...` — code restructuring
- `test: ...` — test changes
- `ci: ...` — CI changes

### Breaking changes bump the major version

Two things, and only these two, cause a **major** release:

- a `!` after the type — `feat!: drop the old flag`
- `BREAKING CHANGE` anywhere in the commit body

`git mkver` reads them straight out of the commit messages since the last tag,
so the release that follows your merge is decided by how you word the commit.
This is how the sibling breakfast repo went from 0.107.1 to 1.0.0: a commit
removing a deprecated flag was marked breaking, which was accurate and also a
major-version instruction.

Neither marker is a way to say "this change matters". Use one when you intend to
change the first number, and call it out in the pull request when you do.

The `version` CI job prints the version your merge would release on every pull
request. Check it before merging.

**Careful writing about these markers.** mkver looks for them as a substring on
any line of any commit message since the last tag, so a commit body that
explains "this was committed as `feat!:`" is indistinguishable, to mkver, from
one declaring a breaking change — and releases a major version. Break the string
when you need to refer to it: `feat!` without the trailing colon, or the footer
written with a hyphen.

## Testing

Tests live in `tests/`. Use `pytest` with `monkeypatch` and `click.testing.CliRunner`.

```bash
make test
```

### The shell scripts

`install.sh` is the published `curl | bash` install path, and `utils/` holds the
scripts that cut releases. They are covered by a
[bats](https://github.com/bats-core/bats-core) suite in `tests/bats/`:

```bash
make bats
```

Each test runs the **real script as a subprocess** with its collaborators —
`gh`, `git`, `curl`, `tar`, `install` — replaced by stubs on `PATH`, and with
`HOME` redirected into the test's temporary directory. Nothing reaches the
network, and an installer test cannot scribble on the machine running it. The
stubs record their arguments, so a test can assert *what the script asked for*
rather than only what it printed.

`shellcheck` and `typos` are fetched on demand with `uvx`, pinned in the
`Makefile` so the same versions run locally and in CI.

`bats` is the exception: it has no PyPI build, so install it once with
`brew install bats-core` (macOS) or `apt-get install bats` (Debian/Ubuntu).
`make bats` says so if it is missing.

## Pull Requests

- Keep PRs focused on a single concern.
- All CI checks must pass before merging.

## Releases

Releases are automated via CI on push to `main`. The CI pipeline:
1. Runs tests and lint
2. Builds the shiv binary
3. Bumps the version if the current tag already exists
4. Creates a GitHub release with the binary attached

### Which version will it release?

- **`git mkver patch` does not mean "bump the patch number".** It applies the
  file patches named in `mkver.conf` (here, rewriting `version` in
  `pyproject.toml`), and what it writes is the version mkver computed from the
  commit messages — which may be a major, minor or patch increase. The release
  job calls it through `utils/bump_version_if_tag_exists.sh` when the tag for
  the current version already exists.
- `utils/report_next_version.sh` prints the current version alongside the one
  the next release would carry, and says so loudly if the major component
  changes. The `version` CI job runs it on every pull request, so a malformed
  `mkver.conf` fails there rather than on `main`.
- Do **not** run `git mkver patch` on a feature branch — it rewrites the version
  in `pyproject.toml`.
