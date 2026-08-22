---
name: backup-desktop-session
description: Use before signing out of Claude Desktop, switching to a different Anthropic account, migrating to a new Mac, or any time someone wants an inventory or snapshot of their Claude Desktop sessions. Triggers on "backup my sessions", "sao lưu session", "đổi account Claude Desktop", "switch Claude account", "list my Claude Desktop sessions", "session nào đang mở", "trước khi log out Claude", "export session list". Produces a durable snapshot so nothing becomes unreachable after the account changes.
---

# Back up Claude Desktop sessions

Snapshot every Claude Desktop session on this machine, so any of them can be recovered later — including after signing into a different account.

## The problem

Claude Desktop shows the sessions of the account you are signed in as. Sign in as someone else and the list looks empty, which reads like the work is gone.

It is not. Nothing is deleted by an account switch. But recovering a session afterwards needs its identifier, and the identifier shown in the interface is not reliably the one that works — copying it by hand usually fails. This skill captures the working identifiers while they are still easy to reach.

## Steps

1. **Ask what to include, unless the user already said.** Archived sessions restore just as well as active ones, so this is a real choice, not a formality.

   | Scope | Covers | Pick it when |
   |---|---|---|
   | Active | Sessions still in play | Routine snapshot before an account switch |
   | All | Active plus archived | Moving machines, or the user wants nothing left behind |

   Show the counts from `list --active` and `list --all` first if the gap is large — a user who thinks they have a dozen sessions may actually have several times that once archived ones are counted.

2. **Run the backup with that scope.**

   ```bash
   ~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh backup --active
   ~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh backup --all
   ```

   It covers every account on the machine, not just the one signed in, and writes two files into `~/.claude/session-backups/`, named with the scope so two snapshots never overwrite each other:

   - `sessions-<stamp>-<scope>.tsv` — one row per session: identifiers, state, last activity, branch, working directory, title
   - `resume-<stamp>-<scope>.sh` — the same list as ready-to-run commands, one commented block per session, archived ones marked

3. **Report what was captured.** Give the user the session count, the scope used, and both file paths.

   If the output spans more than one account, say so plainly — it means they have switched accounts before and already have sessions hidden from the app right now. Offer the `resume-backedup-desktop` skill to bring those back.

4. **Only if the user is moving to a different Mac**, tell them what has to travel with them. The snapshot alone is not enough:

   - `~/.claude/projects/` — the conversations themselves; large, tens of MB per long session
   - `~/.claude/session-backups/` — the snapshot from step 1

   For an account switch on the same Mac, nothing needs copying.

## Just looking, without backing up

Use the `list-desktop-sessions` skill. The session-listing tools built into the app report the signed-in account only, so do not treat their output as the full set.

## After the backup

Signing out and back in as another account is safe. To pull sessions back into view afterwards, use the `resume-backedup-desktop` skill.

## Do not

- **Do not delete anything under `~/.claude/projects/` to reclaim disk space** without checking the snapshot first. Those files are the conversations; everything else is just a pointer to them.
- **Do not read identifiers out of the interface and pass them around.** Take them from the script's output.
