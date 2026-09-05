.ONESHELL:
SHELL = /bin/bash

# Pinned to the version the CI spell job uses, so the two cannot drift apart.
TYPOS_VERSION := 1.48.0

# Every shell source we ship, plus the test helper, which is shell too and just
# as capable of being wrong.
SHELL_SOURCES := install.sh $(wildcard utils/*.sh) tests/bats/helpers/common.bash

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DESTDIR ?=

.PHONY: activate build version-bump release gh-snitch smoketest test bats lint shellcheck spell format man completions install uninstall

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

man: .venv
	uv sync --extra build
	mkdir -p man1
	uv run python utils/generate_man_page.py man1
	gzip -f man1/gh-snitch.1

completions: .venv
	uv sync
	mkdir -p completions
	_GH_SNITCH_COMPLETE=bash_source uv run gh-snitch > completions/gh-snitch.bash
	# Click emits two unquoted expansions that trip shellcheck; quote them.
	sed -i.bak 's/_GH_SNITCH_COMPLETE=bash_complete $$1)/_GH_SNITCH_COMPLETE=bash_complete "$$1")/' completions/gh-snitch.bash
	sed -i.bak 's/COMPREPLY+=($$value)/COMPREPLY+=("$$value")/' completions/gh-snitch.bash
	rm -f completions/gh-snitch.bash.bak
	_GH_SNITCH_COMPLETE=zsh_source uv run gh-snitch > completions/_gh-snitch
	_GH_SNITCH_COMPLETE=fish_source uv run gh-snitch > completions/gh-snitch.fish

version-bump:
	git mkver patch

release: build man completions

gh-snitch: build

smoketest: build .venv
	. .venv/bin/activate && ./dist/gh-snitch --version

test: .venv
	uv sync --extra test
	uv run pytest -v

lint: .venv shellcheck spell
	uv sync --extra lint
	uv run ruff check .
	uv run black --check .

# Static analysis for every shell source.
shellcheck:
	npx --yes shellcheck $(SHELL_SOURCES)

# The shell test suite. bats and shellcheck arrive via npx — nothing to install
# by hand beyond node.
bats:
	npx --yes bats tests/bats

# Spelling. uvx fetches typos on demand; uv is already this project's package
# manager.
spell:
	uvx --from typos==$(TYPOS_VERSION) typos

format: .venv
	uv sync --extra lint
	uv run ruff check --fix .
	uv run black .
