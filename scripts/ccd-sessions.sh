#!/usr/bin/env bash
#
# ccd-sessions.sh — inventory, back up and restore Claude Desktop sessions.
#
# Problem this solves:
#   Signing into a different Anthropic account makes the Claude Desktop session list look
#   empty. The sessions are not deleted — the app lists only those belonging to the account
#   currently signed in. This script sees all of them regardless of account, and can bring
#   any of them back into the current one.
#
# Ids: a session carries more than one identifier and they do not stay in sync, so an id
# copied out of the UI by hand often will not resolve. Every command below accepts whichever
# form you have and does the matching itself. Prefer that over guessing.
#
# Scope: list, backup and import-all all take --active (live sessions only, the default)
# or --all (archived ones too). Archived sessions are still fully restorable; they are
# just ones the user has already put away, so they are excluded unless asked for.
#
# Usage:
#   ccd-sessions.sh list [--active|--all]        # every session on this Mac, all accounts
#   ccd-sessions.sh backup [--active|--all]      # snapshot + emit a resume-*.sh helper
#   ccd-sessions.sh desktop <id>                 # restore the session into the Desktop app
#   ccd-sessions.sh import-all [--active|--all] [--limit N] [--yes]
#                                                # restore what is not visible under this account
#   ccd-sessions.sh resume <id>                  # reopen it in the terminal instead
#   ccd-sessions.sh resume <id> --fork           # ...as a new session, if the app still has it open

set -euo pipefail

STORE="$HOME/Library/Application Support/Claude/claude-code-sessions"
BACKUP_DIR="$HOME/.claude/session-backups"

die() { printf '%s\n' "$*" >&2; exit 1; }

[ -d "$STORE" ] || die "Session store not found: $STORE"

# Emits TSV: cliSessionId \t localId \t archived \t running_hint \t lastActivityISO \t branch \t cwd \t title
dump_tsv() {
  /usr/bin/python3 - "$STORE" <<'PY'
import json, os, sys, datetime

store = sys.argv[1]
rows = []
for root, _dirs, files in os.walk(store):
    for name in files:
        if not (name.startswith("local_") and name.endswith(".json")):
            continue
        path = os.path.join(root, name)
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        ts = d.get("lastActivityAt") or 0
        try:
            iso = datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
        except Exception:
            iso = "?"
        rows.append((
            ts,
            d.get("cliSessionId") or "",
            d.get("sessionId") or "",
            "archived" if d.get("isArchived") else "active",
            iso,
            d.get("branch") or "-",
            d.get("cwd") or "",
            (d.get("title") or "(untitled)").replace("\t", " ").replace("\n", " "),
        ))

rows.sort(key=lambda r: r[0], reverse=True)
for r in rows:
    print("\t".join(str(x) for x in r[1:]))
PY
}

# Reads --active / --all from the argument list and echoes the resolved scope.
# Anything else is rejected so a typo never silently changes what gets captured.
parse_scope() {
  local scope="active" a
  for a in "$@"; do
    case "$a" in
      --active) scope="active" ;;
      --all)    scope="all" ;;
    esac
  done
  printf '%s\n' "$scope"
}

# Feeds dump_tsv through the scope filter.
scoped_tsv() {
  if [ "$1" = "all" ]; then
    dump_tsv
  else
    dump_tsv | awk -F'\t' '$3 != "archived"'
  fi
}

cmd_list() {
  local scope; scope="$(parse_scope "$@")"

  printf 'Scope: %s\n\n' "$([ "$scope" = all ] && echo "all sessions, archived included" || echo "active sessions only")"
  printf '%-38s %-9s %-17s %-46s %s\n' "CLI SESSION ID" "STATE" "LAST ACTIVITY" "BRANCH" "TITLE"
  printf '%s\n' "$(printf '%.0s-' {1..150})"

  scoped_tsv "$scope" | while IFS=$'\t' read -r cli local state when branch cwd title; do
    printf '%-38s %-9s %-17s %-46s %s\n' "${cli:-<none>}" "$state" "$when" "${branch:0:46}" "${title:0:70}"
  done
}

