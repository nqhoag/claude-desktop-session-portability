"""Read and write Claude Desktop's local session store. Shared by the switch scripts."""
import glob
import json
import os
import subprocess
import sys

APP = os.path.expanduser("~/Library/Application Support/Claude")
APP_ID = "com.anthropic.claudefordesktop"
STORE = os.path.join(APP, "claude-code-sessions")
WT_STORE = os.path.join(APP, "git-worktrees.json")
CONFIG = os.path.join(APP, "claude_desktop_config.json")
BACKUP_ROOT = os.path.expanduser("~/.claude/session-backups")


def parse_args(args, values=(), flags=()):
    """{"positional": [...], "--flag": True, "--opt": "value"}. Exits on an unknown option or a missing value."""
    out, pos, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a in flags:
            out[a] = True
        elif a in values:
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                sys.exit(f"{a} needs a value. Nothing changed.")
            out[a] = args[i + 1]
            i += 1
        elif a.startswith("-"):
            sys.exit(f"Unknown option: {a}. Nothing changed.")
        else:
            pos.append(a)
        i += 1
    out["positional"] = pos
    return out


def load_records():
    """Yields (path, account_key, record) for every session record of every account."""
    for path in glob.glob(os.path.join(STORE, "*", "*", "local_*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:
            continue
        yield path, os.path.relpath(os.path.dirname(path), STORE), rec


def pairs(target=None):
    """Each restored record in the target account, with the record elsewhere that best describes it.

    The target defaults to the signed-in account. It must be explicit: a session switched back and
    forth has restored records in several accounts, and only the target's one is the restore to repair.
    The old side prefers a record that still has its worktree, since an unrepaired earlier restore is
    often the most recently active one.
    """
    target = target or current_account()
    by_cli = {}
    for path, acct, rec in load_records():
        cli = rec.get("cliSessionId")
        if cli:
            by_cli.setdefault(cli, []).append((path, acct, rec))
    out = []
    for cli, recs in by_cli.items():
        new = [r for r in recs if r[1] == target and r[2].get("sessionId") == f"local_{cli}"
               and r[2].get("fromCliTranscript")]
        old = [r for r in recs if r[1] != target]
        if len(new) == 1 and old:
            best = max(old, key=lambda r: (bool(r[2].get("worktreePath")), r[2].get("lastActivityAt") or 0))
            out.append((cli, new[0], best))
    return out


def app_running():
    probe = subprocess.run(["osascript", "-e", f'application id "{APP_ID}" is running'],
                           capture_output=True, text=True)
    # pgrep -x misses the main process; ask LaunchServices and fail closed.
    return probe.returncode != 0 or probe.stdout.strip() != "false"


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    with open(tmp, encoding="utf-8") as fh:
        json.load(fh)  # refuse to swap in an unreadable file
    os.replace(tmp, path)


def current_account():
    """The signed-in account is the one whose store was written to most recently; None for an empty store."""
    files = glob.glob(os.path.join(STORE, "*", "*", "local_*.json"))
    if not files:
        return None
    return os.path.relpath(os.path.dirname(max(files, key=os.path.getmtime)), STORE)


def sidebar_prefs():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            return json.load(fh).get("preferences", {}).get("epitaxyPrefs", {})
    except FileNotFoundError:
        return {}


def sidebar_place(prefs, acct, session_id):
    """(group name or "-", "pin" or "-") of a session in one account's sidebar."""
    scope = prefs.get("dframe-group-scopes", {}).get(acct, {})
    names = {g["id"]: g["name"] for g in scope.get("groups", [])}
    group = names.get(scope.get("assignments", {}).get(f"code:{session_id}"), "-")
    pin = "pin" if session_id in prefs.get("starred-local-code-sessions", []) else "-"
    return group, pin


def load_worktree_store():
    try:
        with open(WT_STORE, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def worktree_entries(store, path):
    return [e for e in store.get("worktrees", {}).values()
            if isinstance(e, dict) and os.path.normpath(e.get("path", "")) == os.path.normpath(path)]


def lease_state(entries, new_sid, old_sids):
    """owned: already the new session's. claimable: held by an old record of it, or released by the app
    (leasedBy null, leaseCleared true). blocked: no single entry, or another session holds it."""
    if len(entries) != 1:
        return "blocked"
    owner = entries[0].get("leasedBy")
    if owner == new_sid:
        return "owned"
    if owner is None or owner in old_sids:
        return "claimable"
    return "blocked"


def session_ids_by_cli():
    """{cliSessionId: {sessionId of each account's record}}, to know which leases a session already held."""
    out = {}
    for _, _, rec in load_records():
        if rec.get("cliSessionId") and rec.get("sessionId"):
            out.setdefault(rec["cliSessionId"], set()).add(rec["sessionId"])
    return out
