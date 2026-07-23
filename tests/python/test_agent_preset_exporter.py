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


def preset_fixture(*, finance: bool = False) -> dict:
    genome = deepcopy(SEED_SKILLS[0])
    if finance:
        genome["metadata"]["category"] = "finance"
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
        scenario="public-company-financial-analysis" if finance else "电商商品信息提取",
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


def test_finance_exports_include_pinned_host_mcp_configuration() -> None:
    preset = preset_fixture(finance=True)
    artifact = build_agent_preset_export(preset, "claude-code")
    files = archive_files(artifact.content)

    assert ".mcp.json" in files
    assert "ROGUESKILLS-INSTALL.md" in files
    config = json.loads(files[".mcp.json"])
    server = config["mcpServers"]["rogueskills-finance"]
    assert server["command"] == "rogueskills-finance-mcp"
    assert server["env"]["ROGUESKILLS_API_BASE_URL"] == "http://127.0.0.1:5173"
    assert (
        server["env"]["ROGUESKILLS_DEFAULT_FINANCE_SKILL_ID"]
        == preset["primarySkill"]["skillId"]
    )
    assert server["env"]["ROGUESKILLS_ALLOWED_CASE_PACKS"] == "finance-stock-analysis"
    assert json.loads(server["env"]["ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS"]) == {
        "finance-stock-analysis": preset["primarySkill"]["skillVersionId"]
    }
    assert "finance_preflight" in files["CLAUDE.md"].decode()
    assert "Do not extract" in files["ROGUESKILLS-INSTALL.md"].decode()

    codex_files = archive_files(build_agent_preset_export(preset, "codex").content)
    assert ".mcp.json" not in codex_files
    assert "ROGUESKILLS-CODEX-INSTALL.md" in codex_files
    codex_guide = codex_files["ROGUESKILLS-CODEX-INSTALL.md"].decode()
    assert "codex mcp add" in codex_guide.replace("'", "")
    assert "rogueskills-case-mcp" in codex_guide
    assert "finance-stock-analysis" in codex_guide
    assert preset["primarySkill"]["skillVersionId"] in codex_guide
    assert "ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS" in codex_guide
    assert "case_preflight" in codex_files["AGENTS.md"].decode()

    universal_files = archive_files(build_agent_preset_export(preset, "universal").content)
    assert ".mcp.json" in universal_files
    assert "ROGUESKILLS-CODEX-INSTALL.md" in universal_files
    assert "ROGUESKILLS-INSTALL.md" in universal_files


def test_non_case_codex_export_does_not_claim_live_mcp_support() -> None:
    files = archive_files(build_agent_preset_export(preset_fixture(), "codex").content)
    guide = files["ROGUESKILLS-CODEX-INSTALL.md"].decode()

    assert "no MCP registration command was generated" in guide
    assert "codex mcp add" not in guide
