#!/bin/bash

printf "\n🎨  Running Ruff Format..."
uv run ruff format .

printf "\n🔍  Running Ruff Lint (Fixing auto-fixable issues)...\n"
uv run ruff check . --fix

printf "\n🛡️  Running Mypy (Type Check)...\n"
uv run mypy .

printf "\n✅  Check Complete!"