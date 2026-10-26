"""Read authenticated review receipts for an existing predeclared cohort; no rerun/LLM."""
import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select

from app import models as m
from app.config import Settings
from app.evaluations.dataset import Dataset
from app.evaluations.review import packet, coverage, owner_gate
from app.repository import owner_transaction
from tools.workflow_demo import local_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluated = json.loads(args.evaluation.read_text(encoding="utf8"))
    dataset = Dataset()
    if evaluated.get("manifest_hash") != dataset.manifest_hash:
        raise ValueError("evaluation_dataset_mismatch")
    cohort = evaluated["owner_report_cohort"]
    if [row["case_id"] for row in cohort] != dataset.read("cases.json")["owner_report_cohort"]:
        raise ValueError("predeclared_owner_cohort_required")
    cfg, settings = local_config(), Settings()
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    owner = UUID(cfg["users"][0]["id"])
    try:
        support, ratings = {}, []
        with owner_transaction(engine, owner) as repo:
            for entry in cohort:
                run_id, report_id = UUID(entry["run_id"]), UUID(entry["report_id"])
                current = packet(repo, run_id, report_id)
                if current["report_hash"] != entry["report_hash"] or current["approval"] != "saved":
                    raise ValueError("cohort_saved_report_binding_mismatch")
                rows = list(repo.conn.execute(select(m.evaluation_results).where(m.evaluation_results.c.owner_id == owner,
                    m.evaluation_results.c.run_id == run_id).order_by(m.evaluation_results.c.created_at, m.evaluation_results.c.id)).mappings())
                if not any(row["data"].get("case_id") == entry["case_id"] and row["data"].get("run_id") == entry["run_id"] for row in rows):
                    raise ValueError("cohort_case_not_bound_to_recorded_execution")
                support[entry["case_id"]] = coverage(current, rows, settings.trusted_reviewer_ids)
                ratings.extend(rows)
        output = {"schema_version": "existing-review-results-1.0", "label": "DEMO", "support": support,
            "owner_usefulness": owner_gate(cohort, ratings, settings.business_owner_ids), "scope": "Existing exact reports; no fabricated human decisions, no model calls or exports"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf8")
        print("Read existing hash-bound review receipts; no new reports, judgments or provider calls")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Existing review grading failed ({type(error).__name__}); details suppressed.") from None
