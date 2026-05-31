-- ============================================================
-- Seed: Default Settings
-- ============================================================
-- Usage: sqlite3 ../../data/config.db < seed_settings.sql
-- ============================================================

-- Safety settings
INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_read_only', 'true');
INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_max_rows', '1000');
