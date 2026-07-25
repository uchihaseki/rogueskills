from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from rogueskills.domain.benchmark import run_admission_benchmark
from rogueskills.domain.discovery import convert_material_to_skill
from rogueskills.domain.genome import validate_skill_genome
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


class AwesomeFinanceSkillsService:
    """Import a local Awesome Finance Skills snapshot through the normal gates.

    The source repository is treated as external material: every item is first
    stored as ``quarantine``, receives the same admission benchmark as a remote
    discovery candidate, and is promoted only when the benchmark and hard gates
    pass.  The importer is intentionally deterministic so a demo can run without
    an LLM or network access.
    """

    SOURCE_ID = "awesome-finance-skills"
    REPOSITORY_URL = "https://github.com/RKiding/Awesome-finance-skills"

    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository

    @staticmethod
    def _license(root: Path) -> str:
        license_path = root / "LICENSE"
        if not license_path.is_file():
            return "unknown"
        text = license_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"Apache License,?\s+Version 2\.0", text, re.I):
            return "Apache-2.0"
        if re.search(r"MIT License", text, re.I):
            return "MIT"
        if re.search(r"GNU GENERAL PUBLIC LICENSE", text, re.I):
            return "GPL-3.0-or-later"
        return "unknown"

    @staticmethod
    def _revision(root: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return "local-snapshot"
        revision = result.stdout.strip()
        return revision or "local-snapshot"

    @staticmethod
    def _skill_paths(root: Path, selected_names: set[str] | None) -> list[Path]:
        skills_root = root / "skills"
        if not skills_root.is_dir():
            raise ApplicationError(
                "AWESOME_FINANCE_SKILLS_NOT_FOUND",
                f"未找到 Awesome Finance Skills 目录：{skills_root}",
                status_code=404,
            )
        paths = sorted(
            path
            for path in skills_root.glob("alphaear-*/SKILL.md")
            if path.parent.name != "skill-creator"
            and (selected_names is None or path.parent.name in selected_names)
        )
        if not paths:
            raise ApplicationError(
                "AWESOME_FINANCE_SKILLS_EMPTY",
                "Awesome Finance Skills 目录中没有匹配的 alphaear-* SKILL.md。",
                status_code=422,
            )
        return paths

    def _existing(self, *, source_url: str, fingerprint: str) -> dict[str, Any] | None:
        return next(
            (
                skill
                for skill in self.repository.list_skills()
                if skill.get("sourceUrl") == source_url or skill.get("fingerprint") == fingerprint
            ),
            None,
        )

    def _admit_existing(
        self,
        existing: dict[str, Any],
        *,
        source_name: str,
        source_path: str,
        auto_promote: bool,
    ) -> dict[str, Any]:
        if existing["status"] == "initial" or not auto_promote:
            return {
                "sourceName": source_name,
                "skillId": existing["id"],
                "skillVersionId": existing["currentVersionId"],
                "name": existing["name"],
                "status": existing["status"],
                "action": "reused",
                "evaluation": (existing.get("evaluations") or [None])[0],
                "sourcePath": source_path,
            }
        evaluation_result = run_admission_benchmark(existing["genome"])
        evaluation = self.repository.record_evaluation(existing["id"], evaluation_result)
        current = existing
        action = "benchmarked"
        if evaluation_result["passed"]:
            current = self.repository.promote_to_initial(
                existing["id"], evaluation["id"], existing["currentVersionId"]
            )
            action = "promoted"
        return {
            "sourceName": source_name,
            "skillId": current["id"],
            "skillVersionId": current["currentVersionId"],
            "name": current["name"],
            "status": current["status"],
            "action": action,
            "evaluation": evaluation,
            "sourcePath": source_path,
        }

    def _import_one(
        self,
        *,
        root: Path,
        skill_path: Path,
        license_value: str,
        revision: str,
        auto_promote: bool,
    ) -> dict[str, Any]:
        content = skill_path.read_text(encoding="utf-8")
        relative_path = skill_path.relative_to(root).as_posix()
        skill_name = skill_path.parent.name
        source_url = f"{self.REPOSITORY_URL}/blob/{revision}/{relative_path}"
        genome = convert_material_to_skill(
            title=None,
            content=content,
            source={
                "platform": "Awesome Finance Skills",
                "url": source_url,
                "author": "RKiding/Awesome-finance-skills",
                "revision": revision,
                "artifactPaths": [relative_path],
            },
            license_value=license_value,
            kind="finance",
        )
        genome["metadata"]["category"] = "finance"
        genome["metadata"]["tags"] = list(
            dict.fromkeys(
                [
                    *genome["metadata"].get("tags", []),
                    "finance",
                    "stock-analysis",
                    "awesome-finance-skills",
                    skill_name,
                ]
            )
        )
        genome["provenance"]["normalizer"] = "deterministic-local"
        validation = validate_skill_genome(genome)
        if not validation["valid"]:
            raise ApplicationError(
                "AWESOME_FINANCE_SKILL_INVALID",
                f"{skill_name} 无法生成合法 Skill Genome。",
                status_code=422,
                details=validation,
            )

        existing = self._existing(
            source_url=source_url,
            fingerprint=genome["provenance"]["fingerprint"],
        )
        if existing:
            return self._admit_existing(
                existing,
                source_name=skill_name,
                source_path=relative_path,
                auto_promote=auto_promote,
            )

        genome["status"] = "quarantine"
        stored = self.repository.save_skill(
            genome,
            source_id=self.SOURCE_ID,
            snapshot_content=content,
        )
        evaluation_result = run_admission_benchmark(stored["genome"])
        evaluation = self.repository.record_evaluation(stored["id"], evaluation_result)
        current = stored
        action = "stored"
        if auto_promote and evaluation_result["passed"]:
            current = self.repository.promote_to_initial(
                stored["id"], evaluation["id"], stored["currentVersionId"]
            )
            action = "promoted"
        return {
            "sourceName": skill_name,
            "skillId": current["id"],
            "skillVersionId": current["currentVersionId"],
            "name": current["name"],
            "status": current["status"],
            "action": action,
            "evaluation": evaluation,
            "sourcePath": relative_path,
        }

    def run(
        self,
        *,
        root: Path,
        selected_names: list[str] | None = None,
        auto_promote: bool = True,
    ) -> dict[str, Any]:
        resolved_root = root.expanduser().resolve()
        if not resolved_root.is_dir():
            raise ApplicationError(
                "AWESOME_FINANCE_SKILLS_NOT_FOUND",
                f"未找到 Awesome Finance Skills 根目录：{resolved_root}",
                status_code=404,
            )
        selected = set(selected_names) if selected_names else None
        paths = self._skill_paths(resolved_root, selected)
        license_value = self._license(resolved_root)
        revision = self._revision(resolved_root)
        results: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for skill_path in paths:
            try:
                results.append(
                    self._import_one(
                        root=resolved_root,
                        skill_path=skill_path,
                        license_value=license_value,
                        revision=revision,
                        auto_promote=auto_promote,
                    )
                )
            except ApplicationError as error:
                rejected.append(
                    {
                        "sourceName": skill_path.parent.name,
                        "sourcePath": skill_path.relative_to(resolved_root).as_posix(),
                        "code": error.code,
                        "message": error.message,
                        "details": error.details,
                    }
                )
        initial_ids = [item["skillId"] for item in results if item["status"] == "initial"]
        return {
            "source": {
                "id": self.SOURCE_ID,
                "name": "Awesome Finance Skills",
                "repository": self.REPOSITORY_URL,
                "root": str(resolved_root),
                "revision": revision,
                "license": license_value,
            },
            "summary": {
                "discovered": len(paths),
                "processed": len(results),
                "initialSkills": len(initial_ids),
                "reused": sum(item["action"] == "reused" for item in results),
                "promoted": sum(item["action"] == "promoted" for item in results),
                "rejected": len(rejected),
            },
            "skills": results,
            "rejected": rejected,
            "initialSkillIds": initial_ids,
        }
