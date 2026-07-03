.ONESHELL:
SHELL = /bin/bash

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DESTDIR ?=

.PHONY: activate build version-bump release gh-snitch smoketest test lint format install uninstall

.venv:
	uv venv .venv
	uv sync --extra dev

activate: .venv
	. .venv/bin/activate

build: .venv

	uv sync --extra build
	mkdir -p dist
	uv run shiv -c gh-snitch -o dist/gh-snitch --python '/usr/bin/env python3.13' .

install: build
	install -d "$(DESTDIR)$(BINDIR)"
	install -m 755 dist/gh-snitch "$(DESTDIR)$(BINDIR)/gh-snitch"

uninstall:
	rm -f "$(DESTDIR)$(BINDIR)/gh-snitch"

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
