# Claude Instructions

## Project Overview
- **gh-snitch** is a spy-themed CLI tool that surveys GitHub contribution counts for configured operatives (users) and renders a ranked, colour-graded table in the terminal.
- Built with Python and Click. Uses the GitHub GraphQL API.
- Package structure: code in `src/ghsnitch/`, tests in `tests/`.
- The name is spy-themed: gh-snitch is your informant, reporting on operatives' GitHub activity.

## Project Structure
- `src/ghsnitch/` — package source code
  - `cli.py` — Click command definition and entry point
  - `api.py` — GitHub GraphQL API interaction logic
  - `config.py` — TOML configuration loading and generation
  - `ui.py` — Terminal formatting, colour grading, OSC 8 hyperlinks
  - `updater.py` — Version checking and caching
- `tests/` — module-specific pytest suite
- `pyproject.toml` — project metadata, dependencies, tool config
- `Makefile` — build, test, lint, and format targets
- `utils/` — helper scripts for release management
- `mkver.conf` — version bump configuration
- `docs/` — project documentation
  - `docs/manual/` — user-facing manual
  - `docs/design/` — technical design documents

## Environment
- Python >= 3.11
- Package manager: **uv** (not pip). Use `uv sync`, `uv run`, etc.
- Requires `GITHUB_TOKEN` environment variable at runtime.

## Common Commands
- `make test` — run tests (`uv run pytest -v`)
- `make lint` — check linting and formatting (`ruff check` + `black --check`)
- `make format` — auto-fix lint and formatting (`ruff check --fix` + `black`)
- `make build` — build a shiv executable to `dist/gh-snitch`
- `make smoketest` — run the built binary with `--version`

## Smoke Test
```bash
GITHUB_TOKEN=<token> uv run gh-snitch --users mrsixw --years 3 --no-update-check
```

## Testing
- Tests use `pytest` with `monkeypatch` for mocking and `click.testing.CliRunner` for CLI tests.
- Run `make test` before committing.
- **Never use bare `except Exception`.** Catch specific exception types.

## Commit Messages
- Use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`).
- Keep the summary short and imperative.
- Never include Claude session URLs in commit messages or PR descriptions.

## Tone and Personality
- This project embraces spy theming. Operatives, surveillance, handlers, dossiers — lean into it.
- Error messages and status output use spy-flavoured language and emoji.
- Keep the spy flavour in the UI layer. The underlying code should be clean and well-tested.

## Documentation
- User-facing documentation lives in `docs/manual/`.
- Design documents live in `docs/design/`.
- When changing CLI options or user-visible behaviour, always update **all three** of:
  - `README.md` — the options table
  - `docs/manual/options.md` — the full options reference and config file example
  - `docs/manual/usage.md` — add or update the relevant usage section

## Code Quality
- Use `ruff` (lint + import sorting) and `black` (formatting).
- Never use bare `except Exception`.
- Before committing, run `make test`, `make lint`.
- Before committing a feature or fix, confirm docs have been updated if any CLI options or user-visible behaviour changed.
