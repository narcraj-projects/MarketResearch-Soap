"""Prepare ONLY the dedicated local stack; never print credentials or tokens."""
import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import urlparse
from uuid import uuid4

from alembic import command
from alembic.config import Config
import httpx
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    stage = "local_status"
    try:
        status = subprocess.run(
            ["npm.cmd" if os.name == "nt" else "npm", "exec", "--offline", "--yes", "--package=supabase@2.122.0", "--cache", str(root / ".cache/npm"),
             "--", "supabase", "status", "-o", "json"], cwd=root, capture_output=True, text=True, check=True,
            env=os.environ | {"DO_NOT_TRACK": "1", "SUPABASE_TELEMETRY_DISABLED": "1"},
        )
        data = json.loads(status.stdout)
        admin_url = make_url(data["DB_URL"]).set(drivername="postgresql+psycopg")
        api_url = data["API_URL"]
        if admin_url.host != "127.0.0.1" or admin_url.port != 57422 or urlparse(api_url).hostname != "127.0.0.1" or urlparse(api_url).port != 57421:
            raise ValueError("dedicated_loopback_stack_required")
        stage = "migration_upgrade"
        os.environ["LATHER_DATABASE_URL"] = admin_url.render_as_string(hide_password=False)
        cfg = Config(str(root / "backend/alembic.ini"))
        command.upgrade(cfg, "head")
        stage = "runtime_role"
        password = secrets.token_urlsafe(36)
        with psycopg.connect(data["DB_URL"], autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'lather_runtime'").fetchone()
            if exists:
                flags = conn.execute("SELECT rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolinherit FROM pg_roles WHERE rolname='lather_runtime'").fetchone()[0]
                if flags:
                    raise ValueError("existing_runtime_role_not_least_privilege")
                conn.execute(sql.SQL("ALTER ROLE lather_runtime PASSWORD {}").format(sql.Literal(password)))
            else:
                conn.execute(sql.SQL("CREATE ROLE lather_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}").format(sql.Literal(password)))
            conn.execute("GRANT lather_api TO lather_runtime")
            conn.execute("CREATE SCHEMA IF NOT EXISTS lather_test_control")
            conn.execute("CREATE TABLE IF NOT EXISTS lather_test_control.identity (id integer PRIMARY KEY CHECK (id=1), instance text NOT NULL)")
            instance = uuid4().hex
            conn.execute("INSERT INTO lather_test_control.identity VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET instance=EXCLUDED.instance", (instance,))
        runtime_url = admin_url.set(username="lather_runtime", password=password)
        stage = "local_auth_accounts"
        key = data.get("PUBLISHABLE_KEY") or data["ANON_KEY"]
        users = []
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            for label in ("a", "b"):
                email = f"demo-{label}-{uuid4().hex}@example.invalid"
                auth_password = secrets.token_urlsafe(36)
                response = client.post(api_url + "/auth/v1/signup", headers={"apikey": key}, json={"email": email, "password": auth_password})
                if response.status_code != 200 or "access_token" not in response.json():
                    raise ValueError("local_signup_failed")
                user = response.json()
                # Verify actual password login too; no service-role/admin Auth API.
                response = client.post(api_url + "/auth/v1/token?grant_type=password", headers={"apikey": key}, json={"email": email, "password": auth_password})
                if response.status_code != 200:
                    raise ValueError("local_login_failed")
                users.append({"id": user["user"]["id"], "token": response.json()["access_token"]})
        output = root / ".cache/auth-stage.json"
        output.write_text(json.dumps({"admin_url": admin_url.render_as_string(hide_password=False), "runtime_url": runtime_url.render_as_string(hide_password=False),
            "supabase_url": api_url, "publishable_key": key, "users": users, "test_instance": instance}), encoding="utf-8")
        output.chmod(0o600)
        print("PASS local migrations, non-bypass runtime role, two DEMO Auth signup/password-login sessions; credentials stored only in ignored local config")
    except Exception as exc:
        print(f"Local preparation failed at {stage}: {type(exc).__name__}; no credential details emitted")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
