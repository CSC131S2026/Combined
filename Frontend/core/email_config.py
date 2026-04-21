"""
Persistent SMTP configuration for the Sacramento County CoI Dashboard.

Settings are stored in:
    ~/.coi_dashboard/email_config.json

WARNING: The sender_password field is base64-encoded, NOT encrypted.
This is purely cosmetic obfuscation to prevent casual plaintext exposure
in the config file.  Anyone with read access to the file can trivially
decode it.  For real security, use a secrets manager or OS keychain.
"""

import base64
import json
from pathlib import Path


# --------------------------------------------------------------------------
# Config file location
# --------------------------------------------------------------------------

_CONFIG_DIR  = Path.home() / ".coi_dashboard"
_CONFIG_FILE = _CONFIG_DIR / "email_config.json"

# Keys present in a valid config dict
_REQUIRED_KEYS = {"smtp_host", "smtp_port", "sender_email", "sender_password"}


# --------------------------------------------------------------------------
# Public helpers
# --------------------------------------------------------------------------

def config_exists() -> bool:
    """Return True if the config file exists and contains the required keys."""
    if not _CONFIG_FILE.is_file():
        return False
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return _REQUIRED_KEYS.issubset(data.keys())
    except Exception:
        return False


def load() -> dict:
    """
    Load SMTP settings from disk.

    Returns
    -------
    dict with keys:
        smtp_host      (str)
        smtp_port      (int)
        sender_email   (str)
        sender_password (str)  — decoded from base64 obfuscation

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

    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed email config JSON: {exc}") from exc

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Email config missing keys: {missing}")

    # Decode obfuscated password
    raw_pw = data.get("sender_password", "")
    try:
        decoded_pw = base64.b64decode(raw_pw.encode()).decode("utf-8")
    except Exception:
        # Fall back to raw value if it was stored without encoding
        decoded_pw = raw_pw

    return {
        "smtp_host":       data["smtp_host"],
        "smtp_port":       int(data["smtp_port"]),
        "sender_email":    data["sender_email"],
        "sender_password": decoded_pw,
    }


def save(config: dict) -> None:
    """
    Persist SMTP settings to disk.

    The ``sender_password`` value will be base64-encoded before writing.
    This is NOT encryption — see module docstring.

    Parameters
    ----------
    config : dict
        Must contain: smtp_host, smtp_port, sender_email, sender_password
    """
    missing = _REQUIRED_KEYS - config.keys()
    if missing:
        raise ValueError(f"Config dict missing keys: {missing}")

    # Obfuscate password with base64
    raw_pw     = config["sender_password"]
    encoded_pw = base64.b64encode(raw_pw.encode("utf-8")).decode("ascii")

    payload = {
        "smtp_host":       config["smtp_host"],
        "smtp_port":       int(config["smtp_port"]),
        "sender_email":    config["sender_email"],
        "sender_password": encoded_pw,
        "_note": (
            "sender_password is base64-encoded, NOT encrypted. "
            "This is cosmetic obfuscation only."
        ),
    }

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
