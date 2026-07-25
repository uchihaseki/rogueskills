from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from rogueskills.application.errors import ApplicationError
from rogueskills.domain.genome import assert_skill_genome, validate_skill_genome

from .database import BenchmarkRunRow, EvolutionRunRow, SkillRow, SkillVersionRow, SourceSnapshotRow


def _now() -> datetime:
    return datetime.now(UTC)


def _iso_now() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse(value: str | None, fallback: Any = None) -> Any:
    try:
        return json.loads(value) if value is not None else fallback
    except json.JSONDecodeError:
        return fallback


class SkillRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def _current_version(self, session: Session, skill: SkillRow) -> SkillVersionRow | None:
        if not skill.current_version_id:
            return None
        return session.get(SkillVersionRow, skill.current_version_id)

    def _add_version(
        self, session: Session, skill_id: str, genome: dict[str, Any], parent_id: str | None
    ) -> SkillVersionRow:
        latest = (
            session.scalar(
                select(func.max(SkillVersionRow.version)).where(
                    SkillVersionRow.skill_id == skill_id
                )
            )
            or 0
        )
        version = SkillVersionRow(
            id=f"{skill_id}@{latest + 1}",
            skill_id=skill_id,
            version=latest + 1,
            parent_version_id=parent_id,
            genome_json=_json(genome),
            created_at=_iso_now(),
        )
        session.add(version)
        session.flush()
        return version

    def save_skill(
        self,
        genome: dict[str, Any],
        *,
        source_id: str = "manual",
        snapshot_content: str | None = None,
        trusted_status: bool = False,
    ) -> dict[str, Any]:
        normalized = deepcopy(genome)
        if not trusted_status:
            normalized["status"] = "quarantine"
            normalized["evaluation"] = {
                **normalized.get("evaluation", {}),
                "status": "not_run",
                "lastRunId": None,
                "score": None,
            }
        assert_skill_genome(normalized)
        timestamp = _iso_now()
        with self.sessions.begin() as session:
            skill = session.get(SkillRow, normalized["id"])
            if skill and not trusted_status and skill.lifecycle_status != "quarantine":
                raise ApplicationError(
                    "IMMUTABLE_PUBLISHED_SKILL",
                    "已准入 Skill 不能通过通用保存接口修改。",
                    status_code=409,
                )
            if not skill:
                skill = SkillRow(
                    id=normalized["id"],
                    name=normalized["name"],
                    description=normalized["description"],
                    lifecycle_status=normalized["status"],
                    current_version_id=None,
                    source_id=source_id,
                    source_url=normalized["provenance"].get("url"),
                    license=normalized["metadata"]["license"],
                    risk_level=normalized["risk"]["level"],
                    fingerprint=normalized["provenance"]["fingerprint"],
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                session.add(skill)
                session.flush()
                version = self._add_version(session, skill.id, normalized, None)
            else:
                current = self._current_version(session, skill)
                if current and _parse(current.genome_json) == normalized:
                    version = current
                else:
                    version = self._add_version(
                        session, skill.id, normalized, current.id if current else None
                    )
                skill.name = normalized["name"]
                skill.description = normalized["description"]
                skill.lifecycle_status = normalized["status"]
                skill.source_id = source_id
                skill.source_url = normalized["provenance"].get("url")
                skill.license = normalized["metadata"]["license"]
                skill.risk_level = normalized["risk"]["level"]
                skill.fingerprint = normalized["provenance"]["fingerprint"]
                skill.updated_at = timestamp
            skill.current_version_id = version.id
            fingerprint = normalized["provenance"].get("fingerprint")
            if fingerprint:
                existing_snapshot = session.scalar(
                    select(SourceSnapshotRow).where(
                        SourceSnapshotRow.skill_id == skill.id,
                        SourceSnapshotRow.fingerprint == fingerprint,
                    )
                )
                if not existing_snapshot:
                    session.add(
                        SourceSnapshotRow(
                            id=f"snapshot-{uuid4().hex}",
                            skill_id=skill.id,
                            source_url=normalized["provenance"].get("url"),
                            revision=normalized["provenance"].get("revision"),
                            artifact_paths_json=_json(
                                normalized["provenance"].get("artifactPaths", [])
                            ),
                            fingerprint=fingerprint,
                            content=snapshot_content,
                            fetched_at=normalized["provenance"].get("capturedAt") or timestamp,
                        )
                    )
        result = self.get_skill(normalized["id"])
        assert result is not None
        return result

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            skill = session.get(SkillRow, skill_id)
            if not skill:
                return None
            current = self._current_version(session, skill)
            versions = session.scalars(
                select(SkillVersionRow)
                .where(SkillVersionRow.skill_id == skill_id)
                .order_by(SkillVersionRow.version.desc())
            ).all()
            snapshots = session.scalars(
                select(SourceSnapshotRow)
                .where(SourceSnapshotRow.skill_id == skill_id)
                .order_by(SourceSnapshotRow.fetched_at.desc())
            ).all()
            evaluations = session.scalars(
                select(BenchmarkRunRow)
                .where(BenchmarkRunRow.skill_id == skill_id)
                .order_by(BenchmarkRunRow.created_at.desc())
            ).all()
            return {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "status": skill.lifecycle_status,
                "currentVersionId": skill.current_version_id,
                "sourceId": skill.source_id,
                "sourceUrl": skill.source_url,
                "license": skill.license,
                "riskLevel": skill.risk_level,
                "fingerprint": skill.fingerprint,
                "createdAt": skill.created_at,
                "updatedAt": skill.updated_at,
                "genome": _parse(current.genome_json) if current else None,
                "versions": [
                    {
                        "id": row.id,
                        "version": row.version,
                        "parentVersionId": row.parent_version_id,
                        "createdAt": row.created_at,
                    }
                    for row in versions
                ],
                "snapshots": [
                    {
                        "id": row.id,
                        "sourceUrl": row.source_url,
                        "revision": row.revision,
                        "artifactPaths": _parse(row.artifact_paths_json, []),
                        "fingerprint": row.fingerprint,
                        "fetchedAt": row.fetched_at,
                    }
                    for row in snapshots
                ],
                "evaluations": [self._evaluation_dict(row) for row in evaluations],
            }

    def list_skills(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.sessions() as session:
            query = select(SkillRow.id)
            if status:
                query = query.where(SkillRow.lifecycle_status == status)
            ids = session.scalars(query.order_by(SkillRow.updated_at.desc())).all()
        return [skill for skill_id in ids if (skill := self.get_skill(skill_id))]

    def delete_skill(self, skill_id: str) -> bool:
        with self.sessions.begin() as session:
            skill = session.get(SkillRow, skill_id)
            if not skill:
                return False
            if skill.lifecycle_status != "quarantine":
                raise ApplicationError(
                    "INVALID_LIFECYCLE_TRANSITION",
                    "只有 Quarantine Skill 可以直接移除。",
                    status_code=409,
                )
            session.delete(skill)
        return True

    @staticmethod
    def _evaluation_dict(row: BenchmarkRunRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "skillId": row.skill_id,
            "skillVersionId": row.skill_version_id,
            "benchmarkId": row.benchmark_id,
            "split": row.split,
            "score": row.score,
            "passed": bool(row.passed),
            "result": _parse(row.result_json, {}),
            "createdAt": row.created_at,
        }

    def record_evaluation(self, skill_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self.sessions.begin() as session:
            skill = session.get(SkillRow, skill_id)
            if not skill or not skill.current_version_id:
                raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
            evaluation_id = result.get("runId") or f"benchmark-{uuid4().hex}"
            if session.get(BenchmarkRunRow, evaluation_id):
                evaluation_id = f"{evaluation_id}-{uuid4().hex[:8]}"
            row = BenchmarkRunRow(
                id=evaluation_id,
                skill_id=skill_id,
                skill_version_id=skill.current_version_id,
                benchmark_id=result["benchmarkId"],
                split=result["split"],
                score=result["score"],
                passed=result["passed"],
                result_json=_json(result),
                created_at=_iso_now(),
            )
            session.add(row)
            session.flush()
            return self._evaluation_dict(row)

    def get_skill_version(self, version_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(SkillVersionRow, version_id)
            return (
                {
                    "id": row.id,
                    "skillId": row.skill_id,
                    "version": row.version,
                    "parentVersionId": row.parent_version_id,
                    "genome": _parse(row.genome_json, {}),
                    "createdAt": row.created_at,
                }
                if row
                else None
            )

    def get_evaluation(self, evaluation_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(BenchmarkRunRow, evaluation_id)
            return self._evaluation_dict(row) if row else None

    def promote_to_initial(
        self, skill_id: str, evaluation_id: str, expected_version_id: str
    ) -> dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        evaluation = self.get_evaluation(evaluation_id)
        if skill["currentVersionId"] != expected_version_id:
            raise ApplicationError(
                "STALE_SKILL_VERSION", "Skill 当前版本已经改变。", status_code=409
            )
        if (
            not evaluation
            or evaluation["skillId"] != skill_id
            or not evaluation["passed"]
            or evaluation["benchmarkId"] != "library-admission-v1"
        ):
            raise ApplicationError(
                "INVALID_EVALUATION", "需要当前 Skill 的通过准入评估。", status_code=409
            )
        if evaluation["skillVersionId"] != skill["currentVersionId"]:
            raise ApplicationError(
                "STALE_EVALUATION", "Evaluation 不属于当前 Skill 版本。", status_code=409
            )
        genome = deepcopy(skill["genome"])
        validation = validate_skill_genome(genome)
        if not validation["valid"]:
            raise ApplicationError(
                "INVALID_SKILL_GENOME",
                "Skill Genome 未通过 Schema 验证。",
                status_code=422,
                details=validation,
            )
        if genome["metadata"]["license"] in ("unknown", "NOASSERTION"):
            raise ApplicationError("LICENSE_GATE_FAILED", "许可证未知。", status_code=409)
        if genome["risk"]["level"] == "high":
            raise ApplicationError(
                "SAFETY_GATE_FAILED", "高风险 Skill 不能进入 Initial Library。", status_code=409
            )
        genome["status"] = "initial"
        genome["evaluation"] = {
            **genome["evaluation"],
            "status": "passed",
            "lastRunId": evaluation_id,
            "score": evaluation["score"],
        }
        return self.save_skill(genome, source_id=skill["sourceId"] or "manual", trusted_status=True)

    def save_evolved_skill(
        self,
        genome: dict[str, Any],
        *,
        expected_version_id: str,
        runtime_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        skill_id = str(genome.get("id") or "")
        current = self.get_skill(skill_id)
        if not current:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        if current["currentVersionId"] != expected_version_id:
            raise ApplicationError(
                "STALE_SKILL_VERSION",
                "Skill 当前版本已经改变，不能保存本次进化。",
                status_code=409,
                details={"currentVersionId": current["currentVersionId"]},
            )
        if current["status"] != "initial":
            raise ApplicationError(
                "SKILL_NOT_INITIAL",
                "只有 Initial Skill 可以通过真实 Case 保存进化版本。",
                status_code=409,
            )
        evolved = deepcopy(genome)
        evolved["status"] = "initial"
        evolved["runtimeVerification"] = deepcopy(runtime_evidence)
        validation = validate_skill_genome(evolved)
        if not validation["valid"]:
            raise ApplicationError(
                "INVALID_EVOLVED_SKILL_GENOME",
                "进化后的 Skill Genome 未通过 Schema 验证。",
                status_code=422,
                details=validation,
            )
        saved = self.save_skill(
            evolved,
            source_id=current["sourceId"] or "finance-runtime",
            trusted_status=True,
        )
        if saved["currentVersionId"] == expected_version_id:
            raise ApplicationError(
                "EVOLVED_SKILL_UNCHANGED",
                "Mutation 没有产生新的 Skill Version。",
                status_code=409,
            )
        return saved

    def save_run(
        self,
        state: dict[str, Any],
        *,
        base_skill_version_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        now = _now()
        with self.sessions.begin() as session:
            row = session.get(EvolutionRunRow, state["id"])
            if not row:
                row = EvolutionRunRow(
                    id=state["id"],
                    base_skill_id=state["baseSkillId"],
                    base_skill_version_id=base_skill_version_id,
                    status=state["status"],
                    phase=state["phase"],
                    state_json=_json(state),
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                if expected_revision is not None and row.revision != expected_revision:
                    raise ApplicationError(
                        "STALE_RUN_REVISION",
                        "Run 已被其他操作更新。",
                        status_code=409,
                        details={"currentRevision": row.revision},
                    )
                row.status = state["status"]
                row.phase = state["phase"]
                row.state_json = _json(state)
                row.revision += 1
                row.updated_at = now
            session.flush()
            return {
                "run": deepcopy(state),
                "revision": row.revision,
                "baseSkillVersionId": row.base_skill_version_id,
            }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(EvolutionRunRow, run_id)
            return (
                {
                    "run": _parse(row.state_json, {}),
                    "revision": row.revision,
                    "baseSkillVersionId": row.base_skill_version_id,
                }
                if row
                else None
            )

    def list_runs(self, *, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
        """Return the most recently updated Evolution Runs.

        The UI normally knows the active Run ID, but external hosts such as Codex
        need a small read-only discovery surface to pick up the latest local demo
        without asking the presenter to copy an opaque ID by hand.
        """

        bounded_limit = max(1, min(int(limit), 100))
        with self.sessions() as session:
            query = select(EvolutionRunRow).order_by(EvolutionRunRow.updated_at.desc())
            if status:
                query = query.where(EvolutionRunRow.status == status)
            rows = session.scalars(query.limit(bounded_limit)).all()
            return [
                {
                    "run": _parse(row.state_json, {}),
                    "revision": row.revision,
                    "baseSkillVersionId": row.base_skill_version_id,
                }
                for row in rows
            ]
