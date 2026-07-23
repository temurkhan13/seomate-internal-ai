#!/usr/bin/env python3
"""One-time helper: mint a Google OAuth refresh token for GSC **and** GA4.

A Google refresh token is scope-bound, so Search Console and Analytics are
not connected separately -- you consent **once** for both scopes and get a
single refresh token that powers both adapters (see
``docs/google-oauth-setup.md``).

This script runs the installed-app / loopback consent flow locally:

  1. prints (and optionally opens) the Google consent screen URL (both scopes),
  2. captures the auth code on ``http://localhost:<port>/``,
  3. exchanges it for a **refresh token**,
  4. uses the fresh access token to list the GA4 properties and GSC sites the
     consenting account can actually see -- so you learn the numeric GA4
     property id and the verified GSC property string immediately.

Secret-safe options
-------------------
- ``--client-secret-from-clipboard`` reads the client secret straight from the
  OS clipboard (Windows PowerShell ``Get-Clipboard``), so it is never typed on
  a command line.
- ``--write-env PATH`` writes GOOGLE_OAUTH_CLIENT_ID / _SECRET / _REFRESH_TOKEN
  and GA4_PROPERTY_ID into that ``.env`` (created/updated in place) instead of
  printing them, so the secret and refresh token never hit stdout.
- ``--no-browser`` just prints the consent URL (for driving the consent in a
  browser you already control).

Zero third-party dependencies (stdlib only).

Usage
-----
    # copy the client secret to the clipboard first (GCP console copy icon),
    # then, secret-safe end to end:
    python scripts/get_google_refresh_token.py \
        --client-id XXXX.apps.googleusercontent.com \
        --client-secret-from-clipboard --write-env .env --no-browser

    # or the simple interactive form (prints a paste-ready .env block):
    python scripts/get_google_refresh_token.py --client-secret-file <downloaded.json>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
GA4_ADMIN_SUMMARIES = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
GSC_SITES = "https://www.googleapis.com/webmasters/v3/sites"

# The two data scopes SEOMATE needs. Both are read-only.
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",   # GSC
    "https://www.googleapis.com/auth/analytics.readonly",    # GA4
    "openid",
    "email",
]


class _CodeCatcher(BaseHTTPRequestHandler):
    """Single-shot handler that captures ?code=... from the redirect."""

    captured: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CodeCatcher.captured = {k: v[0] for k, v in params.items()}
        ok = "code" in _CodeCatcher.captured
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = (
            "<h2>SEOMATE: Google connected.</h2>"
            "<p>Refresh token captured. You can close this tab and return to the terminal.</p>"
            if ok
            else "<h2>SEOMATE: consent failed.</h2><p>Check the terminal for details.</p>"
        )
        self.wfile.write(f"<html><body style='font-family:sans-serif'>{msg}</body></html>".encode())

    def log_message(self, *args: object) -> None:  # silence access logs
        pass


def _http_json(url: str, *, token: str | None = None, data: dict | None = None) -> dict:
    """GET/POST helper returning parsed JSON, with readable error surfacing."""
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}\n{detail}") from None


def _prompt(label: str) -> str:
    val = input(f"{label}: ").strip()
    if not val:
        sys.exit(f"error: {label} is required.")
    return val


def _read_clipboard() -> str:
    """Read the OS clipboard via PowerShell (Windows). Never echoed."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (out.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"error: could not read clipboard: {exc}")


