"""Public lockfile metadata only goes to OSV, and only with --online.

No environment files, installed credentials, requests headers or briefs are read.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def inventory(root=ROOT):
    uv = tomllib.loads((root / "backend/uv.lock").read_text(encoding="utf8"))
    packages = {(row["name"], row["version"], "PyPI") for row in uv["package"] if row.get("source", {}).get("registry")}
    npm = json.loads((root / "frontend/package-lock.json").read_text(encoding="utf8"))
    for path, row in npm["packages"].items():
        if "node_modules/" in path and row.get("version"):
            packages.add((path.rsplit("node_modules/", 1)[1], row["version"], "npm"))
    return [{"package": {"name": name, "ecosystem": ecosystem}, "version": version} for name, version, ecosystem in sorted(packages)]


def secret_scan(root=ROOT):
    rules = {"private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "provider_token": re.compile(r"(?:sk-(?:proj-)?|sb_secret_)[A-Za-z0-9_-]{24,}"),
        "aws_access_id": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")}
    excluded = {".git", ".cache", "node_modules", ".venv", ".next", "__pycache__", ".mypy_cache", ".ruff_cache", "dist", "test-results", "playwright-report"}
    findings, files = [], 0
    for path in root.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.relative_to(root).parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".json", ".md", ".yml", ".yaml", ".toml", ".ps1", ".cjs", ".html"} and path.name != ".env.example":
            continue
        files += 1
        for number, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1):
            for rule, pattern in rules.items():
                if any("DEMO" not in match.group() for match in pattern.finditer(line)):
                    findings.append({"file": path.relative_to(root).as_posix(), "line": number, "rule": rule})
    return {"files_scanned": files, "findings": findings, "scope": "source/config/docs text; ignored credentials and binary artifacts excluded; pattern scan, not proof of no secrets"}


def osv_batch(queries):
    payload = json.dumps({"queries": queries}).encode()
    request = urllib.request.Request("https://api.osv.dev/v1/querybatch", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    # Ignore proxies/netrc: never attach workstation credentials or auth headers.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        data = response.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("advisory_response_limit")
        return json.loads(data)["results"]


def audit(online=False, query=osv_batch):
    packages = inventory()
    result = {"schema_version": "security-dependencies-1.0", "measured_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://api.osv.dev/v1/querybatch", "sent_data": "public package names/ecosystems/versions only", "packages": len(packages),
        "locks_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in ("backend/uv.lock", "frontend/package-lock.json")},
        "queried": 0, "findings": [], "errors": [], "secret_scan": secret_scan(), "status": "not_queried"}
    if online:
        for start in range(0, len(packages), 100):
            batch = packages[start:start + 100]
            try:
                rows = query(batch)
                if len(rows) != len(batch):
                    raise ValueError("advisory_count_mismatch")
                for package, row in zip(batch, rows, strict=True):
                    if row.get("next_page_token") or row.get("error"):
                        result["errors"].append({"package": package, "code": "incomplete_advisory_result"})
                        continue
                    result["queried"] += 1
                    if row.get("vulns"):
                        result["findings"].append(package | {"advisories": sorted(item["id"] for item in row["vulns"])})
            except Exception as error:
                result["errors"].append({"batch_start": start, "exception_class": type(error).__name__})
        result["status"] = "complete" if result["queried"] == len(packages) and not result["errors"] else "incomplete"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.online)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    matched = str(len(result["findings"])) if result["status"] == "complete" else "unmeasured"
    print(f"Dependency audit {result['status']}: {result['queried']}/{result['packages']} queried; affected package versions {matched}; secret pattern findings {len(result['secret_scan']['findings'])}")
    if result["secret_scan"]["findings"] or result["findings"] or (args.online and result["status"] != "complete"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
