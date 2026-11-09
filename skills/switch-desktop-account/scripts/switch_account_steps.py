"""The four steps of a Claude Desktop account switch, and which one the user is on.

  Step 1  Claude Desktop: the skill picks sessions, `plan` writes the plan file
  Step 2  the user signs out and signs in to the new account (by hand)
  Step 3  macOS Terminal.app: `apply` restores, quits the app, repairs worktrees, reopens it
  Step 4  Claude Desktop, new account: the skill rebuilds groups and pins (sidebar tools)

`status` reads the plan file and the app's store and names the current step and its next
action, so no step runs twice or out of order. User-facing text is Vietnamese.
"""
import datetime
import glob
import json
import os
import subprocess
import sys
import time

from desktop_session_store import (APP_ID, BACKUP_ROOT, STORE, app_running, current_account, lease_state,
                                   load_records, load_worktree_store, pairs, parse_args, session_ids_by_cli,
                                   sidebar_place, sidebar_prefs, worktree_entries, write_json)

PLAN = os.path.join(BACKUP_ROOT, "switch-plan.json")
APPLY_CMD = "python3 ~/.claude/skills/switch-desktop-account/scripts/repair-restored-sessions.py apply"
ARRIVE_TIMEOUT = 30  # seconds for the app to write the restored record after a deep link
OPEN_TIMEOUT = 60
QUIT_TIMEOUT = 60
SETTLE_SECONDS = 10  # a freshly opened app drops deep links until the account has loaded
GIVE_UP_AFTER = 2  # consecutive misses with nothing arrived: the app is on the wrong account

STEPS = """Các bước đổi account:
  Bước 1  Trong Claude Desktop: skill chọn session cần chuyển, ghi file kế hoạch.
  Bước 2  Bạn tự đăng xuất, rồi đăng nhập account mới.
  Bước 3  Trong Terminal.app của macOS: chạy lệnh apply.
  Bước 4  Trong Claude Desktop, account mới: skill dựng lại group và pin."""

WRONG_ACCOUNT = ("Không session nào về account mới.\n"
                 "Nguyên nhân thường gặp: Claude Desktop vẫn đăng nhập account cũ.\n"
                 "Làm Bước 2 (đăng nhập account mới), rồi chạy lại lệnh này. Script chưa sửa file nào.")


def load_plan():
    if not os.path.exists(PLAN):
        return None
    with open(PLAN, encoding="utf-8") as fh:
        return json.load(fh)


def restored_record(entry):
    """(account, record) of this session in an account that did not have it at plan time, or None.

    A deep-link restore always names the file local_<cliSessionId>.json, so a glob is enough;
    reading every record on each poll would load tens of MB.
    """
    hits = []
    for path in glob.glob(os.path.join(STORE, "*", "*", f"local_{entry['cli']}.json")):
        acct = os.path.relpath(os.path.dirname(path), STORE)
        if acct in entry["known_accounts"]:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:
            continue  # the app may be mid-write; the next poll reads it
        if rec.get("cliSessionId") == entry["cli"]:
            hits.append((acct, rec))
    return max(hits, key=lambda h: h[1].get("createdAt") or 0) if hits else None


def wait_for(probe, timeout):
    """Polls probe() once a second; returns its first truthy result, or None after the timeout."""
    deadline = time.time() + timeout
    while True:
        result = probe()
        if result or time.time() >= deadline:
            return result or None
        time.sleep(1)


def launched_from_claude_app():
    """True when Claude Desktop started this process: quitting the app would kill this run."""
    if os.environ.get("__CFBundleIdentifier") == APP_ID:
        return True
    pid = os.getppid()
    while pid > 1:
        out = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(pid)],
                             capture_output=True, text=True).stdout.strip()
        if not out:
            return False
        ppid, _, comm = out.partition(" ")
        if "/Claude.app/" in comm:
            return True
        pid = int(ppid)
    return False


