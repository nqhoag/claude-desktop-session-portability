#!/usr/bin/env bash
#
# Install the skills into ~/.claude/skills so every project can use them.
#
#   ./install.sh              # install / update
#   ./install.sh --uninstall  # remove
#
# Each skill folder is copied whole; its scripts live inside it, so the paths in
# SKILL.md resolve the same way in this repo and after install.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
SKILLS=(list-desktop-sessions switch-desktop-account)
# Replaced by switch-desktop-account; left installed, their triggers would compete with it.
RETIRED=(backup-desktop-session resume-backedup-desktop)

remove() {
  for s in "$@"; do
    [ -e "$SKILLS_DIR/$s" ] || continue
    rm -rf "${SKILLS_DIR:?}/$s"
    echo "removed $SKILLS_DIR/$s"
  done
}

if [ "${1:-}" = "--uninstall" ]; then
  remove "${SKILLS[@]}" "${RETIRED[@]}"
  exit 0
fi

case "$(uname -s)" in
  Darwin) ;;
  *) echo "warning: Claude Desktop session paths are macOS-specific; skills may not work here." >&2 ;;
esac

mkdir -p "$SKILLS_DIR"
remove "${RETIRED[@]}"

for s in "${SKILLS[@]}"; do
  src="$REPO_DIR/skills/$s"
  [ -d "$src" ] || { echo "missing skill source: $src" >&2; exit 1; }
  rm -rf "${SKILLS_DIR:?}/$s"
  cp -R "$src" "$SKILLS_DIR/$s"
  echo "installed $SKILLS_DIR/$s"
done

echo
echo "Done. In Claude Desktop, ask: \"switch my Claude Desktop account\". Or check where you are:"
echo "  python3 ~/.claude/skills/switch-desktop-account/scripts/repair-restored-sessions.py status"
