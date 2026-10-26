"""DEMO-only dated history generator from the checked-in research recording. No sockets."""

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
from uuid import UUID, uuid5

from app.agents.analyst import analyze
from app.agents.extraction import extract, parse_html
from app.agents.scout import Discovery, DiscoveryArtifact, Fit, RankedCandidate
from app.agents.reviewer import review
from app.history import version_meta
from app.harness.analysis_types import Competitor, EvidencePack
from app.harness.research_types import CompetitorResearch, RetrievedSource
from app.report_types import ApprovalView, ReportView
from app.reporting import snapshot
from app.repository import digest
from tests.analysis_support import AS_OF, evidence_pack


def history_document(mode="same", *, later=False, run_id=None):
    run_id = run_id or UUID(int=9201 if later else 9200)
    base = evidence_pack("baseline")
    at = AS_OF if later else AS_OF - timedelta(days=14)
    if mode == "long_before":
        at = AS_OF - timedelta(days=60)
    capture_at = (
        AS_OF - timedelta(days=14)
        if mode == "cached"
        else at - timedelta(days=60)
        if mode == "aged"
        else at
    )
    competitors, lanes, candidates = [], [], []
    for index, old in enumerate(base.research):
        name, url = base.competitors[index].name, base.competitors[index].canonical_url
        if mode == "rebrand" and index == 0:
            name = "DEMO Renamed Maker"
        cid = uuid5(run_id, "competitor:" + url)
        competitors.append(Competitor(competitor_id=cid, name=name, canonical_url=url))
        node = deepcopy(old.sources[0].structured[0])
        node["offers"]["availability"] = "https://schema.org/InStock"
        if index == 0:
            if mode in {"price", "conflict", "cached", "aged", "evolution"}:
                node["offers"]["price"] = "140"
            if mode == "currency":
                node["offers"]["priceCurrency"] = "USD"
            if mode == "pack":
                node["numberOfItems"], node["weight"]["value"] = 2, "200"
            if mode == "no_sku":
                node.pop("sku")
            if mode in {"gone", "evolution"}:
                node["offers"]["availability"] = "https://schema.org/Discontinued"
            if mode == "out_of_stock":
                node["offers"]["availability"] = "https://schema.org/OutOfStock"
            if mode == "omission":
                node.pop("description", None)
            if mode == "wrong_offer":
                node["offers"].update(
                    availability="https://schema.org/Discontinued",
                    itemOffered={"sku": "DEMO-other-product"},
                )
        variants = [node]
        if index == 0 and mode in {"new", "conflict", "evolution"}:
            variants.append(deepcopy(node))
            if mode in {"new", "evolution"}:
                variants[1]["sku"], variants[1]["name"] = (
                    "DEMO-A-NEW",
                    "DEMO A travel bar",
                )
                variants[1]["offers"]["availability"] = "https://schema.org/InStock"
            else:
                variants[1]["offers"]["price"] = "180"
        sources, pages = [], []
        for ordinal, item in enumerate(variants):
            page_url = url if ordinal == 0 else url + "/additional"
            sid = uuid5(run_id, "source:" + page_url)
            if index == 0 and mode in {"unavailable", "denied"}:
                source = RetrievedSource(
                    source_id=sid,
                    competitor_id=cid,
                    canonical_url=page_url,
                    requested_url=page_url,
                    retrieved_at=at,
                    title="DEMO unavailable website",
                    publisher="demo-a.invalid",
                    access_status="denied" if mode == "denied" else "unavailable",
                    evidence_kind="page_excerpt",
                    content_hash=None,
                    text_hash=None,
                    reason="access_denied" if mode == "denied" else "network",
                )
            else:
                body = (
                    '<html><title>DEMO history listing</title><script type="application/ld+json">'
                    + json.dumps(item)
                    + "</script><body>DEMO dated history fixture</body></html>"
                )
                title, excerpt, structured, links, _ = parse_html(body, page_url)
                source = RetrievedSource(
                    source_id=sid,
                    competitor_id=cid,
                    canonical_url=page_url,
                    requested_url=page_url,
                    retrieved_at=capture_at,
                    title=title,
                    publisher="DEMO maker",
                    access_status="ok",
                    evidence_kind="page_excerpt",
                    body=body,
                    excerpt=excerpt,
                    structured=structured,
                    links=links,
                    content_hash=sha256(body.encode()).hexdigest(),
                    text_hash=sha256(excerpt.encode()).hexdigest(),
                )
            sources.append(source)
            pages.append(extract(source, name, first_party=True))
        lanes.append(
            CompetitorResearch(
                competitor_id=cid,
                state="partial" if mode in {"unavailable", "denied"} and index == 0 else "complete",
                sources=tuple(sources),
                pages=tuple(pages),
            )
        )
        candidates.append(
            RankedCandidate(
                candidate_id=cid,
                name=name,
                canonical_url=url,
                domain=f"demo-{chr(97 + index)}.invalid",
                source_ids=(sources[0].source_id,),
                excerpt_hash=sources[0].text_hash or "0" * 64,
                fits=tuple(
                    Fit(
                        dimension=dimension,
                        status="unknown",
                        quote=None,
                        rationale="DEMO recorded history fixture, no fresh discovery claim",
                    )
                    for dimension in (
                        "product",
                        "customer",
                        "geography",
                        "price",
                        "channel",
                    )
                ),
                score=0,
                known_dimensions=0,
                rationale="DEMO history fixture identity; not an evaluated discovery ranking",
            )
        )
    pack = EvidencePack(
        run_id=run_id, as_of=at, competitors=tuple(competitors), research=tuple(lanes)
    )
    analysis = analyze(pack)
    shortlist = DiscoveryArtifact(
        discovery=Discovery(
            pool=tuple(candidates),
            candidates=tuple(candidates),
            excluded=(),
            insufficiency_reason=None,
        ),
        competitor_ids=tuple(c.candidate_id for c in candidates),
        insufficiency_reason=None,
    )
    brief = {
        "id": uuid5(run_id, "brief"),
        "owner_id": UUID(int=9020),
        "version": 1,
        "created_at": at,
        "category": "DEMO handmade soap",
        "geography": "DEMO India",
        "customer": "DEMO buyer",
        "objective": "DEMO dated comparison",
        "known_competitors": [],
        "preferences": {},
    }
    rows = [
        {
            key: getattr(s, key)
            for key in (
                "competitor_id",
                "canonical_url",
                "title",
                "publisher",
                "retrieved_at",
                "content_hash",
                "access_status",
                "evidence_kind",
                "excerpt",
            )
        }
        | {"id": s.source_id}
        for lane in lanes
        for s in lane.sources
    ]
    doc = snapshot(brief, analysis, rows, shortlist.model_dump(mode="json"))
    result = review(pack, analysis)
    view = ReportView(
        id=uuid5(run_id, "report:1"),
        version=1,
        content_hash=digest(doc.model_dump(mode="json")),
        created_at=at,
        snapshot=doc,
        review=result,
        approval=ApprovalView(
            state="saved",
            artifact_version=1,
            artifact_hash=digest(doc.model_dump(mode="json")),
        ),
        export_allowed=True,
        projection="persisted",
    )
    return view, version_meta({"id": run_id}, view)
