"""Renew ONLY the existing disposable local fixture identity; never send email.

This is a local test setup helper, not an application auth endpoint. Administrative
material remains only in this CLI process and is never sent to the frontend.
"""
import json
import os
from pathlib import Path
import subprocess

import httpx

from app.security import configure_private_logging
from tools.workflow_demo import local_config


def main():
    configure_private_logging()
    cfg = local_config()  # Validates exact loopback ports and independent DB marker.
    root = Path(__file__).resolve().parents[2]
    owner = cfg["users"][0]["id"]
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as client:
        if cfg["users"][0].get("refresh_token"):
            response = client.post(cfg["supabase_url"] + "/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": cfg["publishable_key"]}, json={"refresh_token": cfg["users"][0]["refresh_token"]})
        else:
            status = subprocess.run(["npm.cmd" if os.name == "nt" else "npm", "exec", "--offline", "--yes", "--package=supabase@2.122.0", "--cache", str(root / ".cache/npm"), "--", "supabase", "status", "-o", "json"],
                cwd=root, capture_output=True, text=True, check=True, env=os.environ | {"DO_NOT_TRACK": "1", "SUPABASE_TELEMETRY_DISABLED": "1"})
            private_status = json.loads(status.stdout)
            if private_status.get("API_URL") != "http://127.0.0.1:57421":
                raise ValueError("local_auth_only")
            admin_headers = {"apikey": private_status["SERVICE_ROLE_KEY"], "Authorization": "Bearer " + private_status["SERVICE_ROLE_KEY"]}
            user_response = client.get(cfg["supabase_url"] + "/auth/v1/admin/users/" + owner, headers=admin_headers)
            user_response.raise_for_status()
            user = user_response.json()
            if user.get("id") != owner or not user.get("email", "").endswith("@example.invalid"):
                raise ValueError("existing_disposable_fixture_identity_required")
            generated = client.post(cfg["supabase_url"] + "/auth/v1/admin/generate_link", headers=admin_headers,
                json={"type": "magiclink", "email": user["email"]})
            generated.raise_for_status()
            raw = generated.json()
            token_hash = raw.get("properties", raw)["hashed_token"]
            # Verify locally. generate_link does not invoke an external email send.
            response = client.post(cfg["supabase_url"] + "/auth/v1/verify", headers={"apikey": cfg["publishable_key"]},
                json={"token_hash": token_hash, "type": "email"})
        response.raise_for_status()
        session = response.json()
        if session["user"]["id"] != owner or session["user"].get("role") != "authenticated":
            raise ValueError("local_owner_session_mismatch")
        cfg["users"][0]["token"] = session["access_token"]
        cfg["users"][0]["refresh_token"] = session["refresh_token"]
        output = root / ".cache/auth-stage.json"
        output.write_text(json.dumps(cfg), encoding="utf8")
        output.chmod(0o600)
    print("PASS local fixture session renewed for the same owner; no email sent, no keys/tokens displayed, research unchanged.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit("Local fixture session renewal failed (" + type(error).__name__ + "); private details suppressed") from None
