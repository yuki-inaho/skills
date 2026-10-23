# Thin wrappers around uv. Every command is available without just.
set shell := ["bash", "-euo", "pipefail", "-c"]
export PYTHONDONTWRITEBYTECODE := "1"

default:
    @just --list

sync:
    uv sync --locked --group dev

lint:
    uv run --locked ruff check .
    uv run --locked python -m compileall -q skills tests

test:
    uv run --locked pytest tests -q

validate:
    uv run --locked python skills/skill-creator/scripts/validate_skill.py

privacy:
    uv run --locked python tests/privacy_scan.py

# One-command aggregate of the local required checks.
# The external agent-jsonl-compact contract stays a separate, explicit profile.
check: lint validate test privacy

# Dedicated profile: the pinned external CLI is required and never skipped.
test-contract:
    REQUIRE_AGENT_JSONL=1 uv run --locked pytest tests/test_agent_jsonl_contract.py -q
