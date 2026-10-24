#!/bin/bash
# Build a clean, shareable copy of the project in .cache/repo-export (git-ignored).
# Personal files (portfel, dziennik, analizy, dane, wykresy) are replaced by empty templates.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/.cache/repo-export"
mkdir -p "$OUT"
# keep .git if the export was already pushed once, wipe everything else
find "$OUT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

cp "$ROOT"/{CLAUDE.md,README.md,MASTER-PROMPT.md,requirements.txt,.gitignore} "$OUT"/
mkdir -p "$OUT/.claude/agents" "$OUT/scripts" "$OUT/szablony" "$OUT"/{analizy,dane,wykresy}
cp "$ROOT"/.claude/agents/*.md "$OUT/.claude/agents/"
cp "$ROOT/.claude/settings.json" "$OUT/.claude/"
cp "$ROOT"/scripts/*.py "$ROOT"/scripts/*.sh "$OUT/scripts/"
cp "$ROOT"/szablony/*.md "$OUT/szablony/"
mkdir -p "$OUT/projekt-free" && cp "$ROOT"/projekt-free/* "$OUT/projekt-free/"
cp "$ROOT/szablony/portfel.md" "$OUT/portfel.md"
cp "$ROOT/szablony/dziennik.md" "$OUT/dziennik.md"
touch "$OUT"/{analizy,dane,wykresy}/.gitkeep

echo "Eksport gotowy: $OUT"
find "$OUT" -path "$OUT/.git" -prune -o -type f -print | sed "s|$OUT/||" | sort
