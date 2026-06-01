import sys
files = [
    "/Users/chendong/Projects/agentic-data-analyst/backend/tests/test_auth_service.py",
    "/Users/chendong/Projects/agentic-data-analyst/backend/tests/test_auth_api.py",
    "/Users/chendong/Projects/agentic-data-analyst/backend/tests/test_admin_stats_api.py",
    "/Users/chendong/Projects/agentic-data-analyst/backend/tests/test_persistence_schema.py",
    "/Users/chendong/Projects/agentic-data-analyst/backend/tests/test_persistence_token.py",
    "/Users/chendong/Projects/agentic-data-analyst/backend/tests/test_admin_config_service.py",
]
for fp in files:
    with open(fp) as f:
        content = f.read()
    print(f"{'='*60}")
    print(f"FILE: {fp.split('/')[-1]}")
    print(f"{'='*60}")
    print(content)
