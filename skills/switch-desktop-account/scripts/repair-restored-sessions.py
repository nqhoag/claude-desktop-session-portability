#!/usr/bin/env python3
"""Move Claude Desktop sessions into a new account, and repair what a claude://resume restore drops.

A deep-link restore rebuilds each session record from its CLI transcript. Two things
do not survive that:

  worktrees  The record loses its worktree link, and the app's worktree store still
             names the OLD account's session id as the worktree's owner. On start the
             app refuses to reattach, tries a fresh checkout of the same branch, and git
             stops it: "This session's branch is checked out in another folder".
  groups     Sidebar groups and pins are stored per account, keyed by session id, and
             the id changes on restore.

Usage:
  repair-restored-sessions.py status                           # which switch step you are on, and the next action
  repair-restored-sessions.py scan [--since DAYS] [--all] [--mine]
                                                               # hidden sessions (or, with --mine, this account's)
  repair-restored-sessions.py plan <cliSessionId>...           # step 1: write the plan file
  repair-restored-sessions.py apply                            # step 3: macOS Terminal.app only; quits and reopens the app
  repair-restored-sessions.py worktrees --dry-run [--account KEY] [<cliSessionId>...]
  repair-restored-sessions.py worktrees [--account KEY] [<cliSessionId>...]   # Claude Desktop must be quit
  repair-restored-sessions.py groups                           # read-only map for the sidebar tools

With no ids, `worktrees` covers every restored session whose old record had a worktree.
--account defaults to the signed-in account (the one whose store was written last).
"""
import datetime
import json
import os
import shutil
import sys

from desktop_session_store import (BACKUP_ROOT, WT_STORE, app_running, current_account, lease_state,
                                   load_records, load_worktree_store, pairs, parse_args, session_ids_by_cli,
                                   sidebar_place, sidebar_prefs, worktree_entries, write_json)
import switch_account_steps

# cwd too: a restore takes it from the transcript's first turns, which can name a folder since moved.
FIELDS = ["cwd", "worktreePath", "worktreeName", "sourceBranch", "branch", "originCwd",
          "gitAnchors", "writtenBranches", "prs"]


