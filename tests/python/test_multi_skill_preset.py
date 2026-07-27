from copy import deepcopy
from datetime import UTC, datetime

import pytest

from rogueskills.adapters.agent_preset_loader import AgentPresetIntegrityError, load_agent_preset
from rogueskills.domain.catalogs import SEED_SKILLS
from rogueskills.domain.evolution import create_run
from rogueskills.domain.multi_skill import (
    InvalidMultiSkillPreset,
    compile_multi_skill_agent_preset,
)
from rogueskills.domain.presets import compile_agent_preset


def source_preset(skill_id: str, seed: str) -> tuple[dict, dict]:
    genome = deepcopy(SEED_SKILLS[0])
    genome["id"] = skill_id
    genome["name"] = skill_id
    genome["metadata"]["category"] = "finance"
    genome["provenance"]["fingerprint"] = f"fingerprint-{skill_id}"
    run = create_run(seed=seed, skill_genome=genome)
    run.update(
        {
            "status": "victory",
            "phase": "ended",
            "mutationIds": ["schema_validator", "injection_shield"],
            "evolutionIds": ["secure_browser"],
            "encounterHistory": [
                {"passed": True, "benchmarkId": "scenario-runtime-v1"},
            ],
        }
    )
    preset = compile_agent_preset(
        run=run,
        run_revision=7,
        base_skill_version_id=f"{skill_id}@1",
        base_skill_genome=genome,
        project_name=f"{skill_id} Agent",
        project_description=f"Evolved {skill_id} workflow.",
        scenario="public-company-financial-analysis",
        clock=lambda: datetime(2026, 7, 26, tzinfo=UTC),
    )
    return run, preset


def test_multi_skill_preset_compiles_routes_and_loads() -> None:
    primary_run, primary = source_preset("alphaear-signal-tracker-test", "MULTI-PRIMARY")
    _, stock = source_preset("alphaear-stock-test", "MULTI-STOCK")
    _, reporter = source_preset("alphaear-reporter-test", "MULTI-REPORTER")
    merge_run = deepcopy(primary_run)
    merge_run["id"] = "merge-run-aapl-test"
    routes = [
        {
            "id": "market-evidence",
            "order": 1,
            "when": "dated price or company facts are required",
            "useSkillRole": "market-data",
            "instruction": "Collect dated market evidence before analysis.",
            "fallbackSkillRole": "signal-tracking",
        },
        {
            "id": "report-synthesis",
            "order": 2,
            "when": "evidence-bound findings are ready",
            "useSkillRole": "report-synthesis",
            "instruction": "Assemble the final report without inventing facts.",
            "fallbackSkillRole": "signal-tracking",
        },
    ]

    merged = compile_multi_skill_agent_preset(
        merge_run=merge_run,
        merge_run_revision=1,
        primary_role="signal-tracking",
        primary_preset=primary,
        supporting_presets=[
            {"role": "market-data", "preset": stock},
            {"role": "report-synthesis", "preset": reporter},
        ],
        routing=routes,
        project_name="AAPL Multi-Skill Evidence Agent",
        project_description="Route market evidence into signal analysis and report synthesis.",
        scenario="AAPL verified replay",
        clock=lambda: datetime(2026, 7, 26, tzinfo=UTC),
    )

    assert merged["multiSkill"]["primaryRole"] == "signal-tracking"
    assert [item["role"] for item in merged["multiSkill"]["supportingSkills"]] == [
        "market-data",
        "report-synthesis",
    ]
    assert merged["evaluationEvidence"]["runtimeVerified"] is False
    assert "multi-skill-merge-contract-v1" in merged["evaluationEvidence"]["benchmarkIds"]
    assert all(step["source"].startswith("skill:") for step in merged["workflow"])

    loaded = load_agent_preset(merged)
    assert loaded["supportingSkillVersionIds"] == [
        stock["primarySkill"]["skillVersionId"],
        reporter["primarySkill"]["skillVersionId"],
    ]
    assert "Skill routing:" in loaded["developerPrompt"]

    tampered = deepcopy(merged)
    tampered["multiSkill"]["primaryRole"] = "tampered"
    with pytest.raises(AgentPresetIntegrityError):
        load_agent_preset(tampered)


def test_multi_skill_preset_rejects_duplicate_roles() -> None:
    primary_run, primary = source_preset("alphaear-signal-tracker-test", "DUP-PRIMARY")
    _, stock = source_preset("alphaear-stock-test", "DUP-STOCK")
    merge_run = deepcopy(primary_run)
    merge_run["id"] = "merge-run-duplicate-role"

    with pytest.raises(InvalidMultiSkillPreset, match="Duplicate Skill role"):
        compile_multi_skill_agent_preset(
            merge_run=merge_run,
            merge_run_revision=1,
            primary_role="signal-tracking",
            primary_preset=primary,
            supporting_presets=[{"role": "signal-tracking", "preset": stock}],
            routing=[
                {
                    "id": "route",
                    "order": 1,
                    "when": "always",
                    "useSkillRole": "signal-tracking",
                    "instruction": "Run the primary workflow.",
                }
            ],
            project_name="Duplicate",
            project_description="Duplicate role test.",
            scenario="test",
        )
