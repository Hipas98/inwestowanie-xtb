#!/bin/bash
# SessionStart hook: in Claude Code cloud sessions (phone/web) build .venv from requirements.txt.
# Locally it exits immediately, so it never touches your machine.
[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 1
if [ -x .venv/bin/python ] && sha256sum --check --status .venv/.requirements.sha256 2>/dev/null; then
  exit 0
fi
python3 -m venv .venv \
  && .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt \
  && sha256sum requirements.txt > .venv/.requirements.sha256
exit 0
