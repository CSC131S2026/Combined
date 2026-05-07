"""
Persistent SMTP configuration for the Sacramento County CoI Dashboard.

Settings are stored in:
    ~/.coi_dashboard/email_config.json

The JSON file stores only non-secret SMTP metadata. The sender password is
stored in the user's OS keychain through the optional ``keyring`` package.
Legacy configs that still contain a base64-obfuscated ``sender_password`` can
be loaded for compatibility, but new saves never write that field to JSON.
"""

import base64
import json
import os
import stat
from pathlib import Path

try:
    import keyring
except Exception:  # pragma: no cover - exercised by patching in tests
    keyring = None


# --------------------------------------------------------------------------
# Config file location
# --------------------------------------------------------------------------

_CONFIG_DIR  = Path.home() / ".coi_dashboard"
_CONFIG_FILE = _CONFIG_DIR / "email_config.json"

# Keys present in metadata saved on disk.
_METADATA_KEYS = {"smtp_host", "smtp_port", "sender_email"}

# Keys required when callers save a full config dict.
_SAVE_REQUIRED_KEYS = _METADATA_KEYS | {"sender_password"}

_KEYRING_SERVICE = "coi_dashboard.smtp"
_CONFIG_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------


def _read_metadata() -> dict:
    """Read and validate the non-secret SMTP metadata JSON."""
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed email config JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Malformed email config JSON: expected an object")

    missing = _METADATA_KEYS - data.keys()
    if missing:
        raise ValueError(f"Email config missing keys: {missing}")

    return data


def _write_metadata(payload: dict) -> None:
    """Write metadata with owner-only file permissions."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(_CONFIG_DIR, stat.S_IRWXU)
    except OSError:
        pass

    fd = os.open(
        _CONFIG_FILE,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        _CONFIG_FILE_MODE,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.chmod(_CONFIG_FILE, _CONFIG_FILE_MODE)


def _get_keyring_password(sender_email: str) -> str | None:
    if keyring is None:
        return None

    try:
        return keyring.get_password(_KEYRING_SERVICE, sender_email)
    except Exception:
        return None


def _set_keyring_password(sender_email: str, password: str) -> None:
    if keyring is None:
        raise RuntimeError(
            "The keyring package is unavailable, so the email password "
            "cannot be stored securely."
        )

    try:
        keyring.set_password(_KEYRING_SERVICE, sender_email, password)
    except Exception as exc:
        raise RuntimeError(
            "The OS keychain rejected the email password. Install or configure "
            "a keyring backend, then try saving SMTP settings again."
        ) from exc


def _legacy_password(data: dict) -> str | None:
    raw_pw = data.get("sender_password")
    if raw_pw is None:
        return None

    try:
        return base64.b64decode(raw_pw.encode()).decode("utf-8")
    except Exception:
        return raw_pw


# --------------------------------------------------------------------------
# Public helpers
# --------------------------------------------------------------------------


def config_exists() -> bool:
    """Return True if the config file exists and contains SMTP metadata."""
    if not _CONFIG_FILE.is_file():
        return False

    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False

    return isinstance(data, dict) and _METADATA_KEYS.issubset(data.keys())


def load() -> dict:
    """
    Load SMTP settings from disk.

    Returns
    -------
    dict with keys:
        smtp_host      (str)
        smtp_port      (int)
        sender_email   (str)
        sender_password (str)  — read from OS keychain when available

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    ValueError
        If the file is missing required keys or is malformed.
    """
    if not _CONFIG_FILE.is_file():
        raise FileNotFoundError(
            f"Email config not found: {_CONFIG_FILE}\n"
            "Open the SMTP Settings panel in the Email dialog to create it."
        )

    data = _read_metadata()
    sender_email = data["sender_email"]
    password = _get_keyring_password(sender_email)
    if password is None:
        password = _legacy_password(data)
    if password is None:
        raise ValueError(
            "Email password not found in the OS keychain. Re-enter and save "
            "the SMTP app password."
        )

    return {
        "smtp_host":       data["smtp_host"],
        "smtp_port":       int(data["smtp_port"]),
        "sender_email":    sender_email,
        "sender_password": password,
    }


def save(config: dict) -> None:
    """
    Persist SMTP settings to disk.

    The ``sender_password`` value is stored in the OS keychain via keyring.
    The metadata JSON never contains the password and is written chmod 0600.

    Parameters
    ----------
    config : dict
        Must contain: smtp_host, smtp_port, sender_email, sender_password
    """
    missing = _SAVE_REQUIRED_KEYS - config.keys()
    if missing:
        raise ValueError(f"Config dict missing keys: {missing}")

    sender_email = config["sender_email"]
    _set_keyring_password(sender_email, config["sender_password"])

    payload = {
        "smtp_host":       config["smtp_host"],
        "smtp_port":       int(config["smtp_port"]),
        "sender_email":    sender_email,
        "_password_storage": "keyring",
        "_keyring_service": _KEYRING_SERVICE,
        "_note": (
            "sender_password is stored in the OS keychain and is not present "
            "in this metadata file."
        ),
    }

    _write_metadata(payload)
