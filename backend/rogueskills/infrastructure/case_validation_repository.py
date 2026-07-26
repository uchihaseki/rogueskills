from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .database import CaseValidationRow


class StaleCaseValidationRevision(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _date_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class CaseValidationRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def save(
        self,
        state: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        persisted = deepcopy(state)
        try:
            with self.sessions.begin() as session:
                row = session.get(CaseValidationRow, state["id"])
                if row is None:
                    if expected_revision not in {None, 0}:
                        raise StaleCaseValidationRevision(
                            f"CaseValidation does not exist at revision {expected_revision}."
                        )
                    persisted["revision"] = 1
                    row = CaseValidationRow(
                        id=state["id"],
                        idempotency_key=state["idempotencyKey"],
                        source_run_id=state["sourceRunId"],
                        candidate_preset_id=state["candidatePresetId"],
                        case_pack_id=state["casePackId"],
                        case_pack_version=state["casePackVersion"],
                        replay_case_id=state["replayCaseId"],
                        skill_id=state["skillId"],
                        base_skill_version_id=state["baseSkillVersionId"],
                        evolved_skill_version_id=(state.get("promotion") or {}).get(
                            "evolvedSkillVersionId"
                        ),
                        status=state["status"],
                        phase=state["phase"],
                        state_json=_json(persisted),
                        revision=1,
                        created_at=now,
                        updated_at=now,
                        completed_at=_date_time(state.get("completedAt")),
                    )
                    session.add(row)
                else:
                    if expected_revision is not None and row.revision != expected_revision:
                        raise StaleCaseValidationRevision(
                            f"Expected CaseValidation revision {expected_revision}; found {row.revision}."
                        )
                    persisted["revision"] = row.revision + 1
                    row.evolved_skill_version_id = (state.get("promotion") or {}).get(
                        "evolvedSkillVersionId"
                    )
                    row.status = state["status"]
                    row.phase = state["phase"]
                    row.state_json = _json(persisted)
                    row.revision = persisted["revision"]
                    row.updated_at = now
                    row.completed_at = _date_time(state.get("completedAt"))
                session.flush()
        except IntegrityError:
            existing = self.get_by_idempotency_key(state["idempotencyKey"])
            if existing is not None:
                return existing
            raise
        state["revision"] = persisted["revision"]
        return persisted

    def get(self, validation_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(CaseValidationRow, validation_id)
            if row is None:
                return None
            result = _parse(row.state_json)
            result["revision"] = row.revision
            return result

    def get_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.scalar(
                select(CaseValidationRow).where(CaseValidationRow.idempotency_key == key)
            )
            if row is None:
                return None
            result = _parse(row.state_json)
            result["revision"] = row.revision
            return result

    def list_by_run(self, run_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.sessions() as session:
            rows = session.scalars(
                select(CaseValidationRow)
                .where(CaseValidationRow.source_run_id == run_id)
                .order_by(CaseValidationRow.created_at.desc())
                .limit(max(1, min(int(limit), 100)))
            ).all()
            result = []
            for row in rows:
                state = _parse(row.state_json)
                state["revision"] = row.revision
                result.append(state)
            return result
