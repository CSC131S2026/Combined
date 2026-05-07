import base64
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from core import email_config


class FakeKeyring:
    def __init__(self):
        self.passwords = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password


class EmailConfigContractTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.tmpdir.name) / ".coi_dashboard"
        self.config_file = self.config_dir / "email_config.json"
        self.keyring = FakeKeyring()
        self.patches = [
            mock.patch.object(email_config, "_CONFIG_DIR", self.config_dir),
            mock.patch.object(email_config, "_CONFIG_FILE", self.config_file),
            mock.patch.object(email_config, "keyring", self.keyring),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmpdir.cleanup()

    def test_save_stores_password_in_keyring_not_metadata_json(self):
        config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "sender_email": "sender@example.com",
            "sender_password": "app-password",
        }

        email_config.save(config)

        metadata = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(metadata["smtp_host"], "smtp.example.com")
        self.assertEqual(metadata["smtp_port"], 587)
        self.assertEqual(metadata["sender_email"], "sender@example.com")
        self.assertNotIn("sender_password", metadata)
        self.assertEqual(
            self.keyring.passwords[
                (email_config._KEYRING_SERVICE, "sender@example.com")
            ],
            "app-password",
        )
        self.assertEqual(
            stat.S_IMODE(self.config_file.stat().st_mode),
            stat.S_IRUSR | stat.S_IWUSR,
        )

    def test_load_combines_metadata_with_keyring_password(self):
        email_config.save({
            "smtp_host": "smtp.example.com",
            "smtp_port": "465",
            "sender_email": "sender@example.com",
            "sender_password": "app-password",
        })

        loaded = email_config.load()

        self.assertEqual(loaded, {
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "sender_email": "sender@example.com",
            "sender_password": "app-password",
        })

    def test_load_accepts_legacy_base64_password_when_keyring_missing(self):
        self.config_dir.mkdir(parents=True)
        legacy_password = base64.b64encode(b"legacy-password").decode("ascii")
        self.config_file.write_text(
            json.dumps({
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "sender_email": "sender@example.com",
                "sender_password": legacy_password,
            }),
            encoding="utf-8",
        )

        with mock.patch.object(email_config, "keyring", None):
            loaded = email_config.load()

        self.assertEqual(loaded["sender_password"], "legacy-password")

    def test_save_fails_without_keyring_instead_of_writing_password_to_json(self):
        with mock.patch.object(email_config, "keyring", None):
            with self.assertRaises(RuntimeError):
                email_config.save({
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "sender_email": "sender@example.com",
                    "sender_password": "app-password",
                })

        self.assertFalse(self.config_file.exists())


if __name__ == "__main__":
    unittest.main()
