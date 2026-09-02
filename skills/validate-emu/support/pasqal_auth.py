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

**A resolved project is not a chosen project.** Finding credentials on the
machine says nothing about which project should pay for this run, and a project
id left in an environment variable is the last thing someone happened to export,
not a decision. Scripts that spend credits therefore call
`load_credentials(project_id=..., require_explicit_project=True)` and refuse to
run until someone names the project. `python pasqal_auth.py --whoami` is the
free, read-only way to show the user what is on the machine and what their
projects hold before they choose.

This module never hardcodes a password and never writes one to disk, and neither
--whoami nor any summary it prints ever contains a password or a token.

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

# Credits live in the billing API, which the SDK does not wrap. Same host split
# as pasqal_cloud.endpoints: SA1 is invisible from the default region.
BILLING_URL = {
    "sa": "https://apis.sa.pasqal.cloud/billing",
    None: "https://apis.pasqal.cloud/billing",
}


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


def credential_sources() -> dict:
    """Where each field would come from, without resolving the password itself.

    What --whoami shows the user before they confirm: an agent that says "found
    credentials" has told them nothing, while "username from the environment,
    password from the system keyring" is something they can recognise or deny.
    """
    from_file = _read_cred_file()
    sources = {}
    for f in FIELDS:
        if os.environ.get(f"PASQAL_{f.upper()}"):
            sources[f] = f"environment (PASQAL_{f.upper()})"
        elif f == "password" and _keyring_get("password"):
            sources[f] = "system keyring"
        elif from_file.get(f):
            sources[f] = str(CRED_FILE) + (
                " — plaintext password, move it to the keyring"
                if f == "password" else "")
        else:
            sources[f] = "not found"
    return sources


def load_credentials(project_id: str | None = None,
                     require_explicit_project: bool = False) -> dict:
    """Return the keyword arguments for a cloud connection.

    Keys are exactly `username`, `password`, `project_id`, `region`, so the
    result can be splatted straight into either client:

        sdk  = SDK(**load_credentials())
        conn = PasqalCloud(**load_credentials())

    `region=None` selects the default (`fr`). SA1 lives in `sa` and is
    invisible from any other region — set PASQAL_REGION=sa or `"region": "sa"`
    in the credentials file.

    `project_id` overrides whatever the machine resolved: it carries a choice the
    user made in the conversation. With `require_explicit_project=True` — what
    every script that spends credits passes — its absence is a hard stop, because
    the alternative is billing a project nobody picked.
    """
    if require_explicit_project and not project_id:
        raise SystemExit(
            "✘ no project was chosen, and the environment's project id is not a "
            "choice.\n"
            "  Show the user what is on this machine and what their projects "
            "hold:\n"
            f"      python {Path(__file__).name} --whoami\n"
            "  Then re-run this script with --project-id <the id they picked>.")

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

    if project_id:
        creds["project_id"] = project_id

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


# ── Projects and credits ──────────────────────────────────────────────────────

def fetch_credits(sdk, project_id: str, region: str | None = None) -> dict:
    """Remaining credits per backend type, or the reason there are none to show.

    The billing API is not wrapped by the SDK, so this is a plain GET with the
    SDK's own bearer token. Every failure degrades to a string: a credit balance
    is context for a decision, never a precondition for one, and an agent that
    stops because billing returned 403 has turned a nicety into an outage.
    """
    import urllib.error
    import urllib.request

    token = None
    try:
        token = sdk.user_token()
    except Exception:
        pass
    if not token:
        return {"error": "no token available from this SDK version"}

    base = BILLING_URL.get(region, BILLING_URL[None])
    out: dict = {}
    for backend in ("QPU", "EMU"):
        url = (f"{base}/api/v1/contracts/{project_id}/credit-pools"
               f"?backend_type={backend}&limit=100")
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                pools = json.loads(resp.read()).get("data") or []
            out[backend] = sum(p.get("remaining_credits") or 0 for p in pools)
        except urllib.error.HTTPError as e:
            out[backend] = f"unavailable (HTTP {e.code})"
        except Exception as e:                       # network, JSON, schema drift
            out[backend] = f"unavailable ({type(e).__name__})"
    return out


def list_projects(sdk) -> list[dict]:
    """The projects this user is actually a member of, id and name."""
    try:
        return [{"id": p.id, "name": p.name} for p in sdk.get_all_projects()]
    except Exception as e:
        print(f"⚠  could not list projects ({type(e).__name__}: {e})")
        return []


