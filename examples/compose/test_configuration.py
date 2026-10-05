"""Static isolation checks. Requires PyYAML; does not invoke Docker."""
from pathlib import Path
import unittest

import yaml

HERE = Path(__file__).resolve().parent


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = yaml.safe_load((HERE / "compose.yml").read_text())

    def test_only_web_port_is_published_on_ipv4_loopback(self):
        services = self.compose["services"]
        self.assertEqual(set(services), {"web", "db"})
        self.assertNotIn("ports", services["db"])
        self.assertEqual(services["web"]["ports"], ["127.0.0.1:${NOVA_LOCAL_PORT:-8000}:8000"])
        for service in services.values():
            self.assertNotIn("network_mode", service)
            self.assertNotIn("privileged", service)
            self.assertNotIn("container_name", service)

    def test_volume_and_network_names_remain_compose_project_scoped(self):
        self.assertEqual(self.compose["volumes"], {"postgres_data": None})
        self.assertEqual(self.compose["services"]["db"]["volumes"], ["postgres_data:/var/lib/postgresql/data"])
        self.assertNotIn("networks", self.compose)

    def test_secrets_are_file_injections_and_not_plain_environment_values(self):
        self.assertEqual(set(self.compose["secrets"]), {"postgres_password", "django_secret_key"})
        for secret in self.compose["secrets"].values():
            self.assertTrue(secret["file"].startswith("./.local/"))
        for service in self.compose["services"].values():
            environment = service.get("environment", {})
            self.assertNotIn("POSTGRES_PASSWORD", environment)
            self.assertNotIn("DJANGO_SECRET_KEY", environment)
            self.assertNotIn("POSTGRES_HOST_AUTH_METHOD", environment)
            self.assertNotIn("DJANGO_SUPERUSER_PASSWORD", environment)

    def test_healthy_database_gates_web_start_and_web_has_readiness_probe(self):
        web = self.compose["services"]["web"]
        self.assertEqual(web["depends_on"]["db"]["condition"], "service_healthy")
        self.assertIn("/_health/", " ".join(web["healthcheck"]["test"]))
        self.assertIn("pg_isready", " ".join(self.compose["services"]["db"]["healthcheck"]["test"]))

    def test_private_state_is_excluded_from_source_control_and_build_context(self):
        self.assertIn(".local/", (HERE / ".gitignore").read_text().splitlines())
        ignored = (HERE / "Dockerfile.dockerignore").read_text().splitlines()
        self.assertIn("**/.local", ignored)
        self.assertIn("**/.env", ignored)
        self.assertIn("**/*.sqlite3", ignored)
        dockerfile = (HERE / "Dockerfile").read_text()
        self.assertNotIn("ARG NOVA_POSTGRES_PASSWORD", dockerfile)
        self.assertNotIn("ARG DJANGO_SECRET_KEY", dockerfile)


if __name__ == "__main__":
    unittest.main(verbosity=2)