def cmd_plan(args):
    clis = list(dict.fromkeys(parse_args(args)["positional"]))
    if not clis:
        sys.exit("Cần ít nhất một CLI SESSION ID, lấy ở cột đầu của lệnh scan. Chưa ghi gì.")
    by_cli = {}
    for _, acct, rec in load_records():
        if rec.get("cliSessionId") in clis:
            by_cli.setdefault(rec["cliSessionId"], []).append((acct, rec))
    unknown = [c for c in clis if c not in by_cli]
    if unknown:
        sys.exit(f"Không tìm thấy session: {', '.join(unknown)}. Lấy id từ lệnh scan. Chưa ghi gì.")
    prefs = sidebar_prefs()
    cur = current_account()
    sessions, sources = [], set()
    for cli in clis:
        # Step 1 runs in the account being left; planning after the switch falls back to the newest use.
        own = [r for r in by_cli[cli] if r[0] == cur]
        acct, rec = max(own or by_cli[cli], key=lambda r: r[1].get("lastActivityAt") or 0)
        sources.add(acct)
        group, pin = sidebar_place(prefs, acct, rec["sessionId"])
        sessions.append({"cli": cli, "title": rec.get("title") or "(untitled)", "group": group, "pin": pin,
                         "worktree": rec.get("worktreePath"), "archived": bool(rec.get("isArchived")),
                         "known_accounts": sorted({a for a, _ in by_cli[cli]})})
    if len(sources) > 1:
        sys.exit(f"Các session thuộc {len(sources)} account khác nhau (cột ACCOUNT của scan). "
                 "Mỗi kế hoạch chỉ chuyển từ một account. Chưa ghi gì.")
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    if os.path.exists(PLAN):
        kept = PLAN[:-5] + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
        os.replace(PLAN, kept)
        print(f"Kế hoạch cũ được giữ lại tại: {kept}")
    write_json(PLAN, {"version": 1, "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                      "source_account": sources.pop(), "sessions": sessions})
    print(f"Đã ghi kế hoạch chuyển {len(sessions)} session tại: {PLAN}\n")
    cmd_status([])


def session_state(entry, hit, wt_store, prefs, ids):
    """Where one planned session stands, given the record the restore wrote (hit) or None."""
    if not hit:
        return {"arrived": False}
    acct, rec = hit
    wt = entry["worktree"]
    if not wt:
        wt_state = "-"
    elif not os.path.isdir(wt):
        wt_state = "thư mục đã mất"
    else:
        lease = lease_state(worktree_entries(wt_store, wt), rec["sessionId"],
                            ids.get(entry["cli"], set()) - {rec["sessionId"]})
        if lease == "blocked":
            wt_state = "không sửa được"  # another session holds it; apply skips it rather than loop
        elif lease == "owned" and rec.get("worktreePath") == wt:
            wt_state = "xong"
        else:
            wt_state = "chưa sửa"
    group, pin = sidebar_place(prefs, acct, rec["sessionId"])
    return {"arrived": True, "session_id": rec["sessionId"], "worktree": wt_state,
            "group_ok": entry["group"] == "-" or group == entry["group"],
            "pin_ok": entry["pin"] == "-" or pin == "pin",
            # Restores were seen arriving archived although the original was not.
            "archive_ok": entry["archived"] or not rec.get("isArchived")}


def cmd_status(args):
    parse_args(args)
    print(STEPS + "\n")
    plan = load_plan()
    if not plan:
        print("Bạn đang ở: Bước 1. Chưa có file kế hoạch.")
        print("Việc tiếp theo: chọn session cần chuyển. Skill /switch-desktop-account làm việc này:")
        print("  - Chưa đổi account: chọn trong các session của account đang đăng nhập.")
        print("  - Đã đăng nhập account mới rồi: chọn trong các session đang ẩn. Sau đó bỏ qua Bước 2.")
        return
    wt_store, prefs, ids = load_worktree_store(), sidebar_prefs(), session_ids_by_cli()
    states = [(e, session_state(e, restored_record(e), wt_store, prefs, ids)) for e in plan["sessions"]]
    mark = lambda ok: "xong" if ok else "chưa"
    print(f"Kế hoạch tạo lúc {plan['created_at']}, {len(states)} session:")
    print("VỀ ACCOUNT MỚI\tWORKTREE\tGROUP\tPIN\tARCHIVE\tSESSION ID MỚI\tTITLE")
    for e, s in states:
        group = "-" if e["group"] == "-" else f"{e['group']} ({mark(s.get('group_ok'))})"
        pin = "-" if e["pin"] == "-" else f"pin ({mark(s.get('pin_ok'))})"
        archive = "cần bỏ archive" if s["arrived"] and not s["archive_ok"] else "-"
        print("\t".join(["có" if s["arrived"] else "chưa", s.get("worktree", "-"), group, pin, archive,
                         s.get("session_id", "-"), e["title"][:60]]))
    print()
    not_arrived = sum(not s["arrived"] for _, s in states)
    wt_left = sum(s.get("worktree") == "chưa sửa" for _, s in states)
    sidebar_left = sum(s["arrived"] and not (s["group_ok"] and s["pin_ok"] and s["archive_ok"]) for _, s in states)
    if not_arrived == len(states) and current_account() == plan["source_account"]:
        print("Bạn đang ở: Bước 2. Kế hoạch đã có, Claude Desktop vẫn đăng nhập account cũ.")
        print("Việc tiếp theo:")
        print("  1. Đăng xuất Claude Desktop, rồi đăng nhập account mới. Đã đăng nhập account mới rồi thì bỏ qua mục này.")
        print("  2. Mở Terminal.app của macOS. Không dùng terminal bên trong Claude Desktop.")
        print(f"  3. Chạy: {APPLY_CMD}")
    elif not_arrived or wt_left:
        print(f"Bạn đang ở: Bước 3. Còn {not_arrived} session chưa về, {wt_left} worktree chưa sửa.")
        print(f"Việc tiếp theo: mở Terminal.app của macOS và chạy: {APPLY_CMD}")
        print("Lệnh bỏ qua phần đã làm, chạy lại nhiều lần không sao.")
    elif sidebar_left:
        print(f"Bạn đang ở: Bước 4. Còn {sidebar_left} session chưa đúng group, pin hoặc archive.")
        print("Việc tiếp theo: skill dùng công cụ sidebar để sửa các ô 'chưa' và 'cần bỏ archive' trong bảng trên.")
    else:
        print("Xong cả 4 bước. Gửi một tin vào mỗi session có worktree để kiểm session chạy được.")
    blocked = sum(s.get("worktree") == "không sửa được" for _, s in states)
    if blocked:
        print(f"Lưu ý: {blocked} worktree đang do session khác giữ, script không sửa. Session đó chạy ở thư mục repo.")


def deep_link(entry):
    """Opens the session in Claude Desktop and waits for its record; resends once, since the app drops some."""
    url = f"claude://resume?session={entry['cli']}"
    for _ in range(2):
        subprocess.run(["open", "-b", APP_ID, url])
        hit = wait_for(lambda: restored_record(entry), ARRIVE_TIMEOUT / 2)
        if hit:
            return hit
    return None


def cmd_apply(args, repair_worktrees):
    if args:
        sys.exit("apply không nhận tham số. Muốn xem trước, chạy status.")
    plan = load_plan()
    if not plan:
        sys.exit("Chưa có file kế hoạch. Làm Bước 1 trước: trong Claude Desktop, gõ /switch-desktop-account.")
    if launched_from_claude_app():
        sys.exit("Lệnh này tắt Claude Desktop, nên không chạy được từ terminal bên trong app.\n"
                 f"Mở Terminal.app của macOS (Cmd+Space, gõ Terminal), rồi chạy lại:\n  {APPLY_CMD}")
    print(f"Bước 3: chuyển {len(plan['sessions'])} session theo kế hoạch.")
    if not app_running():
        print("Mở Claude Desktop ...")
        subprocess.run(["open", "-b", APP_ID])
        if not wait_for(app_running, OPEN_TIMEOUT):
            sys.exit("Claude Desktop không mở lên. Mở app bằng tay, rồi chạy lại lệnh này. Script chưa sửa file nào.")
        time.sleep(SETTLE_SECONDS)

    found, missing = {}, []
    for entry in plan["sessions"]:
        hit = restored_record(entry)
        if hit:
            print(f"  đã về từ trước: {entry['title'][:60]}")
        else:
            print(f"  mở: {entry['title'][:60]}")
            hit = deep_link(entry)
            time.sleep(1)  # rapid bursts of deep links get dropped
        if hit:
            found[entry["cli"]] = hit  # reused below: a second read can land mid-write
            continue
        print(f"    chưa về sau {ARRIVE_TIMEOUT} giây")
        missing.append(entry)
        if not found and len(missing) >= GIVE_UP_AFTER:
            sys.exit("\n" + WRONG_ACCOUNT)
    if not found:
        sys.exit("\n" + WRONG_ACCOUNT)

    targets = {acct for acct, _ in found.values()}
    if len(targets) > 1:
        sys.exit(f"Session đã về {len(targets)} account khác nhau, script không biết account nào là account mới.\n"
                 "Chưa sửa worktree. Chạy status trong Claude Desktop để xem bảng.")
    target = targets.pop()
    has_old_worktree = {p[0] for p in pairs(target) if p[2][2].get("worktreePath")}
    wt_store, prefs, ids = load_worktree_store(), sidebar_prefs(), session_ids_by_cli()
    # Only unrepaired worktrees justify quitting the app; a re-run after a full repair skips the restart.
    wt_clis = [e["cli"] for e in plan["sessions"] if e["cli"] in found and e["cli"] in has_old_worktree
               and session_state(e, found[e["cli"]], wt_store, prefs, ids)["worktree"] == "chưa sửa"]
    if wt_clis:
        print("\nThoát Claude Desktop để sửa worktree ...")
        subprocess.run(["osascript", "-e", f'tell application id "{APP_ID}" to quit'])
        if not wait_for(lambda: not app_running(), QUIT_TIMEOUT):
            sys.exit(f"Claude Desktop chưa thoát sau {QUIT_TIMEOUT} giây. Bấm Cmd+Q trong app, rồi chạy lại lệnh này.\n"
                     "Session đã về sẽ được bỏ qua.")
        try:
            time.sleep(2)  # the app finishes writing its files after the process is gone
            repair_worktrees(["--account", target] + wt_clis)
        finally:
            print("\nMở lại Claude Desktop ...")
            if subprocess.run(["open", "-b", APP_ID]).returncode != 0:
                print("Không mở lại được Claude Desktop. Mở app bằng tay.")
    else:
        print("\nKhông có worktree cần sửa, không cần tắt app.")

    plan["applied_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    plan["missing"] = [e["cli"] for e in missing]
    write_json(PLAN, plan)
    if missing:
        print(f"\nCòn {len(missing)} session chưa về. Chạy lại lệnh này để thử lại:\n  {APPLY_CMD}")
        return
    print("\nBước 3 xong. Việc tiếp theo, Bước 4:")
    print("  1. Trong Claude Desktop, mở một session mới ở account mới.")
    print("  2. Gõ /switch-desktop-account. Skill sẽ dựng lại group và pin.")
    print("  3. Gửi một tin vào mỗi session có worktree để kiểm session chạy được.")
