"""Allowlisted source ZIP. Never packages local keys, tokens, caches or credits screenshots."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {
    ".git",
    ".cache",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "test-results",
    "playwright-report",
    "Available credits",
}
ROOT_FILES = {"README.md", "Makefile", ".gitignore", ".gitattributes", ".env.example"}
SUBMISSION_DOCS = {
    "USAGE_GUIDE.md",
    "LIVE_PILOT_RESULTS.md",
    "VIDEO_SCRIPT_3M30.md",
    "SUBMISSION_OVERVIEW.md",
    "REQUIREMENTS_TRACEABILITY.md",
    "ARCHITECTURE.md",
    "HARNESS_SPEC.md",
    "AGENT_CONTRACTS.md",
    "EVAL_PLAN.md",
    "CI_GATES.md",
    "MODEL_BENCHMARK.md",
    "MODEL_IMPLEMENTATION_PLAN.md",
    "AUTH_STORAGE.md",
    "SCOUT_SPEC.md",
    "RESEARCH_SPEC.md",
    "ANALYSIS_SPEC.md",
    "REPORT_SPEC.md",
    "HISTORY_SPEC.md",
    "CHAOS_SPEC.md",
    "EVALUATION_SPEC.md",
    "EVALUATION_REPORT.md",
    "SECURITY_AUDIT.md",
    "SECURITY_STAGE_RESULTS.md",
    "UI_FIDELITY.md",
    "SOURCE_AUDIT.md",
    "BACKLOG.md",
    "source-manifest.json",
    "openapi.json",
    "Lather_Lens_PRD_v1.1.md",
    "Agentic_Market_Research_Agent_BRD_Handmade_Soap.docx",
    "Soap Market Research Agent — UI.html",
    "live-golden-candidate.json",
    "live-golden-regression.json",
    "live-secret-audit.json",
    "LIVE_STAGE_FILES.json",
    "LIVE_RECEIPT.json",
    "REQUIREMENTS_QUALITY_AUDIT.md",
    "EVALUATION_PLAN.md",
    "SECURITY_STAGE_FILES.json",
}


def files(clean=False):
    selected = []
    for folder in ("backend", "frontend", "docs", "scripts", "supabase", ".github"):
        for path in (ROOT / folder).rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if clean and relative.parts[0] == "docs" and (
                any(part in {"Available credits", "Project handout", "ui-screenshots"} for part in relative.parts)
                or "PRD" in path.name or path.suffix == ".docx" or path.name == "Soap Market Research Agent — UI.html"
            ):
                continue
            if any(part in EXCLUDED for part in relative.parts):
                continue
            if path.name.startswith(".env") and path.name != ".env.example":
                continue
            if (
                path.suffix in {".pyc", ".tsbuildinfo", ".log", ".zip"}
                or path.is_symlink()
            ):
                continue
            if (
                clean
                and relative.parts[0] == "docs"
                and path.name not in SUBMISSION_DOCS
                and not any(
                    part in {"adr", "ui-reference", "reference"}
                    for part in relative.parts[1:-1]
                )
            ):
                continue
            selected.append(path)
    selected.extend(ROOT / name for name in ROOT_FILES if (ROOT / name).is_file())
    if clean:
        selected.extend(
            ROOT / "submission" / name
            for name in (
                "Lather-Lens-Overview.pdf",
                "Lather-Lens-Overview.html",
                "Lather-Lens-3m30.mp4",
                "Lather-Lens-LIVE-report.html",
                "Lather-Lens-LIVE-report.csv",
            )
            if (ROOT / "submission" / name).is_file()
        )
    return sorted(set(selected))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "submission/Lather-Lens-source.zip"
    )
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--checkout", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("submission_output_must_stay_in_workspace")
    if output.exists():
        raise ValueError("submission_archive_exists_use_a_new_filename")
    from tools.security_audit import secret_scan

    scan = secret_scan()
    if scan["findings"]:
        raise ValueError("source_secret_pattern_findings_require_review")
    selected = files(args.clean)
    # Pattern scanning is supplemented by exact comparison with this machine's
    # configured secrets. Values are never printed or put into the manifest.
    from app.harness.live_policy import LiveSecrets

    private = LiveSecrets()
    protected = [
        value.get_secret_value().encode()
        for value in (private.lather_tavily_api_key, private.lather_llm_api_key)
        if value is not None
    ]
    local_auth = ROOT / ".cache/auth-stage.json"
    if local_auth.exists():
        config = json.loads(local_auth.read_text(encoding="utf8"))
        protected.extend(
            user[key].encode()
            for user in config.get("users", [])
            for key in ("token", "refresh_token")
            if user.get(key)
        )
        protected.extend(
            config[key].encode()
            for key in ("admin_url", "runtime_url")
            if config.get(key)
        )
    for source in selected:
        content = source.read_bytes()
        if any(value in content for value in protected if len(value) >= 12):
            raise ValueError("configured_private_material_in_submission_source")
    if args.checkout:
        checkout = args.checkout.resolve()
        if (
            not checkout.is_relative_to(ROOT / ".cache")
            or not (checkout / ".git").is_dir()
        ):
            raise ValueError("isolated_submission_checkout_required")
        import shutil

        for source in selected:
            target = checkout / source.relative_to(ROOT)
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ValueError(
                    "existing_checkout_content_preserved_use_clean_checkout"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        print(
            f"PASS {len(selected)} allowlisted files copied into isolated checkout; no originals removed."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Source submission, not a deployed release",
        "excluded": sorted(EXCLUDED)
        + ["private .env files", "credit/account screenshots"],
        "files": [],
    }
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for path in selected:
            name = path.relative_to(ROOT).as_posix()
            archive.write(path, "Lather-Lens/" + name)
            manifest["files"].append(
                {"path": name, "sha256": sha256(path.read_bytes()).hexdigest()}
            )
        archive.writestr(
            "Lather-Lens/SUBMISSION_MANIFEST.json",
            json.dumps(manifest, indent=2) + "\n",
        )
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert not any(part in EXCLUDED for part in Path(name).parts)
            assert not (
                Path(name).name.startswith(".env") and Path(name).name != ".env.example"
            )
    print(
        f"PASS submission ZIP: {len(selected)} source/document files, {output.stat().st_size} bytes; private config/caches/credit screenshots excluded."
    )


if __name__ == "__main__":
    main()
