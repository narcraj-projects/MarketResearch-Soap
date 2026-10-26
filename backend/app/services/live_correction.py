"""User-requested extractive correction; a fresh independent review is mandatory."""

from copy import deepcopy
from uuid import UUID

from app import models as m
from app.harness.live_types import (
    EvidenceNote,
    LiveCritique,
    LiveNarrative,
    LiveSynthesis,
)
from app.harness.policy import PolicyDenied


def corrected_draft(workflow, state):
    with workflow.transaction() as repo:
        prior = repo.report(workflow.lease.run_id)
        if prior["version"] != 3:
            raise PolicyDenied("manual_correction_version_mismatch")
        run = repo.get(m.runs, workflow.lease.run_id)
        if (
            run["checkpoint"].get("live_manual_correction", {}).get("prior_hash")
            != prior["content_hash"]
        ):
            raise PolicyDenied("manual_correction_authorization_missing")
        if str(state.manual_correction_request) != run["checkpoint"][
            "live_manual_correction"
        ].get("request_id"):
            raise PolicyDenied("manual_correction_reference_mismatch")
        sources = {
            str(row["id"]): row
            for row in repo.list(m.sources, workflow.lease.run_id, limit=1000)
        }
    data = deepcopy(prior["data"])
    original = LiveSynthesis.model_validate(data["live_narrative"]["synthesis"])
    # Remove problematic price ranges, promotion-date summaries and inferred gaps.
    # Retain the other attributed notes, then add literal listing excerpts.
    notes = [note for index, note in enumerate(original.notes) if index in {0, 2, 3, 4}]

    def listing(candidate_ids, keyword):
        source_id = next(
            (
                str(sid)
                for sid in candidate_ids
                if keyword.casefold() in (sources[str(sid)]["excerpt"] or "").casefold()
            ),
            None,
        )
        if source_id is None:
            raise PolicyDenied("manual_correction_evidence_missing")
        source = sources[source_id]
        text = source["excerpt"] or ""
        start = max(0, text.casefold().find(keyword.casefold()))
        quote = text[start : start + 650]
        if not quote or source["access_status"] != "ok":
            raise PolicyDenied("manual_correction_evidence_missing")
        return EvidenceNote(
            text="Verbatim search-listing excerpt (attributed, not independently verified): "
            + quote,
            source_ids=(UUID(source_id),),
            kind="source_claim",
        )

    notes.append(listing(original.notes[1].source_ids, "Turmeric"))
    notes.append(listing(original.notes[5].source_ids, "Luxury Sugar Soap"))
    synthesis = LiveSynthesis(
        summary="This dated snapshot compares Fika Soaps and Forest Essentials using retained public evidence. "
        "Notes below attribute the source wording. Incomplete purchase-item bindings limit price normalization. "
        "The sampled evidence does not establish an unoccupied market segment or proven customer demand.",
        notes=tuple(notes),
        opportunities=(),
        limitations=(
            "Search snippets are incomplete snapshots, not independently verified catalog records.",
            "SKU, variant and pack bindings are not sufficient for price-per-100g normalization.",
            "No complete market price distribution, market share or representative customer feedback is established.",
            "Old promotional dates do not establish a current promotion.",
            "Efficacy and certification wording remains attributed marketing, not verified performance.",
            "Owner usefulness and genuine material-claim support have not been human adjudicated.",
        ),
        insufficiency_reason="The reviewed opportunity premises overstated sampled evidence. They were removed; three grounded opportunities could not be established in this run.",
    )
    ids = {str(sid) for note in synthesis.notes for sid in note.source_ids}
    evidence = [
        {
            "source_id": sid,
            "url": sources[sid]["canonical_url"],
            "excerpt": sources[sid]["excerpt"],
        }
        for sid in sorted(ids)
    ]
    critique = LiveCritique.model_validate(
        workflow.models.invoke(
            "reviewer",
            "Independently review this extractive correction. Check every retained note against its cited source. "
            "Source quotations are attributed claims, never verified efficacy. Missing opportunities are explicitly explained. "
            "Flag any wrong-source quote, unsupported fact or misleading statement. Return ready_for_human only when no material issue is identified.",
            {
                "synthesis": synthesis.model_dump(mode="json"),
                "source_excerpts": evidence,
            },
            LiveCritique.model_json_schema(),
        )
    )
    narrative = LiveNarrative(
        provider=workflow.permit.provider,
        model=workflow.permit.model,
        synthesis=synthesis,
        critique=critique,
    )
    data["revision"] = 3
    data["live_narrative"] = narrative.model_dump(mode="json")
    data["presentation"]["live_narrative"] = narrative.model_dump(mode="json")
    data["methodology"]["manual_correction"] = (
        "User-requested extractive pruning of v3; fresh independent model review; prior reports retained."
    )
    return data
