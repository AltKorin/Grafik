#!/usr/bin/env python3
"""Klient wspólnego OpenProject działający jako codex, bez sekretów w repo."""
import importlib.util
from pathlib import Path
import sys


def client():
    source = Path.home() / "Claude/OpenProject/op.py"
    spec = importlib.util.spec_from_file_location("shared_openproject", source)
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    op.TOKEN = (Path.home() / ".config/openproject/codex.token").read_text().strip()
    return op


def main():
    op = client()
    command, *args = sys.argv[1:] or ["todo", "grafik"]
    if command == "whoami":
        user = op.check(*op.api("GET", "/users/me"))
        print(user["id"], user["login"], user["name"])
    elif command == "todo":
        op.todo(*args)
    elif command == "show":
        wp = op.check(*op.api("GET", f"/work_packages/{int(args[0])}"))
        print(f"#{wp['id']} [{wp['_links']['status']['title']}] {wp['subject']}\n\n{wp['description']['raw']}")
    elif command == "add":
        op.add(*(a for a in args if a != "--czeka"), waiting="--czeka" in args)
    elif command == "move":
        op.move(*args)
    elif command == "comment":
        op.check(*op.api("POST", f"/work_packages/{int(args[0])}/activities", {"comment": {"raw": args[1]}}))
        print(f"#{args[0]}: komentarz dodany")
    else:
        raise SystemExit("Użycie: openproject.py whoami | todo <projekt> | show <id> | add <projekt> <tytuł> [opis] [--czeka] | move <id> <status> | comment <id> <tekst>")


if __name__ == "__main__":
    main()
