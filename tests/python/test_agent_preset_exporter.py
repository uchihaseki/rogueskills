import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import pytest

from rogueskills.adapters.agent_preset_exporter import build_agent_preset_export
from rogueskills.adapters.agent_preset_loader import AgentPresetIntegrityError
from rogueskills.domain.catalogs import SEED_SKILLS
from rogueskills.domain.evolution import create_run
from rogueskills.domain.presets import compile_agent_preset


def preset_fixture() -> dict:
    genome = SEED_SKILLS[0]
    run = create_run(seed="EXPORT-001", skill_genome=genome)
    run.update(
        {
            "status": "victory",
            "phase": "ended",
            "mutationIds": ["schema_validator", "screenshot_ocr", "injection_shield"],
            "evolutionIds": ["adaptive_web_extractor"],
            "encounterHistory": [
                {"passed": True, "benchmarkId": "scenario-runtime-v1"},
            ],
        }
    )
    return compile_agent_preset(
        run=run,
        run_revision=9,
        base_skill_version_id=f"{genome['id']}@1",
        base_skill_genome=genome,
        project_name="商品采集 Agent",
        project_description="从商品页面提取并校验结构化数据。",
        scenario="电商商品信息提取",
        clock=lambda: datetime(2026, 7, 21, tzinfo=UTC),
    )


def archive_files(content: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.parametrize(
    ("target", "required", "excluded"),
    [
        ("codex", {"AGENTS.md", ".agents/skills/"}, {"CLAUDE.md", ".claude/skills/"}),
        (
            "claude-code",
            {"CLAUDE.md", ".claude/skills/"},
            {"AGENTS.md", ".agents/skills/"},
        ),
        (
            "universal",
            {"AGENTS.md", "CLAUDE.md", ".agents/skills/", ".claude/skills/"},
            set(),
        ),
    ],
)
def test_agent_preset_exports_platform_packages(
    target: str, required: set[str], excluded: set[str]
) -> None:
    preset = preset_fixture()
    artifact = build_agent_preset_export(preset, target)  # type: ignore[arg-type]
    files = archive_files(artifact.content)
    names = set(files)

    assert artifact.media_type == "application/zip"
    assert artifact.filename.endswith(f"-{target}.zip")
    for marker in required:
        assert marker in names or any(name.startswith(marker) for name in names)
    for marker in excluded:
        assert marker not in names and not any(name.startswith(marker) for name in names)
    assert all(not name.startswith(("/", "../")) and "/../" not in name for name in names)

    manifest_path = next(name for name in names if name.endswith("/export-manifest.json"))
    manifest = json.loads(files[manifest_path])
    assert manifest["target"] == target
    assert manifest["presetId"] == preset["id"]
    assert set(manifest["entrypoints"]) == required.intersection({"AGENTS.md", "CLAUDE.md"})
    declared_paths = {item["path"] for item in manifest["files"]}
    assert declared_paths == names - {manifest_path}
    for item in manifest["files"]:
        digest = "sha256:" + hashlib.sha256(files[item["path"]]).hexdigest()
        assert item["digest"] == digest

    skill_paths = [name for name in names if name.endswith("/SKILL.md")]
    for path in skill_paths:
        skill = files[path].decode()
        frontmatter = skill.split("---", 2)[1].strip().splitlines()
        assert [line.split(":", 1)[0] for line in frontmatter] == ["name", "description"]
        assert f"name: {manifest['skillName']}" in frontmatter
        assert "从商品页面提取并校验结构化数据。" in skill
        assert "Runtime verification is false" in skill
        assert "Maximum tool calls" in skill


def test_agent_preset_export_is_deterministic_and_checks_integrity() -> None:
    preset = preset_fixture()
    first = build_agent_preset_export(preset, "universal")
    second = build_agent_preset_export(preset, "universal")
    assert first == second

    tampered = deepcopy(preset)
    tampered["project"]["name"] = "Tampered"
    with pytest.raises(AgentPresetIntegrityError):
        build_agent_preset_export(tampered, "codex")

    with pytest.raises(ValueError, match="Unsupported AgentPreset export target"):
        build_agent_preset_export(preset, "unknown")  # type: ignore[arg-type]
