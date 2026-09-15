#!/usr/bin/env python3
"""
One-time OAuth setup to get a refresh token for the Alexa Smart Home API.
Run this once, then poll.py handles token refresh automatically.

Steps this script walks you through:
  1. Open an Amazon authorization URL in your browser
  2. You log in and approve access
  3. Amazon redirects to localhost — this script catches it
  4. Exchanges the code for tokens and saves config.json
"""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

CONFIG_FILE = Path(__file__).parent / "config.json"

LWA_AUTH_URL  = "https://www.amazon.com/ap/oa"
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
REDIRECT_URI  = "http://localhost:9876/callback"
SCOPES        = " ".join([
    "alexa::smarthome:devices:read",
    "alexa::smarthome:guest:skill:invokeAlexa",
])

# The authorization code captured by the local HTTP server
_auth_code = None
_server    = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;padding:40px">
                <h2>&#10003; Authorization successful!</h2>
                <p>You can close this tab and return to the terminal.</p>
                </body></html>
            """)
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body>Error: {error}</body></html>".encode())
        threading.Thread(target=_server.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass  # silence request logs


def main():
    print("=" * 60)
    print("  Alexa Smart Home — one-time OAuth setup")
    print("=" * 60)
    print()

    if CONFIG_FILE.exists():
        existing = json.loads(CONFIG_FILE.read_text())
        if existing.get("refresh_token"):
            print(f"Config already exists at {CONFIG_FILE}")
            ans = input("Re-authorize and overwrite? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                return

    print("Step 1 of 3 — Enter your Amazon developer credentials")
    print("  (Create a security profile at developer.amazon.com if you")
    print("   haven't already — see SETUP.md for details)")
    print()
    client_id     = input("  Client ID:     ").strip()
    client_secret = input("  Client Secret: ").strip()

    if not client_id or not client_secret:
        print("ERROR: Client ID and secret are required.")
        raise SystemExit(1)

    # Build the auth URL
    params = {
        "client_id":     client_id,
        "scope":         SCOPES,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
    }
    auth_url = f"{LWA_AUTH_URL}?{urlencode(params)}"

    print()
    print("Step 2 of 3 — Log in and approve access")
    print(f"  Opening: {auth_url[:80]}…")
    print()
    print("  (If the browser doesn't open, paste the URL above manually)")
    webbrowser.open(auth_url)

    # Start local server to catch the redirect
    global _server
    _server = HTTPServer(("localhost", 9876), CallbackHandler)
    print("  Waiting for Amazon to redirect back to localhost:9876…")
    _server.serve_forever()

    if not _auth_code:
        print("ERROR: No authorization code received.")
        raise SystemExit(1)

    print()
    print("Step 3 of 3 — Exchanging code for tokens…")
    r = requests.post(LWA_TOKEN_URL, data={
        "grant_type":   "authorization_code",
        "code":         _auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id":    client_id,
        "client_secret": client_secret,
    }, timeout=15)

    if r.status_code != 200:
        print(f"ERROR: Token exchange failed ({r.status_code}): {r.text}")
        raise SystemExit(1)

    tokens = r.json()
    config = {
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"  Saved config to {CONFIG_FILE}")
    print()
    print("All done! Run the poller with:")
    print("  python poll.py")
    print("  python poll.py --interval 1    # poll every minute")
    print("  python poll.py --once          # single poll, for cron")


if __name__ == "__main__":
    main()
