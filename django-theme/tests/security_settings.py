"""Each process owns a synthetic file-backed DB; explicit overrides remain supported."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from config.security_settings import *  # noqa: F403

_test_directory = TemporaryDirectory(prefix="nova-security-tests-")
DATABASES["default"]["TEST"] = {"NAME": os.environ.get("NOVA_SECURITY_TEST_DB", str(Path(_test_directory.name) / "security-test.sqlite3"))}  # noqa: F405
# Integration cases deliberately simulate independent remote connection IPs.
NOVA_DEMO_LOOPBACK_ONLY = False
