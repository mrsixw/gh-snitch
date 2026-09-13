.ONESHELL:
SHELL = /bin/bash

# Pinned so the same version runs locally and in CI, and cannot drift apart.
# Both arrive through uv, which is already this project's package manager —
# no second ecosystem to install.
TYPOS_VERSION := 1.48.0
SHELLCHECK_VERSION := 0.11.0.1

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
	uv run shiv -c gh-snitch -o dist/gh-snitch --python '/usr/bin/env python3' .

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

# Deliberately does NOT activate the venv: the venv puts the exact interpreter
# the binary was built against on PATH, so an activated smoke test passes even
# when the shebang names a version no user has. Run it the way a user would.
smoketest: build
	./dist/gh-snitch --version

test: .venv
	uv sync --extra test
	uv run pytest -v

lint: .venv shellcheck spell
	uv sync --extra lint
	uv run ruff check .
	uv run black --check .

# Static analysis for every shell source. shellcheck-py ships the real
# shellcheck binary as a wheel, so this is the same tool npx fetched — but
# pinned, and without downloading from GitHub, which rate-limits shared CI
# runners and made this job fail on unrelated commits.
shellcheck:
	uvx --from shellcheck-py==$(SHELLCHECK_VERSION) shellcheck $(SHELL_SOURCES)

# The shell test suite. bats is the one tool with no PyPI build, so it comes
# from the system package manager rather than uv: `brew install bats-core` on
# macOS, `apt-get install bats` on Debian/Ubuntu and CI. That means it is the
# one version that can differ between a laptop and CI; bats is stable enough
# across minor versions for that to be a fair trade against pulling in npm.
bats:
	@command -v bats >/dev/null 2>&1 || { \
	  echo "❌ bats not found. Install it with one of:"; \
	  echo "     brew install bats-core     (macOS)"; \
	  echo "     apt-get install bats       (Debian/Ubuntu)"; \
	  exit 1; }
	bats tests/bats

# Spelling. Kept as its own target *and* a separate CI job: `lint` runs its
# prerequisites in order, so a shellcheck failure stops make before spelling is
# ever checked. The standalone job is the only one guaranteed to run.
spell:
	uvx --from typos==$(TYPOS_VERSION) typos

format: .venv
	uv sync --extra lint
	uv run ruff check --fix .
	uv run black .