def account_summary(sdk, project_id: str, region: str | None = None,
                    username: str | None = None) -> str:
    """The account block that goes into a plan the user is asked to approve.

    A cost is meaningless without whose credits pay it. This is the difference
    between "300 shots, confirm?" and "300 shots, on <project>, which has 4200
    QPU credits left, as <user>" — the second is a question someone can answer.
    """
    names = {p["id"]: p["name"] for p in list_projects(sdk)}
    credits = fetch_credits(sdk, project_id, region)
    lines = [
        f"  account           {username or '(unknown user)'}",
        f"  project           {names.get(project_id, '(name unavailable)')}  "
        f"[{project_id}]",
        f"  region            {region or 'fr (default)'}",
    ]
    if "error" in credits:
        lines.append(f"  credits left      unavailable — {credits['error']}")
    else:
        lines.append("  credits left      " + ",  ".join(
            f"{k}: {v}" for k, v in credits.items()))
    return "\n".join(lines)


def print_whoami(as_json: bool = False) -> None:
    """Read-only: what is on this machine, and what the user's projects hold.

    Costs nothing, submits nothing, and is the step that has to happen before a
    project is picked. Prints no password and no token, in either format.
    """
    sources = credential_sources()
    creds   = load_credentials()
    region  = creds.get("region")
    env_pid = creds.get("project_id")

    sdk = None
    try:
        from pasqal_cloud import SDK
        sdk = SDK(**creds)
    except Exception as e:
        print(f"⚠  could not open a cloud session ({type(e).__name__}: {e})")

    projects = list_projects(sdk) if sdk else []
    for p in projects:
        p["credits"] = fetch_credits(sdk, p["id"], region) if sdk else {}

    if as_json:
        print(json.dumps({
            "username": creds["username"], "region": region or "fr",
            "sources": sources,
            "environment_project_id": env_pid,
            "projects": projects,
        }, indent=2, default=str))
        return

    print("=== Pasqal Cloud account — nothing has been submitted ===")
    print(f"  username   {creds['username']}")
    print(f"  region     {region or 'fr (default)'}")
    print("  resolved from:")
    for field, src in sources.items():
        print(f"    {field:<11} {src}")
    print()
    if not projects:
        print("  No project list available. Ask the user for the project id to "
              "use, and pass it as --project-id.")
    else:
        print(f"  {len(projects)} project(s) available to this account:")
        for p in projects:
            cr = p.get("credits") or {}
            shown = ("credits unavailable" if "error" in cr else
                     ",  ".join(f"{k}: {v}" for k, v in cr.items()))
            mark = "  ← the environment's default, NOT a choice" if (
                p["id"] == env_pid) else ""
            print(f"    {p['name']}")
            print(f"      id       {p['id']}{mark}")
            print(f"      {shown}")
    print()
    print("  Ask the user which project should pay for this run, then pass it as")
    print("  --project-id <id>. Do not infer it from the environment.")


# ── Self-check ────────────────────────────────────────────────────────────────

def _self_test() -> None:
    """Asserts on the parts that must hold offline. No network, no credentials."""
    try:
        load_credentials(require_explicit_project=True)
    except SystemExit as e:
        assert "--whoami" in str(e), str(e)
    else:
        raise AssertionError("a missing project must be refused, not defaulted")

    class _FakeSDK:
        def user_token(self):
            raise RuntimeError("no session")

        def get_all_projects(self):
            raise RuntimeError("no session")

    assert "error" in fetch_credits(_FakeSDK(), "pid"), "must degrade, not raise"
    assert list_projects(_FakeSDK()) == [], "must degrade to an empty list"
    summary = account_summary(_FakeSDK(), "pid-1", None, "user@example.com")
    assert "pid-1" in summary and "unavailable" in summary, summary
    assert BILLING_URL["sa"] != BILLING_URL[None], "SA1 needs its own host"
    print("pasqal_auth self-test OK")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Show the Pasqal Cloud account, projects and credits on this "
                    "machine. Read-only: submits nothing, spends nothing.")
    ap.add_argument("--whoami", action="store_true",
                    help="print credential sources, projects and credits")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable output for --whoami")
    ap.add_argument("--self-test", action="store_true",
                    help="offline asserts on the refusal and degradation paths")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
    elif args.whoami or args.json:
        print_whoami(as_json=args.json)
    else:
        ap.print_help()
