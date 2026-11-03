#!/usr/bin/env python3
"""Point Supabase auth email at Gmail or Resend, chosen by EMAIL_PROVIDER.

Supabase sends the invite and password-reset emails itself, through whatever SMTP server its
auth settings name, so the backend never reads any of this. The switch lives here instead:

    apply [--dry-run]   PATCH the production project's auth config through the Management API:
                        the chosen provider's SMTP settings, plus the invite and recovery
                        templates and subjects and the link expiry, read from supabase/config.toml
                        so the repo is the one copy of them.
    env                 Print `export SMTP_*=...` lines for the chosen provider, for the
                        env(SMTP_*) values in config.toml when sending real mail locally.

Settings come from supabase/.env (gitignored; see supabase/.env.example). A real environment
variable beats the file, so `EMAIL_PROVIDER=resend just smtp-apply` works without editing it.
Standard library only: nothing to install, and json.dumps escapes the HTML templates safely.
"""

import argparse
import json
import os
import shlex
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUPABASE_DIR = REPO_ROOT / "supabase"
ENV_FILE = SUPABASE_DIR / ".env"
CONFIG_FILE = SUPABASE_DIR / "config.toml"
MANAGEMENT_API = "https://api.supabase.com/v1/projects/{ref}/config/auth"
DEFAULT_SENDER_NAME = "NCA Worker Management"

# Each provider's SMTP settings, as (field, literal value or name of the variable holding it).
# Both use port 587 with STARTTLS. Gmail must send as the mailbox it signs in as; Resend signs in
# as the literal user "resend" with the API key as password, and sends from a verified domain.
PROVIDERS: dict[str, dict[str, tuple[str, str]]] = {
    "gmail": {
        "host": ("literal", "smtp.gmail.com"),
        "user": ("env", "GMAIL_SMTP_USER"),
        "pass": ("env", "GMAIL_APP_PASSWORD"),
        "admin_email": ("env", "GMAIL_SMTP_USER"),
    },
    "resend": {
        "host": ("literal", "smtp.resend.com"),
        "user": ("literal", "resend"),
        "pass": ("env", "RESEND_API_KEY"),
        "admin_email": ("env", "RESEND_SENDER_EMAIL"),
    },
}
SMTP_PORT = "587"


def load_env() -> dict[str, str]:
    """supabase/.env, overlaid with the real environment."""
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.removeprefix("export ").partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    values.update({k: v for k, v in os.environ.items() if v})
    return values


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def smtp_settings(env: dict[str, str]) -> tuple[str, dict[str, str]]:
    """The chosen provider's name and resolved SMTP settings. Exits naming anything missing."""
    provider = env.get("EMAIL_PROVIDER", "").lower()
    if provider not in PROVIDERS:
        fail(f"EMAIL_PROVIDER must be one of {', '.join(PROVIDERS)} (got {provider or 'nothing'}).")
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for field, (kind, value) in PROVIDERS[provider].items():
        if kind == "literal":
            resolved[field] = value
        elif env.get(value):
            resolved[field] = env[value]
        elif value not in missing:
            missing.append(value)
    if missing:
        fail(f"{provider} needs {', '.join(missing)} in {ENV_FILE.relative_to(REPO_ROOT)} or the environment.")
    resolved["port"] = SMTP_PORT
    resolved["sender_name"] = env.get("EMAIL_SENDER_NAME") or DEFAULT_SENDER_NAME
    return provider, resolved


def mailer_settings() -> dict[str, object]:
    """Templates, subjects and link expiry, read from config.toml rather than repeated here."""
    email = tomllib.loads(CONFIG_FILE.read_text())["auth"]["email"]
    settings: dict[str, object] = {"mailer_otp_exp": email["otp_expiry"]}
    for name, template in email.get("template", {}).items():
        # content_path is relative to the repo root, where the Supabase CLI runs.
        settings[f"mailer_subjects_{name}"] = template["subject"]
        settings[f"mailer_templates_{name}_content"] = (REPO_ROOT / template["content_path"]).read_text()
    return settings


def apply(env: dict[str, str], dry_run: bool) -> None:
    provider, smtp = smtp_settings(env)
    payload: dict[str, object] = {f"smtp_{field}": value for field, value in smtp.items()}
    payload.update(mailer_settings())

    templates = sorted(k.removeprefix("mailer_subjects_") for k in payload if k.startswith("mailer_subjects_"))
    summary = (
        f"{provider}: {smtp['host']}:{smtp['port']} as {smtp['user']}, "
        f"from {smtp['sender_name']} <{smtp['admin_email']}>; "
        f"templates {', '.join(templates)}; links expire after {payload['mailer_otp_exp']}s"
    )
    if dry_run:
        print(f"Would apply {summary}")
        return

    ref, token = env.get("SUPABASE_PROJECT_REF"), env.get("SUPABASE_ACCESS_TOKEN")
    if not ref or not token:
        fail("apply needs SUPABASE_PROJECT_REF and SUPABASE_ACCESS_TOKEN (a personal access token).")
    request = urllib.request.Request(
        MANAGEMENT_API.format(ref=ref),
        data=json.dumps(payload).encode(),
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            # The API sits behind a CDN that turns away urllib's default user agent.
            "User-Agent": "nca-worker-management/auth-email",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            applied = json.load(response)
    except urllib.error.HTTPError as exc:
        fail(f"Supabase refused the change ({exc.code}): {exc.read().decode(errors='replace')}")
    except urllib.error.URLError as exc:
        fail(f"could not reach the Supabase Management API: {exc.reason}")
    if applied.get("smtp_host") != smtp["host"]:
        fail(f"the change did not take: smtp_host is still {applied.get('smtp_host')!r}")
    print(f"Applied {summary}")


def print_env(env: dict[str, str]) -> None:
    _, smtp = smtp_settings(env)
    for field, value in smtp.items():
        print(f"export SMTP_{field.upper()}={shlex.quote(value)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    apply_parser = commands.add_parser("apply", help="apply the chosen provider to the production project")
    apply_parser.add_argument("--dry-run", action="store_true", help="show what would change, send nothing")
    commands.add_parser("env", help="print SMTP_* exports for the local stack")
    args = parser.parse_args()

    env = load_env()
    if args.command == "apply":
        apply(env, args.dry_run)
    else:
        print_env(env)


if __name__ == "__main__":
    main()
