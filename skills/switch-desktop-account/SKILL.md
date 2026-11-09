---
name: switch-desktop-account
description: Use when switching the Anthropic account signed into Claude Desktop, before signing out or migrating to a new Mac, or when sessions, sidebar groups or pins are missing after an account change. Triggers on "đổi account Claude Desktop", "switch Claude account", "backup my sessions", "sao lưu session", "restore my sessions", "khôi phục session", "mất session sau khi đổi account", "session không hiện trong app", "chuyển session sang account mới", "đồng bộ section 2 account", and on "This session's branch is checked out in another folder" after a restore.
---

# Switch Claude Desktop account

An account switch deletes nothing. The app lists only the signed-in account's sessions, groups and pins; everything else is still on disk. This skill moves the chosen sessions into the new account with their worktree, group and pin.

```bash
S=~/.claude/skills/switch-desktop-account/scripts
python3 $S/repair-restored-sessions.py <status|scan|plan|apply|worktrees|groups> ...
```

## The four steps

| Step | Where | Who | What |
|---|---|---|---|
| 1 | Claude Desktop, account being left | skill | choose sessions, `plan` writes the plan file |
| 2 | Claude Desktop | user | sign out, sign in to the new account |
| 3 | macOS Terminal.app | user runs `apply` | restore, quit app, repair worktrees, reopen |
| 4 | Claude Desktop, new account | skill | rebuild groups and pins |

## Always start with status

Before anything else, run `python3 $S/repair-restored-sessions.py status`. It reads the plan file and the app's store and prints "Bạn đang ở: Bước N" with the next action. Tell the user that step and its next action, then do only that step. Never run a step that `status` did not name; run `status` again after each step.

## Step 1: plan

The backup and the scan below are part of step 1, not separate steps.

1. Decide which account the sessions come from. The user's words usually say it ("tôi vừa đăng nhập account mới" = already switched). Unclear → ask that one question first.

   | Situation | Scan | After `plan` |
   |---|---|---|
   | Not switched yet | `scan --mine --since <days>` | Step 2, then step 3 |
   | Already signed in to the new account | `scan --since <days>` (hidden sessions) | Step 2 is skipped; straight to step 3 |

2. Not switched yet → run `bash $S/ccd-sessions.sh backup --all` as a safety copy. Moving to another Mac → also copy `~/.claude/projects/` and `~/.claude/session-backups/`.
3. Run the scan from the table, then again with `--all` for archived ones. Its GROUP and PIN columns are the sidebar place in the ACCOUNT shown.
4. Show the rows, summarised by group. Ask the user which sessions to move, one question. `plan` takes sessions from one ACCOUNT only; if the chosen rows span several, ask which account to move first.
5. Run `plan <cliSessionId>...` with ids from the scan's first column. It ends with `status` output; relay its next action with the exact `apply` command, then end the turn.

The user signs out and in themself. Never do it for them.

## Step 3: apply

The user runs the command `status` prints, in macOS Terminal.app. It refuses to run inside Claude Desktop, because it quits the app. Re-running is safe: done parts are skipped. If the user pastes its output, read it, then run `status`.

## Step 4: groups and pins

From a session in the new account, the `status` table is the only work list: its GROUP and PIN columns hold the target from the plan, marked "xong" or "chưa", next to each NEW SESSION ID. Ignore `groups` and `scan` here; they cover sessions outside the plan. For each "chưa": reuse groups from `list_groups`, `create_group` for missing names exactly as spelled, `move_sessions`, `set_pinned`. "cần bỏ archive" → `unarchive_session`. Run `status` until it prints "Xong cả 4 bước", then ask the user to send one message in each session with a worktree.

"không sửa được" in WORKTREE means another session holds that worktree. The session still runs, in the repository folder. Tell the user; do not force it.

Titles normally survive. Only a session with no title gets renamed from `bash $S/ccd-sessions.sh title-map <id>` with `set_session_title`.

## Why worktrees need repair

The deep link carries only the session id, so the app rebuilds the record from the transcript. The record loses its worktree path, and the app's worktree store still names the old account's session as owner. The app then tries a fresh checkout of the same branch, and git stops it. `apply` restores both while the app is quit and backs up every file it touches.

## Common mistakes

| Mistake | Result | Do instead |
|---|---|---|
| Skip `status` | Steps run twice or out of order | `status` first, every time |
| Run `apply` in the app's terminal | Refused: it would die with the app | macOS Terminal.app |
| Run `apply` before signing in to the new account | Stops after the first session; nothing changed | Step 2, then `apply` again |
| Copy ids from the app's interface | They do not resolve | Ids from `scan` output |
| Edit app files while the app runs | The app overwrites the edit | Only `apply` / `worktrees`, which check first |
| Switch back to an account that already has the sessions | Not handled yet: its sessions can hit the branch error | Tell the user; do not improvise a fix |

## Just looking

Use `list-desktop-sessions`.
