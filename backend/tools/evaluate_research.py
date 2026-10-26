"""Execute all pinned research recordings. Persistence is evaluated separately in Postgres."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from app.agents.extraction import contradictions, extract
from app.agents.researcher import research_parallel
from tests.research_support import FOLDER, MemoryResearchState, setup, versions


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline labeled research recording evaluation; no external calls")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for path in sorted(FOLDER.glob("R*.json")):
        recording, journal, clock, gateway, ctx = setup(path.stem)
        if "parallel" in path.stem:
            competitors = tuple({"id": UUID(int=10 + i), "name": c["name"], "canonical_url": c["url"]} for i, c in enumerate(recording.case["competitors"]))
            results = research_parallel(ctx, competitors, gateway, MemoryResearchState(competitors))
            sources = [source for result in results for source in result.sources]
            pages = tuple(page for result in results for page in result.pages)
            root_url = ""
        else:
            cid, competitor = UUID(int=10), recording.case["competitor"]
            root_url = competitor["url"]
            sources = list(gateway.retrieve(ctx, cid, root_url))
            if recording.case.get("include_news"):
                hits = gateway.news(ctx, cid, competitor["name"])
                sources.extend(hits)
                for hit in hits:
                    sources.extend(gateway.retrieve(ctx, cid, hit.canonical_url))
            pages = tuple(extract(source, competitor["name"], first_party=source.publisher.endswith("demo-a.invalid")) for source in sources if source.evidence_kind == "page_excerpt")
        products = [product for page in pages for product in page.products]
        actual = {"products": len(products), "amounts": [str(p.amount) if p.amount is not None else None for p in products],
            "totals": [str(p.total_weight_g) if p.total_weight_g is not None else None for p in products],
            "sku": products[0].sku if products else None, "denied": any(s.access_status == "denied" for s in sources),
            "page_requests": recording.requests.count("GET " + root_url), "conflicts": len(contradictions(pages)),
            "launches": sum(o.field == "reported_launch" and o.value is not None for page in pages for o in page.observations), "retry_delays": clock.delays}
        # No cross-competitor contradiction inference in production. This diagnostic is only
        # used by single-competitor expected cases; production aggregates within each lane.
        expected = recording.case["expected"]
        checks = {key: actual.get(key) == value for key, value in expected.items()}
        evidence_checks = []
        for page in pages:
            for observation in [*page.observations, *(o for p in page.products for o in p.observations)]:
                for evidence in observation.evidence:
                    source = next(s for s in sources if s.source_id == evidence.source_id)
                    evidence_checks.append(source.access_status == "ok" and evidence.quote in (source.excerpt or "") and sha256(evidence.quote.encode()).hexdigest() == evidence.quote_hash)
        checks["quote_provenance"] = all(evidence_checks)
        checks["unknowns_remain_null"] = all(o.value is not None or (o.unavailable_reason is not None and not o.evidence) for page in pages for o in page.observations)
        rows.append({"case_id": path.stem, "label": "DEMO", "expected": expected, "actual": {key: actual[key] for key in expected}, "checks": checks,
            "outcome": "passed" if all(checks.values()) else "failed", "recorded_http_requests": len(recording.requests), "accounted_attempts": len(journal.rows)})
    report = {"label": "DEMO", "dataset_version": "research-demo-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha256((FOLDER / "manifest.json").read_bytes()).hexdigest(), "versions": versions().model_dump(mode="json"),
        "cases": rows, "recordings": len(rows), "passed": sum(row["outcome"] == "passed" for row in rows), "actual_external_calls": 0,
        "actual_provider_credits_spent": 0, "semantic_support": "not_evaluated", "owner_usefulness": "not_evaluated",
        "limits": "Synthetic HTTP/news/DNS, fake clock and test-only memory stores. Real local persistence, approval, isolation and process restart are separate integration tests; no live security or extraction quality certification."}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(f"DEMO research recordings: {report['passed']}/{len(rows)} passed; zero external calls/credits. Semantic support and usefulness not evaluated.")
    if report["passed"] != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
