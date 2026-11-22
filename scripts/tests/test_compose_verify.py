"""Exercise the Compose verifier's timeout without Docker or a Django installation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.compose import verify


class ComposeVerifyTests(unittest.TestCase):
    def test_stalled_test_process_times_out_and_cleans_up_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manage = root / "django-theme" / "demo" / "manage.py"
            manage.parent.mkdir(parents=True)
            manage.write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
            with (
                patch.object(verify, "__file__", str(root / "examples" / "compose" / "verify.py")),
                patch.object(verify, "TEST_TIMEOUT_SECONDS", 0.2),
                patch.object(verify.sys, "argv", ["verify.py"]),
                patch.object(tempfile, "tempdir", temporary),
                self.assertRaisesRegex(SystemExit, r"timed out after 0\.2 seconds\."),
            ):
                verify.main()
            self.assertEqual(list(root.glob("nova-compose-tests-*")), [])
