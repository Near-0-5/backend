#!/bin/bash

# 에러 발생 시 즉시 중단
set -e

printf "\n📊   Running Pytest with Coverage...\n\n"

uv run pytest

printf "\n ✅  Test and Coverage Complete!"