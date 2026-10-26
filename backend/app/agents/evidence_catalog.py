"""Read-only evidence boundary, rebuilt from immutable raw pages, not analyst prose."""
from uuid import uuid5

from app.agents.extraction import canonical, extract, parse_html
from app.agents.analysis_policy import MEDICAL
from app.harness.analysis_types import EvidencePack, Finding, FindingKind
from app.harness.policy import PolicyDenied
from app.harness.urls import normalize_url
from app.agents.snippet_extraction import eligible


def catalog(pack: EvidencePack) -> tuple[Finding, ...]:
    result = {}
    competitors = {c.competitor_id: c for c in pack.competitors}
    for lane in pack.research:
        competitor = competitors[lane.competitor_id]
        domain = normalize_url(competitor.canonical_url, demo=True)[1]
        pages = []
        for source in lane.sources:
            if source.access_status == "ok" and source.evidence_kind == "page_excerpt":
                _, excerpt, structured, links, restricted = parse_html(source.body or "", source.canonical_url)
                if restricted or (excerpt, structured, links) != (source.excerpt, source.structured, source.links):
                    raise PolicyDenied("raw_evidence_snapshot_mismatch")
            if source.evidence_kind == "page_excerpt" or eligible(source, normalize_url(source.canonical_url, demo=True)[1] == domain):
                pages.append(extract(source, competitor.name, first_party=normalize_url(source.canonical_url, demo=True)[1] == domain))
        if tuple(pages) != lane.pages:
            raise PolicyDenied("extraction_snapshot_mismatch")
        for page in pages:
            groups = [(None, page.observations)] + [(product.locator, product.observations) for product in page.products]
            for locator, observations in groups:
                for observation in observations:
                    kind: FindingKind = "source_claim" if (observation.kind == "competitor_marketing_claim" or observation.field == "audience"
                        or (observation.value is not None and MEDICAL.search(canonical(observation.value)))) else "fact"
                    fid = uuid5(pack.run_id, canonical([str(lane.competitor_id), str(page.source_id), locator, observation.model_dump(mode="json")]))
                    text = ("Source reports " if kind == "source_claim" else "Listed ") + observation.field + ": " + canonical(observation.value)
                    finding = Finding(finding_id=fid, competitor_id=lane.competitor_id, source_id=page.source_id, product_locator=locator,
                        field=observation.field, value=observation.value, kind=kind, text=text, evidence=observation.evidence,
                        unavailable_reason=observation.unavailable_reason,
                        caveat="Attribution only; not independently established or representative of all customers." if kind == "source_claim" else "Observed in the cited listing, not independently verified product performance.")
                    result[fid] = finding
    return tuple(result[key] for key in sorted(result, key=str))
