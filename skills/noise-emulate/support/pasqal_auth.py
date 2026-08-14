"""Pasqal Cloud credentials — the one implementation.

Every support script that talks to the cloud imports this instead of carrying
its own loader. Each field is resolved independently, most trusted source first:

  1. Environment variables — PASQAL_USERNAME / PASQAL_PASSWORD /
     PASQAL_PROJECT_ID. The only mechanism that keeps the password off disk;
     use it on shared machines and in SLURM scripts.
  2. System keyring (password only) — OS-encrypted, needs `pip install keyring`.
  3. ~/.pasqal_credentials.json — plaintext password, warned about.
  4. Interactive prompt — only when stdin is a terminal.

Per-field resolution matters: exporting PASQAL_PASSWORD to override a stale
password in the credentials file has to work, and it would not if the file were
consulted as an all-or-nothing block.

This module never hardcodes a password and never writes one to disk.

This file is vendored byte-identical into each skill's `support/` directory, so
a skill keeps working when installed or copied on its own. Edit one copy and
`scripts/check_manifests.py` fails until the others match.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

CRED_FILE = Path.home() / ".pasqal_credentials.json"
KEYRING_SERVICE = "pasqal-cloud"
FIELDS = ("username", "password", "project_id")


def _keyring_get(key: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, key)
    except Exception:
        return None


def _keyring_set(key: str, value: str) -> bool:
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, key, value)
        return True
    except Exception:
        return False


def _read_cred_file() -> dict:
    if not CRED_FILE.exists():
        return {}
    if CRED_FILE.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):
        print(f"⚠  {CRED_FILE} is readable by others — run: chmod 600 {CRED_FILE}")
    return json.loads(CRED_FILE.read_text())


def _save_non_secret(username: str, project_id: str) -> None:
    """Persist everything except the password, so it need not be retyped."""
    CRED_FILE.write_text(json.dumps(
        {"username": username, "project_id": project_id}, indent=2))
    CRED_FILE.chmod(0o600)
    print(f"  Username and project ID saved → {CRED_FILE}")


def _interactive_setup() -> dict:
    """One-time setup at a terminal. The password goes to the keyring or nowhere."""
    import getpass

    print()
    print("=" * 62)
    print("  Pasqal Cloud credentials not found.")
    print("  (One-time setup — the password will NOT be written to disk)")
    print("=" * 62)
    print()
    username   = input("  Pasqal Cloud username (email): ").strip()
    project_id = input("  Pasqal Cloud project ID:       ").strip()
    password   = getpass.getpass("  Pasqal Cloud password (hidden): ").strip()

    if _keyring_set("password", password):
        print("\n  Password saved to the system keyring (OS-encrypted).")
        _save_non_secret(username, project_id)
    else:
        print("\n  ⚠  System keyring unavailable. Password NOT saved to disk.")
        print("  Add this to your shell profile (or your SLURM script):")
        print()
        print(f'    export PASQAL_USERNAME="{username}"')
        print('    export PASQAL_PASSWORD="<your_password>"')
        print(f'    export PASQAL_PROJECT_ID="{project_id}"')
        print()
        print("  To keep it out of your shell history:")
        print("    read -rs -p 'Password: ' PASQAL_PASSWORD && export PASQAL_PASSWORD")
        print()
        _save_non_secret(username, project_id)

    return {"username": username, "password": password, "project_id": project_id}


def load_credentials() -> dict:
    """Return the keyword arguments for a cloud connection.

    Keys are exactly `username`, `password`, `project_id`, `region`, so the
    result can be splatted straight into either client:

        sdk  = SDK(**load_credentials())
        conn = PasqalCloud(**load_credentials())

    `region=None` selects the default (`fr`). SA1 lives in `sa` and is
    invisible from any other region — set PASQAL_REGION=sa or `"region": "sa"`
    in the credentials file.
    """
    from_file = _read_cred_file()
    creds = {f: os.environ.get(f"PASQAL_{f.upper()}") or None for f in FIELDS}

    if not creds["password"]:
        creds["password"] = _keyring_get("password")

    from_file_used = [f for f in FIELDS if not creds[f] and from_file.get(f)]
    for field in from_file_used:
        creds[field] = from_file[field]
    if "password" in from_file_used:
        print(f"⚠  the password in {CRED_FILE} is plaintext — move it to the "
              "system keyring, or use the PASQAL_PASSWORD environment variable.")

    if not all(creds.values()):
        if sys.stdin.isatty():
            creds = _interactive_setup()
        else:
            missing = ", ".join(f"PASQAL_{f.upper()}" for f in FIELDS if not creds[f])
            raise SystemExit(
                f"✘ Pasqal Cloud credentials incomplete — missing: {missing}\n"
                "  Either export those environment variables, or run this "
                "script from a terminal to set up the system keyring, or "
                f"create {CRED_FILE} (chmod 600) with:\n"
                '    {"username": "...", "password": "...", "project_id": "..."}')

    creds["region"] = os.environ.get("PASQAL_REGION") or from_file.get("region")
    return creds
