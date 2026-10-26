"""Read-only version history and conservative dated evidence comparisons. No I/O tools."""
from collections import defaultdict
from datetime import timedelta
from hashlib import sha256
import json
import unicodedata
from urllib.parse import urlsplit
from uuid import UUID, NAMESPACE_URL, uuid5

from fastapi import HTTPException
from sqlalchemy import select, func

from app import models as m
from app.harness.urls import normalize_url
from app.history_types import ChangeKind, DatedEvidence, HistoricalChange, HistoricalValue, HistoricalVersion, HistoryDiff, VersionList
from app.report_types import ReportSnapshot, ReportView
from app.reporting import report_view

FIELDS = {"product", "product_type", "ingredients", "marketing_claim", "positioning", "audience", "channels", "packaging", "public_review", "reported_launch", "availability", "weight_g", "pack_qty", "weight_basis"}
DISCONTINUED = {"Discontinued", "https://schema.org/Discontinued", "http://schema.org/Discontinued"}


def stable_brand(name: str, url: str) -> tuple[UUID, str]:
    canonical, _ = normalize_url(url, demo=True)
    host = urlsplit(canonical).hostname or ""
    host = host.removeprefix("www.")
    # Shared store hosts are not a reason to merge differently named brands.
    key = host + "|" + " ".join(unicodedata.normalize("NFC", name).casefold().split())
    return uuid5(NAMESPACE_URL, "lather:brand:1:" + key), host


def stable_product(brand: UUID, sku: str, variant: str | None) -> UUID:
    # Case-sensitive source SKU; do not infer identity from display name or price.
    return uuid5(brand, json.dumps(["product:1", unicodedata.normalize("NFC", sku.strip()), variant], ensure_ascii=False))


def version_meta(run: dict, view: ReportView) -> HistoricalVersion:
    return HistoricalVersion(report_id=view.id, run_id=run["id"], version=view.version, content_hash=view.content_hash,
        created_at=view.created_at, as_of=view.snapshot.analysis.as_of if view.snapshot else None,
        approval=view.approval.state, comparable=view.snapshot is not None and view.export_allowed,
        label=view.snapshot.label if view.snapshot else None)


def versions(repo, run_id: UUID, limit: int = 100, offset: int = 0) -> VersionList:
    run = repo.get(m.runs, run_id)
    rows = repo.conn.execute(select(m.reports).where(m.reports.c.owner_id == repo.owner, m.reports.c.run_id == run_id)
        .order_by(m.reports.c.version.desc()).limit(limit).offset(offset)).mappings()
    total = repo.conn.execute(select(func.count()).select_from(m.reports).where(m.reports.c.owner_id == repo.owner, m.reports.c.run_id == run_id)).scalar_one()
    entries = []
    for row in rows:
        try:
            entries.append(version_meta(run, report_view(repo, run, dict(row))))
        except HTTPException as error:
            if error.status_code != 409:
                raise
            # Preserve metadata without exposing corrupted contents or hiding valid siblings.
            entries.append(HistoricalVersion(report_id=row["id"], run_id=run_id, version=row["version"], content_hash=row["content_hash"],
                created_at=row["created_at"], as_of=None, approval="integrity_error", comparable=False, label="DEMO" if row["data"].get("label") == "DEMO" else None))
    return VersionList(entries=entries, total=total)


