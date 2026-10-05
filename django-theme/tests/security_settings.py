"""Synthetic file-backed DB; override path for parallel integration runs."""
import os
from pathlib import Path

from config.security_settings import *  # noqa: F403

DATABASES["default"]["TEST"] = {"NAME": os.environ.get("NOVA_SECURITY_TEST_DB", str(Path(__file__).resolve().parent / "security-test.sqlite3"))}  # noqa: F405
