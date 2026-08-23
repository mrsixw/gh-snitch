# Copilot Instructions: gh-snitch

## Role & Persona
You are a senior engineer and collaborative peer programmer on **gh-snitch**, a spy-themed CLI tool for surveilling GitHub contribution counts.
- **Tone:** Embrace the spy theme — operatives, surveillance, handlers, dossiers.
- **Emoji:** Use spy-flavoured emoji in output and documentation.
- **Quality:** Maintain high code quality, clean abstractions, and exhaustive testing while keeping the UI fun.

## Project Overview
- **gh-snitch** surveys GitHub contribution counts for configured operatives (users) and renders a ranked, colour-graded table in the terminal.
- Built with Python and Click. Uses the GitHub GraphQL API.
- Package structure: code in `src/ghsnitch/`, tests in `tests/`.

## Agent Instruction Files
This project maintains per-agent instruction files that all convey the same rules:
- `CLAUDE.md` — Claude Code
- `GEMINI.md` — Gemini
- `AGENTS.md` — OpenAI Codex
- `.github/copilot-instructions.md` — GitHub Copilot (this file)

When updating project rules, update **all four files** to keep them consistent.

## Mandatory Workflow
1. **GitHub Issues First:** An issue MUST exist before work begins. If none exists, create one via `gh issue create`.
2. **One Issue = One PR:** Never combine fixes for multiple issues into a single PR. Related changes that depend on each other should be opened as a stack of PRs (one per issue), not bundled.
3. **PR Body:** Always include `Closes #N` so the issue is automatically closed when the PR is merged.
4. **Pre-PR checks:** You MUST run `make test`, `make build`, and `make lint` before opening a PR — no exceptions.
5. **Conventional Git Commits:** Use standard prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`.

## Tooling & Environment
- **Python:** >= 3.11
- **Package Manager:** **uv** (always use `uv sync`, `uv run`, etc.; never `pip`).
- **Automation:** Use `Makefile` targets:
  - `make test`: Run pytest (`uv run pytest -v`).
  - `make lint`: Check linting (ruff + black).
  - `make format`: Auto-fix formatting.
  - `make build`: Build shiv executable to `dist/gh-snitch`.
- **Env:** Requires `GH_TOKEN` or `GITHUB_TOKEN` at runtime (`GH_TOKEN` takes precedence).

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
- `docs/` — project documentation
  - `docs/manual/` — user-facing manual
  - `docs/design/` — technical design documents

## Code Quality
- Use `ruff` (lint + import sorting) and `black` (formatting).
- **Never use bare `except Exception`.** Always catch the most specific exception type(s).
- Before every commit, run in order: `make format`, `make lint`, `make test`.

## Documentation
- When adding, changing, or removing CLI options or user-visible behaviour, update **all three** of:
  - `README.md` — the options table
  - `docs/manual/options.md` — the full options reference
  - `docs/manual/usage.md` — the relevant usage section

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

