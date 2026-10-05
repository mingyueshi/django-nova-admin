#!/usr/bin/env python3
"""Verify the delivered source files before making local edits; stdlib only."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
errors = []
for name, expected in manifest["files"].items():
    path = root / name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        errors.append(f"missing or unsafe: {name}")
        continue
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        errors.append(f"changed: {name}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"OK: {len(manifest['files'])} source and asset files match the delivery manifest")
print("Local edits after this check will intentionally change the hashes.")
