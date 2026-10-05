"""Host-only verification; no Docker, network, dependencies or real secrets."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("compose_demo", Path(__file__).with_name("demo.py"))
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_keys_are_unique_private_and_reused(self):
        local = demo.prepare_local(self.root)
        initial = {name: (local / name).read_text() for name in ("postgres_password", "django_secret_key")}
        self.assertNotEqual(*initial.values())
        self.assertTrue(all(len(value.strip()) >= 64 for value in initial.values()))
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(local.stat().st_mode), 0o700)
            self.assertTrue(all(stat.S_IMODE((local / name).stat().st_mode) == 0o600 for name in initial))
        demo.prepare_local(self.root)
        self.assertEqual(initial, {name: (local / name).read_text() for name in initial})

    def test_invalid_key_is_never_replaced(self):
        local = demo.prepare_local(self.root)
        path = local / "postgres_password"
        path.write_text("invalid")
        with self.assertRaises(ValueError):
            demo.prepare_local(self.root)
        self.assertEqual(path.read_text(), "invalid")

    def test_missing_initialized_key_is_not_rotated(self):
        local = demo.prepare_local(self.root)
        (local / "options.json").write_text("{}")
        (local / "postgres_password").unlink()
        with self.assertRaises(ValueError):
            demo.prepare_local(self.root)
        self.assertFalse((local / "postgres_password").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_broad_secret_permissions_rejected(self):
        local = demo.prepare_local(self.root)
        (local / "django_secret_key").chmod(0o644)
        with self.assertRaises(ValueError):
            demo.prepare_local(self.root)

    def test_secret_symlinks_rejected(self):
        local = demo.prepare_local(self.root)
        target = local / "postgres_password"
        target.unlink()
        target.symlink_to(local / "django_secret_key")
        with self.assertRaises(ValueError):
            demo.prepare_local(self.root)

    def test_project_is_stable_but_checkout_scoped(self):
        self.assertEqual(demo.project_name(self.root), demo.project_name(self.root / "."))
        self.assertNotEqual(demo.project_name(self.root), demo.project_name(self.root / "other"))
        self.assertRegex(demo.project_name(self.root), r"^nova-local-[a-f0-9]{12}$")

    def test_missing_docker_does_not_generate_keys(self):
        with patch.object(demo, "HERE", self.root), patch.object(demo.shutil, "which", return_value=None), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                demo.main(["up"])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / ".local").exists())

    def test_up_persists_options_and_down_preserves_volumes(self):
        with patch.object(demo, "HERE", self.root), patch.object(demo.shutil, "which", return_value="/fake/docker"), patch.object(demo.subprocess, "run") as run, redirect_stdout(io.StringIO()) as output:
            demo.main(["up", "--captcha", "--port", "8123"])
            up = run.call_args
            self.assertIn("--wait", up.args[0])
            self.assertEqual(up.kwargs["env"]["NOVA_EXAMPLE_CAPTCHA"], "1")
            self.assertEqual(up.kwargs["env"]["NOVA_LOCAL_PORT"], "8123")
            demo.main(["down"])
            down = run.call_args
            self.assertEqual(down.args[0][-1], "down")
            self.assertNotIn("--volumes", down.args[0])
            self.assertEqual(down.kwargs["env"]["NOVA_EXAMPLE_CAPTCHA"], "1")
        for name in ("postgres_password", "django_secret_key"):
            self.assertNotIn((self.root / ".local" / name).read_text().strip(), output.getvalue())
        self.assertEqual(json.loads((self.root / ".local" / "options.json").read_text()), {"captcha": True, "port": 8123})

    def test_invalid_port_and_mutating_flags_on_down_rejected(self):
        for args in (["up", "--port", "0"], ["up", "--port", "65536"], ["down", "--captcha"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                demo.main(args)

    def test_external_compose_project_is_not_inherited(self):
        with patch.dict(os.environ, {"COMPOSE_FILE": "/unrelated.yml", "COMPOSE_PROJECT_NAME": "production"}):
            env = demo.compose_environment(False, 8000)
        self.assertNotIn("COMPOSE_FILE", env)
        self.assertNotIn("COMPOSE_PROJECT_NAME", env)

    def test_account_creation_is_only_an_explicit_interactive_step(self):
        with patch.object(demo, "HERE", self.root), patch.object(demo.shutil, "which", return_value="/fake/docker"), patch.object(demo.subprocess, "run") as run, redirect_stdout(io.StringIO()):
            demo.main(["up", "--create-superuser"])
        self.assertEqual(run.call_args.args[0][-5:], ["exec", "web", "python", "manage.py", "createsuperuser"])
        self.assertNotIn("--noinput", run.call_args.args[0])
        self.assertNotIn("DJANGO_SUPERUSER_PASSWORD", run.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
