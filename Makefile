SHELL = /bin/bash

# Create the venv with the interpreter pinned in .python-version and install
# the dev/test/publish toolchain from the [dev] extra.
.PHONY: deps
.ONESHELL:
deps:
	set -e
	@echo "Setting up the Python environment..."
	python3 -m venv venv
	. venv/bin/activate
	pip install -U pip
	pip install -e '.[dev]'
	@echo "Dependencies installed."

# Auto-fix formatting and lint issues.
.PHONY: format
.ONESHELL:
format:
	set -e
	. venv/bin/activate
	ruff format
	ruff check --fix

# Full gate: format check, lint, type check, and the entire test suite.
.PHONY: test
.ONESHELL:
test:
	@echo "Running format check, lint, type check, and tests..."
	set -e
	. venv/bin/activate
	ruff check
	ruff format --check --diff
	npx -y markdownlint-cli2 "*.md"
	pyright --venvpath . --warnings
	python -m pytest
	@echo "All checks passed."

# Alias for `make test`.
.PHONY: check
check: test

# Refresh the committed GraphQL schema fixture from the live API.
.PHONY: schema
.ONESHELL:
schema:
	set -e
	. venv/bin/activate
	python scripts/dump_schema.py

# Build the sdist + wheel into dist/.
.PHONY: build
.ONESHELL:
build:
	set -e
	. venv/bin/activate
	rm -rf dist
	python -m build

# Build then upload to PyPI (requires credentials/token).
.PHONY: publish
.ONESHELL:
publish: build
	set -e
	. venv/bin/activate
	twine check dist/*
	twine upload dist/*

.PHONY: clean
clean:
	@echo "Cleaning up..."
	rm -rf **/__pycache__
	rm -rf .pytest_cache .ruff_cache htmlcov
	rm -f .coverage .coverage.* junit.xml
	rm -rf dist build *.egg-info
	rm -rf venv
	@echo "Cleanup complete."