def exact_report(repo, run_id: UUID, version: int) -> dict:
    repo.get(m.runs, run_id)
    row = repo.conn.execute(select(m.reports).where(m.reports.c.owner_id == repo.owner, m.reports.c.run_id == run_id,
        m.reports.c.version == version)).mappings().first()
    if row is None:
        raise HTTPException(404, "report_version_not_found")
    return dict(row)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _index(document: ReportSnapshot):
    """Rebuild stable keys from the frozen presentation only, never current DB metadata."""
    source_map = {s.id: s for s in document.sources}
    candidates = {c.candidate_id: c for c in document.shortlist.discovery.candidates} if document.shortlist else {}
    brands = {}
    for competitor in document.analysis.comparisons:
        candidate = candidates.get(competitor.competitor_id)
        try:
            if candidate is None:
                continue
            bid, host = stable_brand(candidate.name, candidate.canonical_url)
            brands[competitor.competitor_id] = (bid, host, candidate.name)
        except ValueError:
            continue
    products = {}
    for price in document.analysis.normalized_prices:
        brand = brands.get(price.competitor_id)
        if brand and price.sku:
            products[price.competitor_id, price.source_id, price.locator] = (stable_product(brand[0], price.sku, price.variant), price.sku)
    rows: dict[tuple, list] = defaultdict(list)
    unknown_identities = set()
    def append(cid, sid, locator, field, value, kind, refs, *, price=False):
        brand = brands.get(cid)
        identity = products.get((cid, sid, locator)) if locator else None
        if brand is None or (locator and identity is None):
            unknown_identities.add((cid, sid, locator))
            return
        key = brand[0], identity[0] if identity else None, field
        evidence = []
        valid = value is not None and bool(refs)
        for ref in refs:
            source = source_map.get(ref.source_id)
            usable = (source is not None and source.competitor_id == cid and source.access_status == "ok" and source.evidence_kind == "page_excerpt"
                and source.canonical_url is not None and source.excerpt is not None and ref.quote in source.excerpt
                and sha256(ref.quote.encode()).hexdigest() == ref.quote_hash)
            if source:
                evidence.append(DatedEvidence(source=source, quote=ref.quote, quote_hash=ref.quote_hash, locator=ref.locator))
            valid = valid and usable
        if price:
            valid = valid and bool(value and value.get("unit_price_100g") is not None)
        rows[key].append({"value": value, "kind": kind, "evidence": evidence, "valid": bool(valid), "brand": brand[2], "product": identity[1] if identity else None})
    for finding in document.analysis.findings:
        if finding.field in FIELDS and finding.kind in {"fact", "source_claim"}:
            append(finding.competitor_id, finding.source_id, finding.product_locator, finding.field, finding.value, finding.kind, finding.evidence)
    for price in document.analysis.normalized_prices:
        value = {"amount": format(price.amount.normalize(), "f") if price.amount is not None else None, "currency": price.currency,
            "total_weight_g": format(price.total_weight_g.normalize(), "f") if price.total_weight_g is not None else None, "pack_qty": price.pack_qty,
            "unit_price_100g": format(price.unit_price_100g.normalize(), "f") if price.unit_price_100g is not None else None}
        append(price.competitor_id, price.source_id, price.locator, "price", value, "fact", price.evidence, price=True)
    # All known failure records remain available even if no product/field extracted.
    domains = {brand[0]: (brand[1], cid) for cid, brand in brands.items()}
    return rows, domains, unknown_identities


def _value(rows: list, document: ReportSnapshot, freshness_days: int) -> HistoricalValue:
    evidence = {canonical(ref.model_dump(mode="json")): ref for row in rows for ref in row["evidence"]}
    values = {canonical(row["value"]): row["value"] for row in rows if row["value"] is not None}
    refs = tuple(evidence[key] for key in sorted(evidence))
    fresh = bool(refs) and all(ref.source.retrieved_at.utcoffset() is not None and document.analysis.as_of - timedelta(days=freshness_days) <= ref.source.retrieved_at <= document.analysis.as_of for ref in refs)
    valid = bool(rows) and all(row["valid"] for row in rows) and len(values) == 1 and fresh
    reason = None if valid else "not_observed" if not rows else "conflicting_evidence" if len(values) > 1 else "stale_evidence" if refs and not fresh else "unavailable_or_unverified_evidence"
    return HistoricalValue(values=tuple(values[key] for key in sorted(values)), evidence=refs, kinds=tuple(sorted({row["kind"] for row in rows})), usable=valid, reason=reason)


def _brand_capture(document: ReportSnapshot, brand, freshness_days: int) -> tuple[DatedEvidence, ...]:
    if brand is None:
        return ()
    host, cid = brand
    return tuple(DatedEvidence(source=s) for s in document.sources if s.competitor_id == cid and s.canonical_url
        and (urlsplit(s.canonical_url).hostname or "").removeprefix("www.") == host
        and s.evidence_kind == "page_excerpt" and s.access_status == "ok" and s.content_hash
        and s.retrieved_at.utcoffset() is not None
        and document.analysis.as_of - timedelta(days=freshness_days) <= s.retrieved_at <= document.analysis.as_of)


def _price_context(value: HistoricalValue) -> set[str]:
    try:
        return {normalize_url(ref.source.canonical_url, demo=True)[0] for ref in value.evidence if ref.source.canonical_url}
    except ValueError:
        return set()


