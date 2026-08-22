---
name: list-desktop-sessions
description: Use to show what Claude Desktop sessions exist on this machine — active ones, or all of them including archived. Triggers on "list my sessions", "liệt kê session", "session nào đang mở", "show all sessions", "session đã archive", "what sessions do I have", "how many sessions", "find my session about X", "session cũ tên gì". Sees every account on the machine, not just the one signed in, so it also reveals sessions hidden by an account switch.
---

# List Claude Desktop sessions

Show the sessions on this machine — including ones the app is not currently displaying.

## Why not just look in the app

The app lists the sessions of whoever is signed in. Anything belonging to another account on the same machine is invisible there, and archived sessions are put away. This gives the complete picture in one place.

## Steps

1. **Pick the scope.** If the user did not say, ask — the two answers differ a lot in size and in what they are useful for.

   | Scope | Shows | Use when |
   |---|---|---|
   | Active | Sessions still in play | Day-to-day: "what am I working on", finding something to resume |
   | All | Active plus archived | Auditing, hunting for something old, before an account switch or machine move |

   Default to active if the user wants a quick answer and does not care.

2. **Run it.**

   ```bash
   ~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh list --active
   ~/.claude/skills/backup-desktop-session/scripts/ccd-sessions.sh list --all
   ```

   Each row gives the identifier, state, last activity, git branch, and title. The listing is sorted newest first.

3. **Summarise rather than dumping.** These lists run to dozens of rows. Lead with the counts, then show only what the user is actually after — the most recent handful, or the ones matching what they described. Offer the full table if they want it.

   Call out anything notable:

   - **Sessions spanning more than one account** — they have switched accounts before and have work currently hidden from the app. Point them at `resume-backedup-desktop`.
   - **A large archived count** relative to active, when the user is about to switch accounts or machines — it changes what they should back up.

## Following on

| The user then wants to | Skill |
|---|---|
| Snapshot this before switching account or machine | `backup-desktop-session` |
| Open one of these, or bring back a hidden one | `resume-backedup-desktop` |

## Do not

- **Do not treat the app's own session list as authoritative** when the user asks what exists. It is scoped to one account.
- **Do not paste identifiers into chat as the primary answer.** Titles, branches and timestamps are what the user recognises; identifiers are for the script to consume.
