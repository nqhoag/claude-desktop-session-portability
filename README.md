# Claude Desktop session portability

Three Claude Code skills that make Claude Desktop sessions survive an account switch.

## The problem

Claude Desktop shows the sessions of the account you are signed in as. Sign in as a different one and the list looks empty — as if the work is gone.

It is not. An account switch deletes nothing. But the app has no way to show you the other account's sessions, and the identifier it displays for a session is not reliably the one that can reopen it, so recovering by hand tends to fail and confirm the wrong conclusion.

These skills see every session on the machine regardless of account, snapshot them, and bring any of them back into whichever account you are using now — without signing back into the old one, and without taking anything away from it.

## Install

```bash
git clone https://github.com/nqhoag/claude-desktop-session-portability.git
cd claude-desktop-session-portability
./install.sh
```

Installs into `~/.claude/skills/`, so the skills are available in every project. Remove with `./install.sh --uninstall`.

macOS only. Restoring into the app requires Claude Desktop 1.1.9669 or newer.

## The skills

| Skill | Use when |
|---|---|
| `list-desktop-sessions` | "What sessions do I have?" — across every account, active or including archived. |
| `backup-desktop-session` | Before signing out, switching accounts, or moving to a new Mac. |
| `resume-backedup-desktop` | After the switch, or any time a session is missing from the app. |

They trigger from ordinary phrasing — "back up my sessions before I switch accounts", "my old sessions disappeared", "list everything including archived" — in English or Vietnamese. No need to remember command names.

## Active or all?

Listing, backing up and restoring each take a scope, and the skills will ask before doing anything:

- **Active** — sessions still in play. The default, and right for routine use.
- **All** — archived ones too. Right when moving machines, or auditing, or hunting for something old.

Archived sessions restore exactly as well as active ones. They are excluded by default only because the user already chose to put them away.

## Direct script use

The skills drive one script, installed at
`~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh`.

```bash
ccd-sessions.sh list [--active|--all]           # every session on this Mac, all accounts
ccd-sessions.sh backup [--active|--all]         # snapshot to ~/.claude/session-backups/
ccd-sessions.sh desktop <id>                    # restore one session into the Desktop app
ccd-sessions.sh import-all [--active|--all] [--limit N] [--yes]
                                                # restore everything hidden from this account
ccd-sessions.sh resume <id> [--fork]            # reopen in the terminal instead
```

`<id>` accepts whichever identifier form you have; the script does the matching.

## Typical account switch

```bash
ccd-sessions.sh backup --all      # snapshot first
# sign out, sign in as the other account
ccd-sessions.sh import-all --active --limit 10
```

Nothing needs to be copied for a same-machine switch. For a new Mac, carry both `~/.claude/projects/` (the conversations) and `~/.claude/session-backups/` (the snapshot).

## Caveats

- `import-all` opens one tab per session. Use `--limit`.
- `resume` needs the session's original working directory to still exist; a deleted git worktree breaks it. `desktop` does not care.
- A session that was created but never ran has nothing to restore.
- This depends on Claude Desktop internals that are not a published interface, and could change in a future release. Verified against Claude Code 2.1.221 and Claude Desktop 1.34493.1.
- Reads only your own local files, writes only to `~/.claude/session-backups/` and `~/.claude/skills/`. Nothing leaves the machine.

## License

MIT
