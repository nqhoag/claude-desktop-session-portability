---
name: resume-backedup-desktop
description: Use after switching Anthropic accounts in Claude Desktop, or whenever a session that used to exist is missing from the app. Triggers on "restore my sessions", "khôi phục session", "mất session sau khi đổi account", "session không hiện trong app", "bring back my old sessions", "open session in Desktop", "import sessions from my other account", and on restored sessions turning up nameless — "session mất tên sau khi import", "đặt lại tên session cũ", "restored sessions have no name", "rename imported sessions".
---

# Restore a Claude Desktop session

An account switch deletes nothing — the app lists only the signed-in account's sessions, so the rest look lost. Restoring needs no sign-in to the old account and takes nothing from it. Requires Claude Desktop **1.1.9669+**.

## 1. Find it

Ask first: active only, or all including archived? "Missing" usually means archived, so an active-only search can look like real loss.

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh list --active   # or --all
```

Match with the user on title and timestamp, not identifiers — a session has several, and the one shown in the interface often will not resolve. Pass whatever id the listing prints.

## 2. Restore it

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh desktop <id>   # into the app as a tab — the usual answer
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh resume <id>    # into the terminal; add --fork if also open in the app
```

`resume` needs the original working directory to still exist; `desktop` does not.

## 3. Many at once

Ask about scope — `--all` puts back sessions the user archived.

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh import-all --active --limit 10
```

**Each session becomes a tab**, so dozens of hidden sessions flood the window — agree a batch size first. Do not pass `--yes` unless asked.

## 4. Put the names back

A restored session arrives with **no name at all** — the link that carries it into the app carries the identifier and nothing else. So `desktop` and `import-all` both end by printing a **rename map**: one line per session, its id beside the name it had.

The restore is complete only when both halves are done:

| Half | Done when |
|---|---|
| Tabs open | every session in the batch shows up in the app |
| Names back | every rename-map line has been applied with the session-renaming tool |

```bash
~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh title-map --active   # reprint the map
```

Take each id and title exactly as printed. Sessions that never carried a name are absent — nothing to put back.

## When it does not come back

- **Missing from step 1** — re-run with `--all`; archived is the usual reason.
- **No usable identifier** — created but never ran; nothing to restore.
- **Nothing matches the id** — one copied by hand from the interface. Match on title.
- **Came back unnamed** — expected. Finish step 4.

Never sign out to "free" old sessions. Never hand-edit Claude Desktop's files — a malformed record is worse than a hidden session.