cmd_backup() {
  local scope stamp map resume
  scope="$(parse_scope "$@")"
  stamp="$(date +%Y%m%d-%H%M)"
  map="$BACKUP_DIR/sessions-$stamp-$scope.tsv"
  resume="$BACKUP_DIR/resume-$stamp-$scope.sh"

  mkdir -p "$BACKUP_DIR"
  {
    printf 'cliSessionId\tlocalId\tstate\tlastActivity\tbranch\tcwd\ttitle\n'
    scoped_tsv "$scope"
  } > "$map"

  {
    echo '#!/usr/bin/env bash'
    echo "# Generated $stamp by ccd-sessions.sh (scope: $scope)."
    echo '# Each block is standalone: uncomment one and run it.'
    echo
    scoped_tsv "$scope" | while IFS=$'\t' read -r cli local state when branch cwd title; do
      [ -z "$cli" ] && continue
      printf '# %s  [%s]  %s%s\n' "$when" "$branch" "$title" "$([ "$state" = archived ] && echo '  (archived)')"
      printf '# (cd %q && claude --resume %s)\n\n' "$cwd" "$cli"
    done
  } > "$resume"
  chmod +x "$resume"

  local n
  n="$(($(wc -l < "$map") - 1))"
  printf 'Backed up %s session(s), scope: %s\n  mapping : %s\n  resume  : %s\n' \
    "$n" "$scope" "$map" "$resume"
}

cmd_resume() {
  local want="${1:-}" fork=0
  [ -n "$want" ] || die "usage: ccd-sessions.sh resume <id> [--fork]"
  [ "${2:-}" = "--fork" ] && fork=1

  # Accept local_<uuid>, bare <uuid>, or the cliSessionId directly.
  local bare="${want#local_}"
  local line
  line="$(dump_tsv | awk -F'\t' -v a="$want" -v b="$bare" \
    '$1==a || $1==b || $2==a || $2=="local_" b {print; exit}')"
  [ -n "$line" ] || die "No session matched: $want  (run: ccd-sessions.sh list)"

  local cli cwd title
  cli="$(printf '%s' "$line" | cut -f1)"
  cwd="$(printf '%s' "$line" | cut -f6)"
  title="$(printf '%s' "$line" | cut -f7)"

  [ -n "$cli" ] || die "Session has no cliSessionId yet (never started?): $want"
  [ -d "$cwd" ] || die "Working directory is gone (worktree deleted?): $cwd"

  printf 'Resuming: %s\n  cwd: %s\n\n' "$title" "$cwd"
  cd "$cwd"
  if [ "$fork" = 1 ]; then
    exec claude --resume "$cli" --fork-session
  else
    exec claude --resume "$cli"
  fi
}

MIN_DESKTOP_VERSION="1.1.9669"

# Resolves an id (local_/bare/cli) to a single TSV row, or dies.
find_row() {
  local want="$1" bare="${1#local_}" line
  line="$(dump_tsv | awk -F'\t' -v a="$want" -v b="$bare" \
    '$1==a || $1==b || $2==a || $2=="local_" b {print; exit}')"
  [ -n "$line" ] || die "No session matched: $want  (run: ccd-sessions.sh list)"
  printf '%s\n' "$line"
}

assert_desktop() {
  [ -d /Applications/Claude.app ] || die "Claude Desktop is not installed (/Applications/Claude.app)."
  local v
  v="$(defaults read /Applications/Claude.app/Contents/Info.plist CFBundleShortVersionString 2>/dev/null || true)"
  [ -n "$v" ] || return 0
  # Only a coarse guard; the app itself rejects links it cannot handle.
  [ "$(printf '%s\n%s\n' "$MIN_DESKTOP_VERSION" "$v" | sort -V | head -1)" = "$MIN_DESKTOP_VERSION" ] \
    || die "Claude Desktop $v is older than $MIN_DESKTOP_VERSION; session restore is unsupported."
}

