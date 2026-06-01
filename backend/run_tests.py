import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "-x", "-v",
     "tests/test_prompt_api.py",
     "tests/test_routes_config.py"],
    capture_output=True, text=True, cwd="/Users/chendong/Projects/agentic-data-analyst/backend"
)
print(result.stdout)
print(result.stderr)
print(f"Exit code: {result.returncode}")