def compare(before: ReportView, after: ReportView, before_meta: HistoricalVersion, after_meta: HistoricalVersion) -> HistoryDiff:
    if not before.export_allowed or not after.export_allowed or before.snapshot is None or after.snapshot is None:
        raise HTTPException(409, "approved_saved_versions_required")
    old, new = before.snapshot, after.snapshot
    if old.analysis.as_of.utcoffset() is None or new.analysis.as_of.utcoffset() is None:
        raise HTTPException(409, "dated_reports_required")
    if old.analysis.run_id == new.analysis.run_id or old.analysis.as_of >= new.analysis.as_of:
        raise HTTPException(409, "distinct_chronological_runs_required")
    if any(" ".join(getattr(old.brief, key).casefold().split()) != " ".join(getattr(new.brief, key).casefold().split()) for key in ("category", "geography", "customer")):
        raise HTTPException(409, "incompatible_research_scope")
    days = 30  # Versioned comparison policy, not a changed BRD acceptance target.
    earlier, old_brands, old_unknown = _index(old)
    later, new_brands, new_unknown = _index(new)
    changes = []
    for key in sorted(set(earlier) | set(later), key=lambda key: tuple(str(v) for v in key)):
        bid, pid, field = key
        old_rows, new_rows = earlier.get(key, []), later.get(key, [])
        previous, current = _value(old_rows, old, days), _value(new_rows, new, days)
        status: ChangeKind = "unknown"
        reason = current.reason or previous.reason or "not_comparable"
        captures = _brand_capture(old, old_brands.get(bid), days)
        if not previous.usable and not old_rows and current.usable and captures:
            status, reason = "new", "newly_observed_in_sample_not_proven_launch"
        elif previous.usable and current.usable:
            old_value, new_value = previous.values[0], current.values[0]
            if field == "price" and (not isinstance(old_value, dict) or not isinstance(new_value, dict) or any(old_value.get(k) != new_value.get(k) for k in ("currency", "pack_qty", "total_weight_g"))):
                reason = "currency_or_purchase_basis_changed"
            elif field == "price" and (not _price_context(previous) or _price_context(previous) != _price_context(current)):
                reason = "source_or_offer_context_changed"
            else:
                status, reason = ("unchanged", "same_observed_values") if previous.values == current.values else ("changed", "source_observations_changed")
                if field == "availability" and previous.values != current.values and isinstance(current.values[0], str) and current.values[0] in DISCONTINUED:
                    captures = _brand_capture(new, new_brands.get(bid), days)
                    if captures and all(ref.source in [capture.source for capture in captures] for ref in current.evidence):
                        status, reason = "gone", "first_party_source_reports_discontinued_not_independent_verification"
        if status in {"new", "changed", "gone", "unchanged"} and any(ref.source.retrieved_at <= old.analysis.as_of for ref in current.evidence):
            status, reason = "stale", "not_rechecked_after_earlier_report"
        if status == "unknown" and (current.reason == "stale_evidence" or (previous.usable and not current.usable and new.analysis.as_of - old.analysis.as_of > timedelta(days=days))):
            status, reason = "stale", "old_observation_not_reconfirmed"
        if not current.usable:
            cid = new_brands.get(bid, (None, None))[1]
            failed = tuple(DatedEvidence(source=s) for s in new.sources if s.competitor_id == cid and s.access_status != "ok")
            if failed:
                current = current.model_copy(update={"evidence": current.evidence + failed, "reason": "retrieval_gap"})
                reason = "retrieval_gap_not_discontinued" if status != "stale" else "old_observation_stale_retrieval_gap"
        title = (new_rows or old_rows)[0]
        color_order = list(new_brands) if bid in new_brands else list(old_brands)
        changes.append(HistoricalChange(change_id=uuid5(bid, canonical([str(before.id), str(after.id), str(pid), field])), brand_id=bid,
            product_id=pid, brand=title["brand"], product=title["product"], color_index=color_order.index(bid), field=field, status=status, reason=reason, before=previous, after=current))
    for side, identities in (("earlier", old_unknown), ("later", new_unknown)):
        for cid, sid, locator in sorted(identities, key=str):
            document = old if side == "earlier" else new
            missing = HistoricalValue(evidence=tuple(DatedEvidence(source=s) for s in document.sources if s.id == sid), reason="identity_unavailable")
            changes.append(HistoricalChange(change_id=uuid5(NAMESPACE_URL, f"history-unknown:{before.id}:{after.id}:{side}:{cid}:{sid}:{locator}"),
                brand_id=None, product_id=None, brand="Unmatched recorded identity", product=None, field="identity", status="unknown",
                reason=f"{side}_brand_or_sku_identity_unavailable_no_name_fuzzy_match", before=missing if side == "earlier" else HistoricalValue(), after=missing if side == "later" else HistoricalValue()))
    return HistoryDiff(before=before_meta, after=after_meta, changes=tuple(changes), counts={kind: sum(row.status == kind for row in changes)
        for kind in ("new", "changed", "gone", "unchanged", "unknown", "stale")}, limitations=(
            "Only exact host/name brand identities and case-sensitive SKU/variant identities are matched; rebrands/domain moves require reviewed aliases.",
            "New counts newly observed fields within sampled evidence, not market entry or launch. Missing pages/omissions never prove discontinuation.",
            "Price comparisons require unchanged currency, known same-item weight and pack basis; conflicting observations remain unknown.",
            "All captures are dated history, not assertions of present-day availability. Quote integrity is not genuine semantic support adjudication.",
            "30-day freshness is a versioned proposed policy. Comparisons read immutable approved snapshots and never fetch or rewrite evidence."))


def diff(repo, before_run: UUID, after_run: UUID, before_version: int, after_version: int) -> HistoryDiff:
    # Check BOTH run owners before loading any report content.
    old_run, new_run = repo.get(m.runs, before_run), repo.get(m.runs, after_run)
    before = report_view(repo, old_run, exact_report(repo, before_run, before_version))
    after = report_view(repo, new_run, exact_report(repo, after_run, after_version))
    return compare(before, after, version_meta(old_run, before), version_meta(new_run, after))
