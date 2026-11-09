# Claude Desktop session portability

Two Claude Code skills that carry Claude Desktop sessions across an Anthropic account switch, with their worktree, sidebar group and pin.

## The problem

Claude Desktop shows only the signed-in account's sessions, groups and pins. Sign in as another account and the list looks empty.

An account switch deletes nothing. Each session's transcript is one file shared by every account; each account keeps only a small record (about 15 KB) that points at it. These skills read every account's records, let you choose sessions, and bring them into the new account.

A plain restore through the app's `claude://resume` link loses three things. These skills put them back:

- **Worktree.** The rebuilt record forgets its worktree, and the app's worktree store still names the old account's session as the owner. The app then tries a fresh checkout of the same branch and fails with "This session's branch is checked out in another folder".
- **Sidebar group and pin.** Both are stored per account, keyed by a session id that changes on restore.
- **Archive state.** A restored session can arrive archived although the original was not.

## Install

```bash
git clone https://github.com/nqhoag/claude-desktop-session-portability.git
cd claude-desktop-session-portability
./install.sh
```

Installs into `~/.claude/skills/` and removes the retired `backup-desktop-session` and `resume-backedup-desktop`. Remove with `./install.sh --uninstall`.

macOS only. Needs Claude Desktop 1.1.9669 or newer and `python3`.

## The skills

| Skill | Use when |
|---|---|
| `switch-desktop-account` | Before or after switching accounts, moving to a new Mac, or when sessions, groups or pins are missing. |
| `list-desktop-sessions` | "What sessions do I have?" across every account, active or including archived. |

They trigger from ordinary phrasing in English or Vietnamese.

## The four steps

| Step | Where | Who | What |
|---|---|---|---|
| 1 | Claude Desktop | the skill | choose sessions; `plan` writes the plan file |
| 2 | Claude Desktop | you | sign out, sign in to the new account |
| 3 | macOS Terminal.app | you run `apply` | restore each session, quit the app, repair worktrees, reopen it |
| 4 | Claude Desktop, new account | the skill | rebuild groups and pins, unarchive |

`status` names the step you are on and the next action. The skill runs it before anything else, so no step runs twice or out of order. Already signed in to the new account? Step 1 then lists the hidden sessions, and step 2 is skipped.

`apply` must run in Terminal.app: it quits Claude Desktop, and a terminal inside the app would die with it. It refuses to start there. It is safe to re-run; finished parts are skipped, and the app is restarted only if a worktree still needs repair.

## Direct script use

```bash
S=~/.claude/skills/switch-desktop-account/scripts
python3 $S/repair-restored-sessions.py status                      # current step and next action
python3 $S/repair-restored-sessions.py scan [--since DAYS] [--all] [--mine]
python3 $S/repair-restored-sessions.py plan <cliSessionId>...     # step 1
python3 $S/repair-restored-sessions.py apply                       # step 3, Terminal.app only
python3 $S/repair-restored-sessions.py worktrees --dry-run         # what a repair would change
bash $S/ccd-sessions.sh list [--active|--all]                      # every session, every account
bash $S/ccd-sessions.sh backup [--active|--all]                    # snapshot to ~/.claude/session-backups/
```

Same Mac: nothing to copy. New Mac: carry `~/.claude/projects/` (the transcripts) and `~/.claude/session-backups/`.

## Caveats

- Not handled yet: switching back to an account that already has the sessions. Its sessions can hit the branch error above.
- A worktree held by another session is left alone; that session runs in the repository folder.
- Depends on Claude Desktop internals that are not a published interface. Records are written only while the app is quit, and every file changed is backed up under `~/.claude/session-backups/record-backup-<time>/`.
- Reads only local files. Nothing leaves the machine.

## License

MIT
