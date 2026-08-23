# Codex Instructions: gh-snitch

Instructions found in this file are foundational mandates. They take absolute precedence over general workflows and tool defaults.

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

## Agent Instruction Files
This project maintains per-agent instruction files that all convey the same rules:
- `CLAUDE.md` — Claude Code
- `GEMINI.md` — Gemini
- `AGENTS.md` — OpenAI Codex (this file)
- `.github/copilot-instructions.md` — GitHub Copilot

When updating project rules, update **all four files** to keep them consistent.

## Environment
- Python >= 3.11
- Package manager: **uv** (not pip). Use `uv sync`, `uv run`, etc.
- Requires `GH_TOKEN` or `GITHUB_TOKEN` environment variable at runtime (`GH_TOKEN` takes precedence).

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

## Work Items
- This project uses GitHub issues. Reference the GitHub issue number in branch names and PR titles.
- **A GitHub issue MUST exist before any work begins.** If the user requests a change and no issue exists yet, create one before starting implementation. Every branch, commit, and PR must reference an issue number.
- **One issue = one branch = one PR.** Never combine fixes for multiple issues into a single PR. If changes are related and depend on each other, open them as a stack of PRs (one per issue) rather than bundling.

## Module API contract
- A leading `_` means "internal to this module". Anything a sibling module
  imports must not have one, and must appear in that module's `__all__`.
- Every module in `src/ghsnitch/` declares `__all__`. Add new public names to it.
- Reach other modules through their public names only. If you need something a
  module keeps private, widen that module's API deliberately — rename it and add
  it to `__all__` — rather than reaching past the underscore. A private name you
  had to import was never really private.
- The same applies to third-party libraries: depend on their documented API, not
  on internals that can change in a patch release.
- `tests/test_public_api.py` enforces the first two. Tests may still reach into
  the internals of the module they test — that boundary is not policed.

## Commit Messages
- Use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`).
- Keep the summary short and imperative.

## Pull Requests
- Always include `Closes #N` in the PR body so the issue is automatically closed when the PR is merged.
- **MANDATORY: Before opening a PR, you MUST run `make test`, `make build`, and `make lint`** to ensure the code is functional, buildable, and compliant with project standards.

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
