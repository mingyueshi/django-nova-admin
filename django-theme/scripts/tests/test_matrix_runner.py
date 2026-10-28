"""Runner safety/orchestration checks; no downloads or virtualenv installs."""
import ast
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("matrix_runner", ROOT / "scripts/test-matrix.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "source"
        for directory in ("src/nova_admin", "demo/config", "tests"):
            (self.source / directory).mkdir(parents=True)
        (self.source / "src/nova_admin/__init__.py").write_text('__version__ = "0.5.1"\n')
        (self.source / "demo/config/settings.py").write_text("# fixture\n")
        (self.source / "tests/__init__.py").write_text("")
        (self.source / "pyproject.toml").write_text('[project]\nname="nova-django-admin-theme"\nversion="0.5.1"\n')
        self.wheel = self.base / "nova_django_admin_theme-0.5.1-py3-none-any.whl"
        self.write_wheel("0.5.1")
        self.manifest = runner.load_manifest(ROOT / "scripts/test-matrix.json")

    def write_wheel(self, version):
        with zipfile.ZipFile(self.wheel, "w") as archive:
            archive.writestr(f"nova_django_admin_theme-{version}.dist-info/METADATA",
                             f"Name: nova-django-admin-theme\nVersion: {version}\n")

    def arguments(self, *extra):
        return ["--source", str(self.source), "--root", str(self.base / "run"),
                "--wheel", str(self.wheel), *extra]

    def invoke(self, *extra):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return runner.main(self.arguments(*extra))

    def test_manifest_is_exact_eight_cells_not_cartesian_product(self):
        self.assertEqual([runner.cell_id(cell) for cell in self.manifest["cells"]], [
            "3.10.20/5.2.17", "3.11.17/5.2.17", "3.12.15/5.2.17", "3.12.15/6.0.8",
            "3.12.15/6.1.1", "3.13.16/6.1.1", "3.14.8/5.2.17", "3.14.8/6.1.1"])
        self.assertEqual(self.manifest["core"]["beautifulsoup4"], "4.15.0")

    def test_mapping_precedence_cli_file_environment(self):
        mapping = self.base / "map.json"
        mapping.write_text('{"3.11.17":"/file/python"}')
        with patch.dict(os.environ, {"NOVA_MATRIX_PYTHONS": '{"3.11.17":"/env/python","3.14.8":"/keep/python"}'}):
            actual = runner.parse_mapping(["3.11.17=/cli/python"], mapping)
        self.assertEqual(actual, {"3.11.17": "/cli/python", "3.14.8": "/keep/python"})

    def test_mapping_rejects_non_exact_versions_and_relative_executables(self):
        for value in ("3.11=/absolute/python", "3.11.17=python3", "3.11.17"):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
                runner.parse_mapping([value])

    def test_exact_mismatch_fails_before_creating_root(self):
        with patch.object(runner, "probe_interpreters", side_effect=ValueError("Wrong Python")):
            self.assertEqual(self.invoke(), 2)
        self.assertFalse((self.base / "run").exists())

    def test_probe_checks_actual_micro_version(self):
        executable = Path(os.__file__).parent / "does-not-matter"
        response = subprocess.CompletedProcess([], 0, '{"version":"3.11.16","implementation":"CPython"}', "")
        with patch.object(Path, "is_file", return_value=True), patch.object(os, "access", return_value=True), \
                patch.object(subprocess, "run", return_value=response), self.assertRaisesRegex(ValueError, "Expected CPython 3.11.17"):
            runner.probe_interpreters([{"python": "3.11.17"}], {"3.11.17": str(executable)})

    def test_missing_runtime_mapping_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Missing Python"):
            runner.probe_interpreters(self.manifest["cells"], {})

    def test_refuses_existing_run_directory_even_when_empty(self):
        target = self.base / "run"
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            runner.verify_inputs(self.source, target, self.wheel, ["source", "wheel"])

    def test_refuses_run_directory_in_checkout(self):
        with self.assertRaisesRegex(ValueError, "separate directory trees"):
            runner.verify_inputs(self.source, self.source / "artifacts", self.wheel, ["source"])

    def test_wheel_version_mismatch_is_rejected(self):
        self.write_wheel("0.5.0")
        with self.assertRaisesRegex(ValueError, "name/version"):
            runner.verify_inputs(self.source, self.base / "run", self.wheel, ["wheel"])

    def test_database_and_bytecode_not_copied_to_harness(self):
        (self.source / "demo/db.sqlite3").write_text("must not copy")
        (self.source / "tests/captcha-test.sqlite3-wal").write_text("must not copy")
        (self.source / "tests/test_case.py").write_text("# copied test")
        target = self.base / "harness"
        runner.copy_harness(self.source, target)
        self.assertFalse((target / "demo/db.sqlite3").exists())
        self.assertFalse((target / "tests/captcha-test.sqlite3-wal").exists())
        self.assertTrue((target / "tests/test_case.py").is_file())
        self.assertFalse((target / "src").exists())

    def test_settings_override_both_demo_database_names(self):
        for profile in ("core", "captcha"):
            with self.subTest(profile=profile):
                text = runner.settings_text(profile, self.base / "only-this-test.sqlite3")
                database = ast.literal_eval(ast.parse(text).body[1].value)["default"]
                self.assertEqual(database["NAME"], ":memory:")
                if profile == "captcha":
                    self.assertEqual(database["TEST"]["NAME"], str(self.base / "only-this-test.sqlite3"))
                else:
                    self.assertNotIn("TEST", database)

    def test_environment_drops_inherited_pip_python_django_configuration(self):
        with patch.dict(os.environ, {"PYTHONPATH": "/unsafe", "PIP_EXTRA_INDEX_URL": "https://unsafe.invalid", "PIP_CONFIG_FILE": "/unsafe", "DJANGO_SETTINGS_MODULE": "config.settings", "VIRTUAL_ENV": "/old/venv", "PATH": "/bin"}, clear=True):
            env = runner.clean_environment()
        self.assertNotIn("PIP_EXTRA_INDEX_URL", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("DJANGO_SETTINGS_MODULE", env)
        self.assertNotIn("VIRTUAL_ENV", env)
        self.assertEqual(env["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(env["PATH"], "/bin")

    def test_install_is_pinned_binary_no_dependencies_with_predictable_report(self):
        args = SimpleNamespace(no_index=False, find_links=[])
        command = runner.pip_install_command(Path("/env/bin/python"), Path("/run/pip-report.json"), ["Django==6.1.1"], args, Path("/cache"))
        self.assertEqual(command[:5], ["/env/bin/python", "-I", "-B", "-m", "pip"])
        self.assertIn("--no-deps", command)
        self.assertIn("--only-binary=:all:", command)
        self.assertEqual(command[command.index("--index-url") + 1], "https://pypi.org/simple")
        self.assertEqual(command[command.index("--report") + 1], "/run/pip-report.json")
        self.assertEqual(command[-1], "Django==6.1.1")

    def test_offline_command_has_no_index_and_requires_wheelhouse(self):
        args = SimpleNamespace(no_index=True, find_links=[Path("/wheelhouse")])
        command = runner.pip_install_command(Path("/env/python"), Path("/report"), [], args, Path("/cache"))
        self.assertIn("--no-index", command)
        self.assertNotIn("--index-url", command)
        self.assertIn("/wheelhouse", command)
        self.assertEqual(self.invoke("--no-index"), 2)
        self.assertFalse((self.base / "run").exists())

    def test_preflight_has_no_filesystem_or_install_side_effects(self):
        with patch.object(runner, "probe_interpreters", return_value={}), patch.object(runner, "run_variant") as variant:
            self.assertEqual(self.invoke("--preflight"), 0)
            variant.assert_not_called()
        self.assertFalse((self.base / "run").exists())

    def test_orchestration_selects_32_distinct_variants_in_serial_order(self):
        def successful_variant(*args):
            result = {"status": "passed"}
            args[-1](result)
            return result
        with patch.object(runner, "probe_interpreters", return_value={}), \
                patch.object(runner, "run_variant", side_effect=successful_variant) as variant:
            self.assertEqual(self.invoke("--with-captcha"), 0)
        calls = [call.args[:3] for call in variant.call_args_list]
        self.assertEqual(len(calls), 32)
        self.assertEqual(calls[:4], [(self.manifest["cells"][0], p, m)
                                     for p in ("core", "captcha") for m in ("source", "wheel")])
        report = runner.read_json(self.base / "run/results.json")
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["full_core_matrix"])

    def test_subset_failure_is_reported_and_other_selected_variants_continue(self):
        outcomes = iter(("failed", "passed"))
        def selected_variant(*args):
            result = {"status": next(outcomes)}
            args[-1](result)
            return result
        with patch.object(runner, "probe_interpreters", return_value={}), \
                patch.object(runner, "run_variant", side_effect=selected_variant) as variant:
            self.assertEqual(self.invoke("--cell", "3.11.17/5.2.17"), 1)
        self.assertEqual(variant.call_count, 2)
        report = runner.read_json(self.base / "run/results.json")
        self.assertFalse(report["full_core_matrix"])
        self.assertEqual(report["status"], "failed")

    def test_unknown_cell_is_rejected_before_any_runtime_work(self):
        with patch.object(runner, "probe_interpreters") as probe:
            self.assertEqual(self.invoke("--cell", "3.11.17/6.1.1"), 2)
            probe.assert_not_called()

    def test_copy_harness_error_finalizes_existing_aggregate(self):
        with patch.object(runner, "probe_interpreters", return_value={}), \
                patch.object(runner, "copy_harness", side_effect=OSError("copy fixture failed")):
            self.assertEqual(self.invoke(), 2)
        report = runner.read_json(self.base / "run/results.json")
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["error"], "OSError: copy fixture failed")
        self.assertTrue(report["finished_at"])
        self.assertEqual(report["results"], [])

    def test_worker_copy_error_finalizes_existing_aggregate(self):
        with patch.object(runner, "probe_interpreters", return_value={}), \
                patch.object(runner, "copy_harness"), \
                patch.object(runner.shutil, "copyfile", side_effect=OSError("worker fixture failed")):
            self.assertEqual(self.invoke(), 2)
        report = runner.read_json(self.base / "run/results.json")
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["error"], "OSError: worker fixture failed")
        self.assertTrue(report["finished_at"])

    def test_variant_log_io_error_retains_active_context_and_steps(self):
        original_open = Path.open
        def fail_log(path, *args, **kwargs):
            if path.name == "venv.log":
                raise OSError("log fixture failed")
            return original_open(path, *args, **kwargs)
        verified = {"3.11.17": {"requested_path": "/fixture/python"}}
        with patch.object(runner, "probe_interpreters", return_value=verified), \
                patch.object(Path, "open", fail_log), patch.object(subprocess, "run") as launch:
            self.assertEqual(self.invoke("--cell", "3.11.17/5.2.17"), 2)
            launch.assert_not_called()
        report = runner.read_json(self.base / "run/results.json")
        self.assertEqual(report["status"], "error")
        self.assertTrue(report["finished_at"])
        self.assertEqual(len(report["results"]), 1)
        variant = report["results"][0]
        self.assertEqual(variant["status"], "error")
        self.assertEqual(variant["expected"]["python"], "3.11.17")
        self.assertEqual(variant["steps"]["venv"]["status"], "error")
        self.assertIsNone(variant["steps"]["venv"]["exit_code"])
        self.assertEqual(variant["not_run"], list(runner.STEPS[1:]))
        self.assertEqual(runner.read_json(Path(variant["directory"]) / "result.json"), variant)

    def test_ctrl_c_retains_active_variant_and_successful_previous_step(self):
        verified = {"3.11.17": {"requested_path": "/fixture/python"}}
        with patch.object(runner, "probe_interpreters", return_value=verified), \
                patch.object(subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0), KeyboardInterrupt()]):
            self.assertEqual(self.invoke("--cell", "3.11.17/5.2.17"), 130)
        report = runner.read_json(self.base / "run/results.json")
        self.assertEqual(report["status"], "interrupted")
        self.assertEqual(report["error"], "Interrupted by user")
        self.assertTrue(report["finished_at"])
        self.assertEqual(len(report["results"]), 1)
        variant = report["results"][0]
        self.assertEqual(variant["status"], "interrupted")
        self.assertEqual(variant["finished_at"], report["finished_at"])
        self.assertEqual(variant["expected"]["mode"], "source")
        self.assertEqual(variant["steps"]["venv"]["status"], "passed")
        self.assertEqual(variant["steps"]["venv"]["exit_code"], 0)
        self.assertEqual(variant["steps"]["install"]["status"], "interrupted")
        self.assertIsNone(variant["steps"]["install"]["exit_code"])
        self.assertEqual(variant["not_run"], list(runner.STEPS[2:]))
        self.assertEqual(runner.read_json(Path(variant["directory"]) / "result.json"), variant)

    def test_ctrl_c_during_initialization_also_finalizes_aggregate(self):
        with patch.object(runner, "probe_interpreters", return_value={}), \
                patch.object(runner, "copy_harness", side_effect=KeyboardInterrupt()):
            self.assertEqual(self.invoke(), 130)
        report = runner.read_json(self.base / "run/results.json")
        self.assertEqual(report["status"], "interrupted")
        self.assertTrue(report["finished_at"])
        self.assertEqual(report["results"], [])

    def test_preflight_interruption_creates_no_report(self):
        with patch.object(runner, "probe_interpreters", side_effect=KeyboardInterrupt()):
            self.assertEqual(self.invoke(), 130)
        self.assertFalse((self.base / "run").exists())

    def test_rejected_existing_root_never_overwrites_another_report(self):
        root = self.base / "run"
        root.mkdir()
        path = root / "results.json"
        path.write_text('{"unrelated":"preserve exactly"}')
        self.assertEqual(self.invoke(), 2)
        self.assertEqual(path.read_text(), '{"unrelated":"preserve exactly"}')


if __name__ == "__main__":
    unittest.main(verbosity=2)
