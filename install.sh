#!/usr/bin/env bash
#
# Install the skills into ~/.claude/skills so every project can use them.
#
#   ./install.sh              # install / update
#   ./install.sh --uninstall  # remove
#
# scripts/ccd-sessions.sh in this repo is the single source of truth; the installer
# copies it into the backup skill, which is where every SKILL.md references it.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
SKILLS=(list-desktop-sessions backup-desktop-session resume-backedup-desktop)

if [ "${1:-}" = "--uninstall" ]; then
  for s in "${SKILLS[@]}"; do
    rm -rf "${SKILLS_DIR:?}/$s"
    echo "removed $SKILLS_DIR/$s"
  done
  exit 0
fi

case "$(uname -s)" in
  Darwin) ;;
  *) echo "warning: Claude Desktop session paths are macOS-specific; skills may not work here." >&2 ;;
esac

mkdir -p "$SKILLS_DIR"

for s in "${SKILLS[@]}"; do
  src="$REPO_DIR/skills/$s"
  [ -d "$src" ] || { echo "missing skill source: $src" >&2; exit 1; }
  mkdir -p "$SKILLS_DIR/$s"
  cp "$src/SKILL.md" "$SKILLS_DIR/$s/SKILL.md"
  echo "installed $SKILLS_DIR/$s/SKILL.md"
done

# Every skill invokes the script through the backup skill's path.
mkdir -p "$SKILLS_DIR/backup-desktop-session/scripts"
cp "$REPO_DIR/scripts/ccd-sessions.sh" "$SKILLS_DIR/backup-desktop-session/scripts/ccd-sessions.sh"
chmod +x "$SKILLS_DIR/backup-desktop-session/scripts/ccd-sessions.sh"
echo "installed $SKILLS_DIR/backup-desktop-session/scripts/ccd-sessions.sh"

echo
echo "Done. Try:"
echo "  ~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh list"