def _upsert_env(path: str, values: dict[str, str]) -> None:
    """Create/update KEY=VALUE lines in a .env file, leaving other lines intact."""
    lines: list[str] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in values.items():
        if key not in seen:
            out.append(f"{key}={val}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Mint a GSC+GA4 Google refresh token.")
    ap.add_argument("--client-id", default=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"))
    ap.add_argument("--client-secret", default=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"))
    ap.add_argument(
        "--client-secret-file",
        default=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE"),
        help="path to the client_secret_*.json downloaded from the GCP OAuth client",
    )
    ap.add_argument(
        "--client-secret-from-clipboard",
        action="store_true",
        help="read the client secret from the OS clipboard (never echoed on a command line)",
    )
    ap.add_argument(
        "--write-env",
        default=None,
        help="write GOOGLE_OAUTH_* + GA4_PROPERTY_ID into this .env instead of printing them",
    )
    ap.add_argument(
        "--no-browser",
        action="store_true",
        help="do not auto-open a browser; just print the consent URL",
    )
    ap.add_argument("--port", type=int, default=8765, help="loopback port (default 8765)")
    args = ap.parse_args()

    client_id = args.client_id
    client_secret = args.client_secret
    if args.client_secret_file:
        with open(args.client_secret_file, encoding="utf-8") as fh:
            blob = json.load(fh)
        creds = blob.get("installed") or blob.get("web") or blob
        client_id = creds.get("client_id") or client_id
        client_secret = creds.get("client_secret") or client_secret
    if args.client_secret_from_clipboard and not client_secret:
        client_secret = _read_clipboard()
    client_id = client_id or _prompt("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = client_secret or _prompt("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = f"http://localhost:{args.port}/"

    auth_url = f"{AUTH_ENDPOINT}?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "access_type": "offline",       # -> refresh token
            "prompt": "consent",            # force a refresh token even on re-consent
            "include_granted_scopes": "true",
        }
    )

    print("\n1) Sign in as the account that has access to BOTH the GSC property")
    print("   and the GA4 property, then approve consent.")
    print(f"\n   CONSENT URL:\n   {auth_url}\n")
    if not args.no_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:  # noqa: BLE001
            pass

    print(f"2) Waiting for the redirect on {redirect_uri} ...", flush=True)
    httpd = HTTPServer(("localhost", args.port), _CodeCatcher)
    httpd.handle_request()  # blocks until Google redirects back once
    captured = _CodeCatcher.captured

    if "error" in captured:
        print(f"\nConsent returned error: {captured['error']}")
        return 1
    if "code" not in captured:
        print("\nNo authorization code received.")
        return 1

    print("3) Exchanging the code for tokens ...", flush=True)
    tokens = _http_json(
        TOKEN_ENDPOINT,
        data={
            "code": captured["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    if not refresh_token:
        print("\nNo refresh_token returned. Re-run (the flow forces prompt=consent).")
        return 1

    # Identify the consenting account (helps the 'grant access on the property' step).
    who = ""
    try:
        who = _http_json(USERINFO_ENDPOINT, token=access_token).get("email", "")
    except Exception:  # noqa: BLE001
        pass

    print("\n" + "=" * 68)
    print("SUCCESS -- refresh token minted (covers GSC + GA4).")
    if who:
        print(f"Consented as: {who}")
    print("=" * 68)

    # --- Name the GA4 properties this account can see (non-secret) ------------
    ga4_property_id = ""
    print("\nGA4 properties visible to this account:")
    try:
        summaries = _http_json(GA4_ADMIN_SUMMARIES, token=access_token)
        found = False
        for acct in summaries.get("accountSummaries", []):
            acct_name = acct.get("displayName", "?")
            for prop in acct.get("propertySummaries", []):
                found = True
                pid = prop.get("property", "")            # e.g. "properties/123456789"
                if not ga4_property_id:
                    ga4_property_id = pid
                print(f"  - {pid:<24} {prop.get('displayName','?')}   (account: {acct_name})")
        if not found:
            print("  (none -- add this account in GA4 Admin > Property Access Management)")
    except Exception as exc:  # noqa: BLE001
        print(f"  could not list (enable the Google Analytics Admin API?):\n    {exc}")

    # --- Name the GSC sites this account can see (non-secret) -----------------
    print("\nGSC properties visible to this account:")
    try:
        sites = _http_json(GSC_SITES, token=access_token)
        entries = sites.get("siteEntry", [])
        if entries:
            for s in entries:
                print(f"  - {s.get('siteUrl','?'):<40} ({s.get('permissionLevel','?')})")
        else:
            print("  (none -- add this account as a user on the property in Search Console)")
    except Exception as exc:  # noqa: BLE001
        print(f"  could not list (enable the Search Console API?):\n    {exc}")

    # --- Emit credentials: to .env (secret-safe) or to stdout -----------------
    env_values = {
        "GOOGLE_OAUTH_CLIENT_ID": client_id,
        "GOOGLE_OAUTH_CLIENT_SECRET": client_secret,
        "GOOGLE_OAUTH_REFRESH_TOKEN": refresh_token,
    }
    if ga4_property_id:
        env_values["GA4_PROPERTY_ID"] = ga4_property_id

    if args.write_env:
        _upsert_env(args.write_env, env_values)
        wrote = ", ".join(env_values)
        print("\n" + "-" * 68)
        print(f"Wrote {len(env_values)} keys to {args.write_env}: {wrote}")
        print("Values NOT shown (secret-safe). Keep .env gitignored.")
        print("-" * 68)
    else:
        print("\n" + "-" * 68)
        print("Paste into the repo-root .env (gitignored -- never commit / never chat it):")
        print("-" * 68)
        print(f"GOOGLE_OAUTH_CLIENT_ID={client_id}")
        print("GOOGLE_OAUTH_CLIENT_SECRET=<the client secret you used>")
        print(f"GOOGLE_OAUTH_REFRESH_TOKEN={refresh_token}")
        print(f"GA4_PROPERTY_ID={ga4_property_id or 'properties/REPLACE_WITH_ID_ABOVE'}")
        print("-" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
