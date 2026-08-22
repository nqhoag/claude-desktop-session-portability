---
name: resume-backedup-desktop
description: Use after switching Anthropic accounts in Claude Desktop, or whenever a session that used to exist is missing from the app. Recovers it into the current account. Triggers on "restore my sessions", "khôi phục session", "session cũ đâu rồi", "mất session sau khi đổi account", "session không hiện trong app", "bring back my old sessions", "resume a Claude Desktop session", "open session in Desktop", "import sessions from my other account". Works without signing back into the old account.
---

# Restore a Claude Desktop session

Bring a session back into the Claude Desktop app — including one belonging to a different Anthropic account — or reopen it in the terminal.

## The problem

An account switch never deletes sessions. The app simply lists the ones belonging to whoever is signed in, so everything else disappears from view and looks lost.

Restoring does not require signing back into the old account, and does not take anything away from it. The session becomes visible under the account in use now, and stays available to the other one.

Requires Claude Desktop **1.1.9669 or newer**; the script checks and refuses otherwise.

## Steps

### 1. Find the session

Ask whether to look at active sessions only or all of them including archived, unless the user already said. Something missing from the app may simply have been archived, so a search that skips archived sessions can come back empty and look like real loss.

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh list --active
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh list --all
```

Every session on the machine, every account, newest first, with state, branch, working directory and title. A `sessions-*.tsv` snapshot under `~/.claude/session-backups/` works as a source too.

Match on the title and timestamp with the user rather than on identifiers — a session has more than one, they do not stay in sync, and the one shown in the interface often will not resolve. Feed the script whatever identifier the listing gives you; it does the matching itself.

### 2. Restore it

Into the Claude Desktop app — the default, and the right answer when the complaint is "my session disappeared":

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh desktop <id>
```

It appears as a tab under the current account.

Or into the terminal instead, when the user wants to keep working headless:

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh resume <id>
```

This changes into the session's original working directory first. If the session is still open in the app, add `--fork` to branch a new one rather than contend with the live copy.

### 3. Restoring many at once

Ask about scope here too, and be concrete about the cost — restoring archived sessions puts things the user deliberately filed away back in front of them.

| Scope | Restores | Pick it when |
|---|---|---|
| Active | Only sessions still in play | Just switched accounts and wants their current work back |
| All | Archived ones too | Machine move, or genuinely wants everything visible again |

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh import-all --active
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh import-all --all
```

Either way it finds what is not currently visible under the signed-in account, prints the list with archived ones marked, and waits for confirmation.

**Each session becomes a tab**, so on a machine with dozens hidden this floods the window. Show the user the candidate list and agree on a batch size first:

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh import-all --active --limit 10
```

Do not pass `--yes` unless the user explicitly asked for an unattended bulk restore.

## Choosing between the two targets

| | `desktop` | `resume` |
|---|---|---|
| Opens in | The app, as a tab | A terminal window |
| Needs the original working directory to still exist | No | Yes |
| Recovers a session from another account | Yes, and it shows up in the app | Yes, but stays in the terminal |

## When a session will not come back

- **It never showed up in step 1** — re-run the listing with `--all` before concluding anything. Archived is the most common reason a session is "missing".
- **The listing shows no usable identifier** — the session was created but never actually ran, so there is no conversation to restore.
- **`resume` reports the working directory is gone** — the git worktree was deleted. Use `desktop`, which does not need it.
- **Nothing matches the id** — almost always an identifier typed out of the interface by hand. Run `list` and match on the title instead.

## Do not

- **Do not sign out of the current account to "free" the old sessions.** Restoring works from where you are; signing out just costs time.
- **Do not hand-edit Claude Desktop's own files** to make a session reappear. Let the script do it — a malformed record is harder to recover from than a hidden session.
