#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync each agent's SOUL.md into the `system_prompt` column of Octop's database.

WHY THIS EXISTS
    In Octop 1.0.2, a SOUL.md sitting in the agent's working directory does
    NOT automatically become the persona. The `prompt_files` entry in
    manifest.json is dashboard metadata only. The persona that actually takes
    effect lives in the `system_prompt` column of the `agents` table, applied
    when the manager reloads the agent.

    => After editing SOUL.md you must run this script AND reload, or your
       changes silently do nothing.

USAGE
    python scripts\\sync-persona.py              # sync every agent that has SOUL.md
    python scripts\\sync-persona.py --list       # show diff status, write nothing
    python scripts\\sync-persona.py 90ZHGP       # sync only the given agent(s)

ENV
    OCTOP_DB    override path to octop.db (default: ~/.octop/octop.db)
    OCTOP_AGENTS_DIR  override agents dir (default: ~/.octop/agents)

SAFETY
    Always stop the Octop service (or accept the risk of a dirty read) before
    writing, and back up octop.db first.
"""

import os
import sqlite3
import sys
import time

DB = os.environ.get("OCTOP_DB") or os.path.join(
    os.path.expanduser("~"), ".octop", "octop.db"
)
AGENTS_DIR = os.environ.get("OCTOP_AGENTS_DIR") or os.path.join(
    os.path.expanduser("~"), ".octop", "agents"
)


def discover():
    """Return [(agent_id, abs_path_to_soul_md), ...] for every agent with SOUL.md."""
    found = []
    if not os.path.isdir(AGENTS_DIR):
        return found
    for name in sorted(os.listdir(AGENTS_DIR)):
        p = os.path.join(AGENTS_DIR, name, "SOUL.md")
        if os.path.isfile(p):
            found.append((name, p))
    return found


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    list_only = "--list" in sys.argv

    if not os.path.exists(DB):
        print(f"[ERROR] database not found: {DB}")
        print("        Set OCTOP_DB or check your Octop data dir.")
        return 1

    all_agents = discover()
    if not all_agents:
        print(f"[ERROR] no SOUL.md found under: {AGENTS_DIR}")
        return 1

    if args:
        wanted = {a.upper() for a in args}
        targets = [(i, p) for i, p in all_agents if i.upper() in wanted]
        missing = wanted - {i.upper() for i, _ in targets}
        for m in missing:
            print(f"  [warn] agent {m} has no SOUL.md")
    else:
        targets = all_agents

    if not targets:
        return 1

    con = sqlite3.connect(DB)
    cur = con.cursor()
    now = int(time.time())
    reloaded = []

    for aid, soul in targets:
        text = open(soul, encoding="utf-8").read()
        cur.execute(
            "select length(system_prompt) from agents where agent_id=?", (aid,)
        )
        row = cur.fetchone()
        db_len = row[0] if row and row[0] else 0

        if list_only:
            flag = "OK  " if db_len == len(text) else "DIFF"
            print(f"  [{flag}] {aid}: file {len(text)} / db {db_len}")
            continue

        cur.execute(
            "update agents set system_prompt=?, updated_at=? where agent_id=?",
            (text, now, aid),
        )
        print(f"  [sync] {aid}: {len(text)} chars (was {db_len})")
        reloaded.append(aid)

    if not list_only:
        con.commit()
    con.close()

    if not list_only:
        print("\nDone. Reload each agent for changes to take effect:")
        for aid in reloaded:
            print(f"  octop agent reload {aid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
