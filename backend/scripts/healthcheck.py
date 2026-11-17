"""Container health check: exit 0 if GET /health answers 200, else 1.

Used by docker-compose.yml (`python -m scripts.healthcheck`). A module instead of an
inline `python -c "..."` keeps the command free of spaces and quotes, which some
container engines (e.g. Podman) split differently.
"""

import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
