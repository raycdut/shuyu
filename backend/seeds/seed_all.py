"""Run all seed scripts in sequence.

This script orchestrates:
1. Default settings (safety configuration)
2. Default prompts (factory reset)
3. Initial admin user creation (interactive)

Usage:
    python seeds/seed_all.py                          # run all non-interactive seeds
    python seeds/seed_all.py --with-admin              # include admin creation prompt
    python seeds/seed_all.py --dry-run                 # preview without writing
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


SEEDS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SEEDS_DIR.parent
DB_PATH = BACKEND_DIR / "data" / "config.db"

sys.path.insert(0, str(BACKEND_DIR))

from app.persistence import PROMPT_DEFAULTS  # noqa: E402

PROMPT_CATEGORIES = ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"]


def _get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Make sure the backend server has been started at least once to initialize the database.")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def seed_settings(db: sqlite3.Connection, dry_run: bool = False) -> int:
    count = 0
    settings = [
        ("safety_read_only", "true"),
        ("safety_max_rows", "1000"),
    ]
    for key, value in settings:
        exists = db.execute("SELECT COUNT(*) FROM settings WHERE key = ?", (key,)).fetchone()[0]
        if exists == 0:
            if not dry_run:
                db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            print(f"  Settings: {key} = {value}")
            count += 1
        else:
            print(f"  Settings: {key} already exists, skipped")
    return count


def seed_prompts(db: sqlite3.Connection, dry_run: bool = False) -> int:
    import time
    count = 0
    for name, content in PROMPT_DEFAULTS.items():
        exists = db.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = ?", (name,)
        ).fetchone()[0]
        if exists == 0:
            if not dry_run:
                max_ver = db.execute(
                    "SELECT MAX(version) FROM prompts WHERE name = ?", (name,)
                ).fetchone()[0] or 0
                db.execute(
                    "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (name, content, max_ver + 1, time.time()),
                )
            print(f"  Prompts: seeded '{name}'")
            count += 1
        else:
            print(f"  Prompts: '{name}' already exists, skipped")
    return count


def main():
    parser = argparse.ArgumentParser(description="Run all seed scripts")
    parser.add_argument("--with-admin", action="store_true", help="Also prompt for admin user creation")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    db = _get_db()

    print("=== Seed: Default Settings ===")
    seed_settings(db, dry_run=args.dry_run)

    print("\n=== Seed: Default Prompts ===")
    seed_prompts(db, dry_run=args.dry_run)

    print("\n=== Seed: Complete ===")
    if not args.dry_run:
        db.commit()
        print("All seeds applied successfully.")
    else:
        print("Dry-run complete. Run without --dry-run to apply changes.")

    db.close()

    if args.with_admin:
        print("\n=== Seed: Admin User ===")
        import subprocess
        subprocess.run([sys.executable, str(SEEDS_DIR / "create_admin.py")])


if __name__ == "__main__":
    main()
