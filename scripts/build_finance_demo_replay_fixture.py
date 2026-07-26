"""Build the distributable AAPL demo replay from a persisted real Finance Case.

The original source bundle contains complete raw SEC payloads.  The checked-in
fixture keeps the exact source provenance plus only the filing rows and XBRL
facts selected by the Finance Dataset Builder, so the demo remains small while
reconstructing the same evidence-bound dataset without network access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from rogueskills.domain.case_validation import canonical_digest
from rogueskills.domain.finance_case import (
    FLOW_TAGS,
    POINT_TAGS,
    _annual_records,
    _point_record,
    _quarter_record,
    build_finance_dataset,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = PROJECT_ROOT / "artifacts" / "finance-e2e-20260722" / "prior-real.db"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "backend" / "rogueskills" / "domain" / "data" / "finance-demo-aapl.json"
)
DEFAULT_SOURCE_CASE_ID = "finance-case-6266b782a74c416ea985aa35031aee9d"


def _database_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _selected_facts(bundle: dict[str, Any]) -> dict[str, Any]:
    source = bundle["companyFacts"]
    as_of_date = str(bundle["asOfDate"])
    selected: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def add(record: dict[str, Any] | None) -> None:
        if record is None:
            return
        normalized = dict(record)
        namespace = str(normalized.pop("namespace"))
        tag = str(normalized.pop("tag"))
        unit = str(normalized.pop("unit"))
        values = selected.setdefault((namespace, tag, unit), [])
        if normalized not in values:
            values.append(normalized)

    for tags in FLOW_TAGS.values():
        for record in _annual_records(source, tags, as_of_date):
            add(record)
        add(_quarter_record(source, tags, as_of_date))
    for candidates in POINT_TAGS.values():
        add(_point_record(source, candidates, as_of_date))

    facts: dict[str, dict[str, Any]] = {}
    for (namespace, tag, unit), values in sorted(selected.items()):
        fact = facts.setdefault(namespace, {}).setdefault(tag, {"units": {}})
        fact["units"][unit] = values
    return {
        "cik": source.get("cik"),
        "entityName": source.get("entityName"),
        "facts": facts,
    }


def _selected_submissions(bundle: dict[str, Any]) -> dict[str, Any]:
    source = bundle["submissions"]
    recent = (source.get("filings") or {}).get("recent") or {}
    keys = ("accessionNumber", "filingDate", "form", "reportDate", "primaryDocument")
    rows: list[dict[str, str]] = []
    for index, accession in enumerate(recent.get("accessionNumber") or []):
        row = {key: str((recent.get(key) or [""] * (index + 1))[index]) for key in keys}
        row["accessionNumber"] = str(accession)
        if row["filingDate"] <= str(bundle["asOfDate"]) and row["form"] in {"10-K", "10-Q"}:
            rows.append(row)
        if len(rows) == 4:
            break
    return {
        "cik": source.get("cik"),
        "name": source.get("name"),
        "filings": {
            "recent": {key: [row[key] for row in rows] for key in keys},
        },
    }


def build_fixture(source_db: Path, source_case_id: str) -> dict[str, Any]:
    with sqlite3.connect(source_db) as connection:
        row = connection.execute(
            "SELECT state_json, source_bundle_json FROM finance_case_runs WHERE id = ?",
            (source_case_id,),
        ).fetchone()
    if row is None or row[1] is None:
        raise ValueError(f"Persisted real Finance Case not found: {source_case_id}")
    state = json.loads(row[0])
    original = json.loads(row[1])
    compact_bundle = {
        "company": original["company"],
        "asOfDate": original["asOfDate"],
        "sources": original["sources"],
        "submissions": _selected_submissions(original),
        "companyFacts": _selected_facts(original),
        "market": original.get("market"),
        "warnings": original.get("warnings", []),
    }
    dataset = build_finance_dataset(compact_bundle)
    return {
        "schemaVersion": "demo-finance-replay-fixture-v1",
        "id": "demo-finance-aapl-2026-07-21",
        "displayName": "Apple AAPL 公开财务分析",
        "description": "SEC EDGAR 申报、Company Facts 与截至日市场价格的真实持久化快照。",
        "sourceCaseId": source_case_id,
        "sourceMode": "live",
        "input": {"ticker": "AAPL", "asOfDate": "2026-07-21"},
        "capturedAt": state.get("completedAt") or state.get("createdAt"),
        "sourceDatabaseDigest": _database_digest(source_db),
        "originalSourceBundleDigest": canonical_digest(original),
        "sourceBundleDigest": canonical_digest(compact_bundle),
        "datasetDigest": canonical_digest(dataset),
        "originalRuntimeVerification": {
            "runtimeVerified": bool(state.get("runtimeVerified", False)),
            "score": (state.get("finalEvaluation") or {}).get("score"),
            "completedAt": state.get("completedAt"),
        },
        "datasetSummary": {
            "company": dataset["company"],
            "sourceCount": len(dataset["sources"]),
            "factCount": len(dataset["facts"]),
            "derivedMetricCount": len(dataset["derivedMetrics"]),
            "filingCount": len(dataset["filings"]),
        },
        "sourceBundle": compact_bundle,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", default=str(DEFAULT_SOURCE_DB))
    parser.add_argument("--source-case-id", default=DEFAULT_SOURCE_CASE_ID)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    source_db = Path(args.source_db).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    fixture = build_fixture(source_db, args.source_case_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "bytes": output.stat().st_size,
                "datasetSummary": fixture["datasetSummary"],
                "sourceBundleDigest": fixture["sourceBundleDigest"],
                "datasetDigest": fixture["datasetDigest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