def cmd_worktrees(args):
    opts = parse_args(args, values=("--account",), flags=("--dry-run",))
    dry, account, wanted = opts.get("--dry-run", False), opts.get("--account"), opts["positional"]
    targets = [p for p in pairs(account) if p[2][2].get("worktreePath") and (not wanted or p[0] in wanted)]
    missing = set(wanted) - {p[0] for p in targets}
    if missing:
        sys.exit(f"No restored session with an old worktree for: {', '.join(sorted(missing))}. Nothing changed.")
    if not targets:
        print("No restored session needs a worktree repair.")
        return
    if not dry and app_running():
        sys.exit("Claude Desktop is still running; it would overwrite these files. Quit it first. Nothing changed.")

    store = load_worktree_store()
    ids = session_ids_by_cli()
    plan = []
    for cli, (new_path, _, new_rec), (_, _, old_rec) in targets:
        wt = old_rec["worktreePath"]
        print(f"\n{new_rec.get('title')}  [{cli}]")
        if not os.path.isdir(wt):
            print(f"  SKIP: worktree folder is gone: {wt}")
            continue
        entries = worktree_entries(store, wt)
        lease = lease_state(entries, new_rec["sessionId"], ids.get(cli, set()) - {new_rec["sessionId"]})
        if lease == "blocked":
            print(f"  SKIP: worktree store has {len(entries)} entries for it, or another session owns it")
            continue
        if new_rec.get("worktreePath") == wt and lease == "owned":
            # The app refreshes git anchors once it reattaches; copying the old ones back would undo that.
            print("  already repaired")
            continue
        patched = dict(new_rec)
        for key in FIELDS:
            if key in old_rec:
                patched[key] = old_rec[key]
        patched.pop("priorErrorMark", None)  # stale start failure from the detached state
        changed = patched != new_rec
        for key in FIELDS + ["priorErrorMark"]:
            before, after = new_rec.get(key, "<missing>"), patched.get(key, "<missing>")
            if before != after:
                print(f"  {key}: {json.dumps(before, ensure_ascii=False)[:70]} -> {json.dumps(after, ensure_ascii=False)[:70]}")
        if lease == "claimable":
            print(f"  worktree owner: {entries[0].get('leasedBy')} -> {new_rec['sessionId']}")
            entries[0]["leasedBy"] = new_rec["sessionId"]
            entries[0].pop("leaseCleared", None)  # a live lease carries no leaseCleared key
            changed = True
        if not changed:
            print("  already repaired")
            continue
        plan.append((new_path, patched))

    if not plan:
        print("\nNothing to change.")
        return
    if dry:
        print(f"\nDry run: {len(plan)} session(s) would change; nothing written.")
        return
    bdir = os.path.join(BACKUP_ROOT, "record-backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bdir, exist_ok=True)
    shutil.copy2(WT_STORE, bdir)
    for new_path, patched in plan:
        shutil.copy2(new_path, bdir)
        write_json(new_path, patched)
    write_json(WT_STORE, store)  # unchanged entries are rewritten as read
    print(f"\nRepaired {len(plan)} session(s). Backup of every file touched: {bdir}")
    print(f"Undo: cp '{bdir}'/local_*.json into their account folder, and '{bdir}/git-worktrees.json' to '{WT_STORE}'")


def cmd_scan(args):
    """Sessions hidden from the signed-in account (or, with --mine, its own), with their sidebar place."""
    opts = parse_args(args, values=("--since",), flags=("--all", "--mine"))
    if not opts.get("--since", "0").isdigit():
        sys.exit("--since takes a whole number of days.")
    days, include_archived, mine = int(opts.get("--since", "0")), opts.get("--all", False), opts.get("--mine", False)
    if opts["positional"]:
        sys.exit(f"scan takes no ids: {' '.join(opts['positional'])}")
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp() * 1000 if days else 0
    prefs = sidebar_prefs()
    cur = current_account()
    by_cli = {}
    for _, acct, rec in load_records():
        if rec.get("cliSessionId"):
            by_cli.setdefault(rec["cliSessionId"], []).append((acct, rec))
    rows = []
    for cli, recs in by_cli.items():
        own = [r for r in recs if r[0] == cur]
        if mine != bool(own):
            continue
        acct, rec = max(own or recs, key=lambda r: r[1].get("lastActivityAt") or 0)
        ts = rec.get("lastActivityAt") or 0
        if ts < cutoff or (rec.get("isArchived") and not include_archived):
            continue
        group, pin = sidebar_place(prefs, acct, rec["sessionId"])
        wt = rec.get("worktreePath")
        rows.append((ts, cli, datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M"),
                     "archived" if rec.get("isArchived") else "active", group, pin,
                     "-" if not wt else ("worktree" if os.path.isdir(wt) else "worktree-gone"),
                     acct.split("/")[0][:8], rec.get("title") or "(untitled)"))
    # ACCOUNT matters for `plan`, which takes sessions from one account only.
    print("CLI SESSION ID\tLAST ACTIVITY\tSTATE\tGROUP\tPIN\tWORKTREE\tACCOUNT\tTITLE")
    for r in sorted(rows, reverse=True):
        print("\t".join(r[1:]))


def cmd_groups(args):
    parse_args(args)
    prefs = sidebar_prefs()
    rows = []
    for _, (_, new_acct, new_rec), (_, old_acct, old_rec) in pairs():
        group, pin = sidebar_place(prefs, old_acct, old_rec["sessionId"])
        rows.append((group, pin, new_rec["sessionId"], "archived" if new_rec.get("isArchived") else "active",
                     new_rec.get("title") or "(untitled)"))
    print("GROUP\tPIN\tNEW SESSION ID\tSTATE\tTITLE")
    for r in sorted(rows):
        print("\t".join(r))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"scan": cmd_scan, "worktrees": cmd_worktrees, "groups": cmd_groups,
     "status": switch_account_steps.cmd_status, "plan": switch_account_steps.cmd_plan,
     "apply": lambda a: switch_account_steps.cmd_apply(a, cmd_worktrees),
     }.get(cmd, lambda _a: sys.exit(__doc__))(sys.argv[2:])
