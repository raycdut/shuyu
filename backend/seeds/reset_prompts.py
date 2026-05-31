"""Reset all prompt categories to factory defaults.

This script resets all 6 prompt categories (system, sql_gen, plan,
plan_reflect, report_reflect, schema_describe) to their default values.

Usage:
    python seeds/reset_prompts.py
    python seeds/reset_prompts.py --category plan   # reset a single category
    python seeds/reset_prompts.py --dry-run          # preview without writing
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


SEEDS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SEEDS_DIR.parent
DB_PATH = BACKEND_DIR / "data" / "config.db"

# Insert backend dir into sys.path so we can import app modules
sys.path.insert(0, str(BACKEND_DIR))

from app.persistence import PROMPT_DEFAULTS  # noqa: E402

PROMPT_CATEGORIES = ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"]


def _get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Make sure the backend server has been started at least once to initialize the database.")
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def get_current_versions(db: sqlite3.Connection) -> dict[str, int]:
    versions: dict[str, int] = {}
    for cat in PROMPT_CATEGORIES:
        row = db.execute(
            "SELECT MAX(version) FROM prompts WHERE name = ?", (cat,)
        ).fetchone()
        versions[cat] = row[0] if row and row[0] else 0
    return versions


def reset_prompts(db: sqlite3.Connection, category: str | None = None, dry_run: bool = False):
    targets = [category] if category else PROMPT_CATEGORIES
    versions = get_current_versions(db)
    now = time.time()

    for cat in targets:
        default_content = PROMPT_DEFAULTS.get(cat)
        if default_content is None:
            print(f"  Warning: No default content found for category '{cat}', skipping.")
            continue

        current_version = versions.get(cat, 0)
        new_version = current_version + 1
        preview = default_content[:80].replace("\n", " ") + "..."

        if dry_run:
            print(f"  [DRY-RUN] Would insert {cat} v{new_version} (current: v{current_version})")
            print(f"            Preview: {preview}")
            continue

        # Deactivate all existing active prompts for this category
        db.execute("UPDATE prompts SET is_active = 0 WHERE name = ? AND is_active = 1", (cat,))

        # Insert new version as the active one
        db.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
            (cat, default_content, new_version, now),
        )
        print(f"  Reset '{cat}' to v{new_version} (was v{current_version})")


def main():
    parser = argparse.ArgumentParser(description="Reset prompts to factory defaults")
    parser.add_argument("--category", choices=PROMPT_CATEGORIES, help="Reset only this category")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    db = _get_db()

    print("Resetting prompts to factory defaults...")
    reset_prompts(db, category=args.category, dry_run=args.dry_run)

    if not args.dry_run:
        db.commit()
        print("Done. Restart the backend server for changes to take effect.")
    else:
        print("\nDry-run complete. Run without --dry-run to apply changes.")
        db.close()


if __name__ == "__main__":
    main()
