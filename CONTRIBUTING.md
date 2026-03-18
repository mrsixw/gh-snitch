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
make lint      # ruff check + black --check
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

## Testing

Tests live in `tests/`. Use `pytest` with `monkeypatch` and `click.testing.CliRunner`.

```bash
make test
```

## Pull Requests

- Keep PRs focused on a single concern.
- All CI checks must pass before merging.

## Releases

Releases are automated via CI on push to `main`. The CI pipeline:
1. Runs tests and lint
2. Builds the shiv binary
3. Bumps the version if the current tag already exists
4. Creates a GitHub release with the binary attached
