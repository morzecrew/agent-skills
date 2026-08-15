# Task runner for the skills collection.
# `just` is a convenience: every recipe is a plain command CI can run directly.

# List the recipes
default:
    @just --list

# What CI runs on every push (CI additionally validates PR commit messages,
# which needs a base ref — run `just commits` for that locally)
check: lint validate test

# Markdown style (same config as the pre-commit hook)
lint:
    # Quoted: the shell has no globstar by default, so an unquoted **
    # would silently skip skills/*/references/*.md.
    # Keep this list and `.github/workflows/validate.yml`'s `globs:` identical
    # — they are two copies of one rule, and CI is the one that blocks.
    markdownlint README.md AGENTS.md 'skills/**/*.md' '.github/**/*.md'

# Structural validation of the skill collection — no LLM, no network
validate:
    python3 scripts/validate_skills.py

# Unit tests for the bundled skill scripts
test:
    cd tests && python3 -m unittest discover -s . -p 'test_*.py' -v

# One test module, e.g. `just test-one test_rfc_index`
test-one module:
    cd tests && python3 -m unittest {{module}} -v

# Behavioral skill evals — local only, uses your authenticated claude CLI
evals *args:
    python3 evals/run.py {{args}}

# Validate this repository's own commit messages against the skill
commits base="origin/main":
    python3 skills/gitmoji-conventional/scripts/check_commit_msg.py --range {{base}}..HEAD

# Install the commit-msg hook that enforces the commit format locally
install-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    hook=".git/hooks/commit-msg"
    printf '#!/bin/sh\nexec python3 skills/gitmoji-conventional/scripts/check_commit_msg.py --file "$1"\n' > "$hook"
    chmod +x "$hook"
    echo "installed $hook"
