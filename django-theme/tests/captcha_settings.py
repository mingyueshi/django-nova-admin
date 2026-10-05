"""File-backed synthetic SQLite DB permits real concurrent connection tests."""
import os
from pathlib import Path
from config.captcha_settings import *  # noqa: F403

# Separate from the demo DB; Django creates and destroys this test-only file.
# Override the path when running several matrices in parallel.
DATABASES["default"]["TEST"] = {"NAME": os.environ.get("NOVA_CAPTCHA_TEST_DB", str(Path(__file__).resolve().parent / "captcha-test.sqlite3"))}  # noqa: F405
