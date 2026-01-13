#!/bin/bash

# 에러 발생 시 즉시 중단
set -e

printf "\n🧪  Running Pytest with Coverage...\n\n"
uv run coverage run -m pytest

printf "\n📊  Generating Coverage Report...\n\n"

# 80% 미만일 경우 경고
uv run coverage report --fail-under=80

printf "\n ✅  Test and Coverage Complete!"