-- ============================================================
-- Seed: Default Prompts
-- ============================================================
-- NOTE: This file only contains prompt names and version placeholders.
-- The actual prompt content is large and managed via Python scripts
-- (see ../reset_prompts.py) or the admin UI.
--
-- To reset prompts to factory defaults:
--   python ../reset_prompts.py
-- ============================================================

-- Ensure prompts table exists
CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL DEFAULT 'default',
    content    TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
