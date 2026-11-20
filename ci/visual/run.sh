#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
image=mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea
exec docker run --rm --platform linux/arm64 --ipc=host --network none -e NOVA_VISUAL_SCOPE -e NOVA_VISUAL_DEBUG -e PYTHONPATH=/work/output/visual/python -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/work" -w /work/ci/visual "$image" node node_modules/@playwright/test/cli.js test "$@"