cmd_desktop() {
  local want="${1:-}"
  [ -n "$want" ] || die "usage: ccd-sessions.sh desktop <id>"
  assert_desktop

  local line cli title
  line="$(find_row "$want")"
  cli="$(printf '%s' "$line" | cut -f1)"
  title="$(printf '%s' "$line" | cut -f7)"
  [ -n "$cli" ] || die "Session has no cliSessionId yet (never started?): $want"

  printf 'Opening in Claude Desktop: %s\n' "$title"
  open "claude://resume?session=$cli"
}

# Every session whose cliSessionId has no index record under the signed-in account.
# The signed-in account is the one whose store directory was written to most recently.
current_account_dir() {
  local newest="" newest_ts=0 d ts
  for d in "$STORE"/*/; do
    [ -d "$d" ] || continue
    ts="$(find "$d" -name 'local_*.json' -exec stat -f '%m' {} \; 2>/dev/null | sort -rn | head -1)"
    [ -n "$ts" ] || continue
    if [ "$ts" -gt "$newest_ts" ]; then newest_ts="$ts"; newest="$d"; fi
  done
  [ -n "$newest" ] || die "Could not determine the signed-in account directory."
  printf '%s\n' "$newest"
}

cmd_import_all() {
  local limit=0 assume_yes=0 scope
  scope="$(parse_scope "$@")"
  while [ $# -gt 0 ]; do
    case "$1" in
      --limit) limit="${2:-0}"; shift 2 ;;
      --yes|-y) assume_yes=1; shift ;;
      --active|--all) shift ;;
      *) die "unknown option: $1" ;;
    esac
  done
  assert_desktop

  local acct missing
  acct="$(current_account_dir)"
  printf 'Scope: %s\n' "$([ "$scope" = all ] && echo "all sessions, archived included" || echo "active sessions only")"

  missing="$(scoped_tsv "$scope" | while IFS=$'\t' read -r cli local state when branch cwd title; do
    [ -z "$cli" ] && continue
    grep -rqls "\"cliSessionId\": *\"$cli\"" "$acct" 2>/dev/null && continue
    printf '%s\t%s\t%s\t%s\n' "$cli" "$when" "$state" "$title"
  done | sort -u -t$'\t' -k1,1)"

  if [ -z "$missing" ]; then
    printf 'Nothing to restore — every session in scope is already visible under this account.\n'
    [ "$scope" = active ] && printf 'Archived sessions were not considered; re-run with --all to include them.\n'
    return 0
  fi

  local n
  n="$(printf '%s\n' "$missing" | wc -l | tr -d ' ')"
  [ "$limit" -gt 0 ] && [ "$n" -gt "$limit" ] && n="$limit"

  printf '\n%s session(s) will be opened as tabs in Claude Desktop:\n\n' "$n"
  printf '%s\n' "$missing" | head -n "$n" | while IFS=$'\t' read -r cli when state title; do
    printf '  %s  %s%s\n' "$when" "${title:0:70}" "$([ "$state" = archived ] && echo '  (archived)')"
  done

  if [ "$assume_yes" != 1 ]; then
    printf '\nEach one opens a tab. Proceed? [y/N] '
    local reply; read -r reply
    case "$reply" in y|Y|yes|YES) ;; *) echo "Aborted."; return 1 ;; esac
  fi

  printf '%s\n' "$missing" | head -n "$n" | while IFS=$'\t' read -r cli when state title; do
    printf '  -> %s\n' "${title:0:70}"
    open "claude://resume?session=$cli"
    sleep 1   # let the app settle; rapid bursts get dropped
  done
  echo "Done."
}

case "${1:-list}" in
  list)       shift || true; cmd_list "$@" ;;
  backup)     shift || true; cmd_backup "$@" ;;
  resume)     shift; cmd_resume "$@" ;;
  desktop)    shift; cmd_desktop "$@" ;;
  import-all) shift; cmd_import_all "$@" ;;
  *)          die "unknown command: $1  (list | backup | resume | desktop | import-all)" ;;
esac
