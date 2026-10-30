#!/usr/bin/env bash
# Locate the project safely even when its path contains spaces or another cwd is used.
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "${LOCAL_PYTHON:-}" ]]; then
    LOCAL_INTERPRETER="$LOCAL_PYTHON"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    LOCAL_INTERPRETER="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3.14 >/dev/null 2>&1; then
    LOCAL_INTERPRETER="$(command -v python3.14)"
else
    printf '%s\n' 'Python 3.14 is required. Install it on PATH, or set LOCAL_PYTHON to a prepared Python 3.14 environment.' >&2
    exit 1
fi

# exec preserves signals: Ctrl+C reaches the controller, which cleans up its children.
exec "$LOCAL_INTERPRETER" "$PROJECT_ROOT/scripts/local_runtime.py" "$@"
