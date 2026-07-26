from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from pydantic import ValidationError

from rogueskills.contracts.case_validation import CaseValidationState
from rogueskills.domain.case_validation import validation_idempotency_key
from rogueskills.domain.catalogs import SEED_SKILLS
from rogueskills.domain.genome import validate_skill_genome


def _state() -> dict[str, object]:
    return {
        "schemaVersion": "1.0.0",
        "id": "case-validation-contract",
        "idempotencyKey": "sha256:" + "a" * 64,
        "sourceRunId": "run-contract",
        "candidatePresetId": "preset-contract",
        "candidatePresetDigest": "sha256:" + "b" * 64,
        "casePackId": "finance-stock-analysis",
        "casePackVersion": "1.0.0",
        "mode": "verified_replay",
        "replayCaseId": "case-run-contract",
        "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
        "skillId": "skill-contract",
        "baseSkillVersionId": "skill-contract@1",
        "status": "queued",
        "phase": "queued",
        "createdAt": "2026-07-25T00:00:00Z",
    }


def test_case_validation_contract_rejects_unknown_phase_and_invalid_digest() -> None:
    state = _state()
    assert CaseValidationState.model_validate(state).phase == "queued"

    invalid_phase = {**state, "phase": "doing_something_undefined"}
    with pytest.raises(ValidationError):
        CaseValidationState.model_validate(invalid_phase)

    invalid_digest = {**state, "candidatePresetDigest": "sha256:not-a-digest"}
    with pytest.raises(ValidationError):
        CaseValidationState.model_validate(invalid_digest)


def test_idempotency_key_locks_source_bundle_and_execution_policy() -> None:
    common = {
        "source_run_id": "run-contract",
        "preset_digest": "sha256:" + "b" * 64,
        "case_pack_ref": "finance-stock-analysis@1.0.0",
        "replay_case_id": "case-run-contract",
        "case_input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
        "source_bundle_digest": "sha256:" + "c" * 64,
        "execution_policy_digest": "sha256:" + "d" * 64,
    }
    original = validation_idempotency_key(**common)
    assert original == validation_idempotency_key(**common)
    assert original != validation_idempotency_key(
        **{**common, "source_bundle_digest": "sha256:" + "e" * 64}
    )
    assert original != validation_idempotency_key(
        **{**common, "execution_policy_digest": "sha256:" + "f" * 64}
    )


def test_runtime_binding_schema_matches_python_validator() -> None:
    genome = deepcopy(SEED_SKILLS[0])
    genome["runtimeBinding"] = {
        "contractVersion": "1.0.0",
        "kind": "agent-preset",
        "presetId": "preset-contract",
        "presetDigest": "sha256:" + "b" * 64,
        "validationId": "case-validation-contract",
    }
    genome["runtimeVerification"] = {
        "runtimeVerified": True,
        "casePackId": "finance-stock-analysis",
        "casePackVersion": "1.0.0",
        "caseId": "case-run-contract",
        "evaluationId": "finance-eval-contract",
        "sourceDigest": "sha256:" + "c" * 64,
        "datasetDigest": "sha256:" + "d" * 64,
        "verifiedAt": "2026-07-25T00:00:00Z",
    }
    schema = json.loads(
        (Path(__file__).parents[2] / "src/contracts/skill-genome.schema.json").read_text()
    )

    assert validate_skill_genome(genome)["valid"] is True
    validate(instance=genome, schema=schema)

    genome["runtimeBinding"]["presetDigest"] = "invalid"
    assert validate_skill_genome(genome)["valid"] is False
    with pytest.raises(JsonSchemaValidationError):
        validate(instance=genome, schema=schema)
