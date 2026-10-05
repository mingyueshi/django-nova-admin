#!/usr/bin/env bash
# PYTHON selects the controller, not all matrix interpreters.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$SCRIPT_DIR/test-matrix.py" "$@"
