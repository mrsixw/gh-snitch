.ONESHELL:
SHELL = /bin/bash

.PHONY: activate build version-bump release gh-snitch smoketest test lint format

.venv:
	uv venv .venv
	uv sync --extra dev

activate: .venv
	. .venv/bin/activate

build: .venv

	uv sync --extra build
	mkdir -p dist
	uv run shiv -c gh-snitch -o dist/gh-snitch --python "$(shell uv python find 3.13)" .

version-bump:
	git mkver patch

release: build

gh-snitch: build

smoketest: build .venv
	. .venv/bin/activate && ./dist/gh-snitch --version

test: .venv
	uv sync --extra test
	uv run pytest -v

lint: .venv
	uv sync --extra lint
	uv run ruff check .
	uv run black --check .

format: .venv
	uv sync --extra lint
	uv run ruff check --fix .
	uv run black .
