"""Explicit sanitized export to an already configured LangSmith project; off by default."""
import argparse
import json
from pathlib import Path

from app.evaluations.telemetry import ExportSettings, SafeTrace, export_langsmith


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    settings = ExportSettings()
    if not settings.enabled or not settings.export_approved:
        raise SystemExit("LangSmith export is disabled; separate explicit authorization and an existing project are required.")
    value = json.loads(args.input.read_text(encoding="utf8"))
    if value.get("schema_version") != "sanitized-trace-batch-1.0":
        raise ValueError("sanitized_trace_batch_required")
    traces = tuple(SafeTrace.model_validate(trace) for trace in value["traces"])
    if sum(1 + len(trace.steps) for trace in traces) > settings.max_runs:
        raise SystemExit("Trace batch exceeds the approved run cap; nothing exported.")
    for trace in traces:
        export_langsmith(trace, settings)
    print(f"Exported {len(traces)} sanitized trace(s); no raw research content transmitted")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Trace export failed ({type(error).__name__}); no input/credential details emitted.") from None
