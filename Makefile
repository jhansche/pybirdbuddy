SHELL = /bin/bash -xe

# Create the venv with the interpreter pinned in .python-version and install
# the dev/test/publish toolchain from the [dev] extra.
.PHONY: deps
deps:
	@echo "Setting up the Python environment..."
	python3 -m venv venv
	venv/bin/pip install -U pip
	venv/bin/pip install -e '.[dev]'
	@echo "Dependencies installed."

# Auto-fix formatting and lint issues.
.PHONY: format
format:
	venv/bin/ruff format
	venv/bin/ruff check --fix

# Full gate: format check, lint, type check, and the entire test suite.
.PHONY: test
test:
	@echo "Running format check, lint, type check, and tests..."
	venv/bin/ruff check
	venv/bin/ruff format --check --diff
	npx -y markdownlint-cli2 "*.md"
	venv/bin/pyright --warnings
	venv/bin/pytest tests/
	@echo "All checks passed."

# Alias for `make test`.
.PHONY: check
check: test

# Refresh the committed GraphQL schema fixture from the live API.
.PHONY: schema
schema:
	venv/bin/python scripts/dump_schema.py

# Build the sdist + wheel into dist/.
.PHONY: build
build:
	rm -rf dist
	venv/bin/python -m build

# Build then upload to PyPI (requires credentials/token).
.PHONY: publish
publish: build
	venv/bin/twine check dist/*
	venv/bin/twine upload dist/*

.PHONY: clean
clean:
	@echo "Cleaning up..."
	rm -rf **/__pycache__
	rm -rf .pytest_cache .ruff_cache htmlcov
	rm -f .coverage .coverage.* junit.xml
	rm -rf dist build *.egg-info
	rm -rf venv
	@echo "Cleanup complete."
