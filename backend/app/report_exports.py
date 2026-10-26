"""Approved snapshot downloads only. Escaped HTML and formula-safe structured CSV."""
import csv
from html import escape
from io import StringIO
import json

from fastapi import HTTPException

from app.report_types import ReportView


def csv_text(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        text = "'" + text
    return text


def export_report(report: ReportView, format: str) -> str:
    if not report.export_allowed or report.snapshot is None or report.approval.state != "saved" or report.review is None or report.review.decision != "ready_for_human":
        raise HTTPException(409, "approved_saved_report_required")
    document = report.snapshot
    analysis = document.analysis
    if format == "csv":
        stream = StringIO(newline="")
        columns = ["section", "report_id", "version", "content_hash", "label", "as_of", "competitor_id", "field", "kind", "value", "source_ids", "details"]
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
        writer.writeheader()
        base = {"report_id": str(report.id), "version": str(report.version), "content_hash": report.content_hash, "label": document.label, "as_of": analysis.as_of.isoformat()}
        def row(section, **values):
            writer.writerow({key: csv_text(value) for key, value in (base | {"section": section} | values).items()})
        row("cover", value=document.summary, details=document.scope)
        row("coverage", value=document.coverage.model_dump(mode="json"), details="Citation diagnostics only; genuine support not adjudicated.")
        row("approval", value=report.approval.model_dump(mode="json"))
        if document.live_narrative:
            row("live_model_narrative", kind="interpretation_and_hypotheses", value=document.live_narrative.model_dump(mode="json"), details="Provisional model; genuine support not human-adjudicated.")
        if document.shortlist:
            for candidate in document.shortlist.discovery.candidates:
                row("shortlist", competitor_id=str(candidate.candidate_id), value=candidate.name, source_ids=[str(sid) for sid in candidate.source_ids], details=candidate.model_dump(mode="json"))
        for finding in analysis.findings:
            row("finding", competitor_id=str(finding.competitor_id), field=finding.field, kind=finding.kind, value=finding.value,
                source_ids=[str(e.source_id) for e in finding.evidence], details=finding.model_dump(mode="json"))
        for price in analysis.normalized_prices:
            row("price", competitor_id=str(price.competitor_id), field="unit_price_100g", kind="calculation", value=str(price.unit_price_100g) if price.unit_price_100g is not None else "unavailable",
                source_ids=[str(price.source_id)], details=price.model_dump(mode="json"))
        for opportunity in analysis.opportunities:
            row("opportunity", field=opportunity.rule, kind="hypothesis", value=opportunity.title, details=opportunity.model_dump(mode="json"))
        for point in document.positioning:
            row("positioning", competitor_id=str(point.competitor_id), kind="interpretation", value=point.model_dump(mode="json"))
        for source in document.sources:
            row("source", value=source.title, source_ids=[str(source.id)], details=source.model_dump(mode="json"))
        for issue in report.review.issues if report.review else ():
            row("issue", field=issue.code, value=issue.explanation, details=issue.model_dump(mode="json"))
        for limit in analysis.limitations:
            row("limitation", value=limit)
        return stream.getvalue()
    if format != "html":
        raise HTTPException(422, "unsupported_export_format")
    def e(value):
        return escape(str(value), quote=True)
    source_ids = {source.id for source in document.sources}
    def citations(finding):
        return " ".join(f'<a href="#source-{e(ref.source_id)}">[{e(str(ref.source_id)[:8])}]</a>' for ref in finding.evidence if ref.source_id in source_ids)
    chunks = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
        '<title>Lather Lens — approved report</title><style>body{font:16px/1.6 system-ui;margin:0;color:#14231d;background:#f3f1ea}main{max-width:1100px;margin:auto;padding:32px}header{background:#14231d;color:#c6ef6b;padding:32px}section{margin:32px 0}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:10px;text-align:left;vertical-align:top}pre,blockquote,td{white-space:pre-wrap;overflow-wrap:anywhere}article{background:white;padding:20px;margin:16px 0;border-radius:16px}a{color:#24604f}small{overflow-wrap:anywhere}</style>',
        f'<header><p>{e(document.label)} · Approved saved snapshot · v{report.version}</p><h1>Lather Lens competitor briefing</h1><p>{e(document.brief.category)} · {e(document.brief.geography)}</p></header><main>',
        f'<p>Report {e(report.id)} · SHA-256 {e(report.content_hash)} · as of {e(analysis.as_of.isoformat())}</p>',
        f'<section><h2>Executive summary</h2><p>{e(document.summary)}</p><h2>Scope and methodology</h2><p>{e(document.scope)}</p><p>{"Recorded evidence, deterministic analysis and independent mechanical review; no model selected." if document.label == "DEMO" else "Live retrieved evidence, provisional model-assisted synthesis and independent deterministic review. Model benchmark not completed."}</p></section>',
        f'<section><h2>Source coverage</h2><p>{document.coverage.intact_quotes}/{document.coverage.material_facts} material factual/attributed findings have intact source excerpts. Genuine support: not adjudicated.</p><p>{e(document.coverage.denominator_definition)}</p></section>',
        '<section><h2>Review flags</h2><ul>']
    chunks.extend(f'<li>{e(issue.severity)} · {e(issue.code)}: {e(issue.explanation)}</li>' for issue in report.review.issues if report.review)
    chunks.append('</ul></section><section><h2>Shortlist and rationale</h2><ul>')
    if document.shortlist:
        chunks.extend(f'<li>{e(candidate.name)}: {e(candidate.rationale)}</li>' for candidate in document.shortlist.discovery.candidates)
    chunks.append('</ul></section><section><h2>Competitor comparison</h2>')
    findings = {f.finding_id: f for f in analysis.findings}
    for competitor in analysis.comparisons:
        chunks.append(f'<article><h3>{e(competitor.name)}</h3><table><thead><tr><th>Field</th><th>Observations</th></tr></thead><tbody>')
        for field in competitor.fields:
            values = [findings[key] for key in field.finding_ids if key in findings and findings[key].value is not None]
            content = '<br>'.join('<strong>' + e(finding.kind) + '</strong>: ' + e(finding.text) + ' ' + citations(finding) for finding in values) or e(field.unavailable_reason or "Unavailable")
            chunks.append(f'<tr><th>{e(field.field)}</th><td>{content}</td></tr>')
        chunks.append('</tbody></table></article>')
    chunks.append('</section><section><h2>Price per 100g</h2><table><tr><th>Competitor / SKU</th><th>Listed price / total weight</th><th>Normalized price</th><th>Observed</th></tr>')
    names = {c.competitor_id: c.name for c in analysis.comparisons}
    for price in analysis.normalized_prices:
        value = f'{price.currency} {price.unit_price_100g} /100g' if price.unit_price_100g is not None else 'Unavailable: ' + (price.unavailable_reason or 'unknown basis')
        chunks.append(f'<tr><td>{e(names.get(price.competitor_id, "Unknown"))} · {e(price.sku or "SKU unavailable")}</td><td>{e(price.amount)} {e(price.currency)} / {e(price.total_weight_g or "unknown")} g</td><td>{e(value)} <a href="#source-{e(price.source_id)}">Source</a></td><td>{e(price.observed_at.isoformat())}</td></tr>')
    chunks.append('</table><p>Different products and dated observations; no FX conversion or inferred weights.</p></section><section><h2>Positioning 2×2 interpretation</h2><ul>')
    chunks.extend(f'<li>{e(names.get(point.competitor_id))}: {e(point.x or "x unavailable")} / {e(point.y or "y unavailable")}. {e(point.explanation)} {" ".join(citations(findings[key]) for key in point.premise_ids if key in findings)}</li>' for point in document.positioning)
    chunks.append('</ul></section><section><h2>Opportunities — hypotheses to test</h2>')
    for opportunity in analysis.opportunities:
        chunks.append(f'<article><h3>{e(opportunity.title)}</h3><p>{e(opportunity.rationale)}</p><p>Potential benefit: {e(opportunity.potential_benefit)}</p><p>Assumptions: {e("; ".join(opportunity.assumptions))}</p><p>Next: {e(opportunity.next_step)}</p><ul>')
        chunks.extend(f'<li>{e(findings[key].text)} {citations(findings[key])}</li>' for key in opportunity.evidence_finding_ids if key in findings)
        chunks.append('</ul><p>' + e(opportunity.caveat) + '</p></article>')
    if analysis.insufficiency_reason:
        chunks.append(f'<p>{e(analysis.insufficiency_reason)}</p>')
    if document.live_narrative:
        narrative = document.live_narrative
        chunks.append(f'<section><h2>Live model-assisted briefing</h2><p>{e(narrative.provider)} / {e(narrative.model)}. Provisional profile; no completed quality benchmark.</p><p>{e(narrative.synthesis.summary)}</p>')
        for note in narrative.synthesis.notes:
            refs = ' '.join(f'<a href="#source-{e(sid)}">Source</a>' for sid in note.source_ids)
            chunks.append(f'<p><strong>{e(note.kind)}</strong>: {e(note.text)} {refs}</p>')
        for idea in narrative.synthesis.opportunities:
            chunks.append(f'<article><h3>Hypothesis: {e(idea.title)}</h3><p>{e(idea.rationale)}</p><p>Assumptions: {e("; ".join(idea.assumptions))}</p><p>Next step: {e(idea.next_step)}</p><ul>')
            chunks.extend(f'<li>{e(findings[fid].text)} {citations(findings[fid])}</li>' for fid in idea.premise_finding_ids if fid in findings)
            chunks.append('</ul></article>')
        chunks.append(f'<p>Independent model critique: {e(narrative.critique.decision)}. Genuine support remains unadjudicated by a human.</p></section>')
    chunks.append('</section><section><h2>Gaps and limitations</h2><ul>')
    chunks.extend(f'<li>{e(limit)}</li>' for limit in analysis.limitations)
    chunks.append('</ul></section><section><h2>Dated sources and evidence</h2>')
    for source in document.sources:
        title = f'<a href="{e(source.canonical_url)}" rel="noopener noreferrer">{e(source.title)}</a>' if source.canonical_url else e(source.title)
        chunks.append(f'<article id="source-{e(source.id)}"><h3>{title}</h3><small>{e(source.publisher)} · retrieved {e(source.retrieved_at.isoformat())} · {e(source.access_status)} · hash {e(source.content_hash)}</small>')
        quotes = {(ref.quote, ref.locator) for finding in analysis.findings for ref in finding.evidence if ref.source_id == source.id}
        chunks.extend(f'<blockquote>{e(quote)}<small> · {e(locator)}</small></blockquote>' for quote, locator in sorted(quotes))
        chunks.append('</article>')
    chunks.append('</section></main></html>')
    return ''.join(chunks)
