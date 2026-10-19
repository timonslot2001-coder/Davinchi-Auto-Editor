"""One-time TikTok login (OAuth v2 with PKCE) → stores TIKTOK_REFRESH_TOKEN in .env.

In your TikTok developer app, add redirect URI:  http://127.0.0.1:8765/callback
and request scope video.upload (Content Posting API, "Upload" = drafts to your inbox).
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from .publish import TIKTOK, _set_env

REDIRECT = "http://127.0.0.1:8765/callback"


def login():
    key, secret = os.environ.get("TIKTOK_CLIENT_KEY"), os.environ.get("TIKTOK_CLIENT_SECRET")
    if not key or not secret:
        raise SystemExit("Put TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env first (see README).")
    verifier = secrets.token_urlsafe(64)
    # TikTok desktop PKCE uses the hex SHA256 of the verifier
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    state = secrets.token_urlsafe(16)
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": key, "scope": "user.info.basic,video.upload", "response_type": "code",
        "redirect_uri": REDIRECT, "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>TikTok linked — you can close this tab.</h2>".encode())

        def log_message(self, *a):
            pass

    print("Opening TikTok in your browser… log in and allow access.")
    webbrowser.open(url)
    srv = HTTPServer(("127.0.0.1", 8765), H)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if got.get("state") != state or "code" not in got:
        raise SystemExit(f"TikTok login failed: {got.get('error_description') or got}")
    r = requests.post(f"{TIKTOK}/oauth/token/", timeout=30, data={
        "client_key": key, "client_secret": secret, "code": got["code"], "grant_type": "authorization_code",
        "redirect_uri": REDIRECT, "code_verifier": verifier})
    r.raise_for_status()
    _set_env("TIKTOK_REFRESH_TOKEN", r.json()["refresh_token"])
    print("TikTok connected ✓ (refresh token saved in .env)")
