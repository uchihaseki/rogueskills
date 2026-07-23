from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .database import CaseRunRow


class StaleCaseRunRevision(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse(value: str | None, fallback: Any = None) -> dict[str, Any]:
    parsed = json.loads(value) if value is not None else fallback
    return parsed if isinstance(parsed, dict) else {}


def _date_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class CaseRunRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def save(
        self,
        state: dict[str, Any],
        *,
        source_bundle: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        persisted = deepcopy(state)
        with self.sessions.begin() as session:
            row = session.get(CaseRunRow, state["id"])
            if row is None:
                if expected_revision not in {None, 0}:
                    raise StaleCaseRunRevision(
                        f"Case Run does not exist at revision {expected_revision}."
                    )
                revision = 1
                persisted["revision"] = revision
                row = CaseRunRow(
                    id=state["id"],
                    case_pack_id=state["casePackId"],
                    case_pack_version=state["casePackVersion"],
                    input_json=_json(state.get("input", {})),
                    mode=state["mode"],
                    replay_case_id=state.get("replayCaseId"),
                    skill_id=state["skillId"],
                    base_skill_version_id=state["baseSkillVersionId"],
                    evolved_skill_version_id=state.get("evolvedSkillVersionId"),
                    status=state["status"],
                    phase=state["phase"],
                    state_json=_json(persisted),
                    source_bundle_json=_json(source_bundle) if source_bundle else None,
                    revision=revision,
                    created_at=now,
                    updated_at=now,
                    completed_at=_date_time(state.get("completedAt")),
                )
                session.add(row)
            else:
                if expected_revision is not None and row.revision != expected_revision:
                    raise StaleCaseRunRevision(
                        f"Expected Case Run revision {expected_revision}; found {row.revision}."
                    )
                revision = row.revision + 1
                persisted["revision"] = revision
                row.evolved_skill_version_id = state.get("evolvedSkillVersionId")
                row.status = state["status"]
                row.phase = state["phase"]
                row.state_json = _json(persisted)
                if source_bundle is not None:
                    row.source_bundle_json = _json(source_bundle)
                row.revision = revision
                row.updated_at = now
                row.completed_at = _date_time(state.get("completedAt"))
            session.flush()
        state["revision"] = persisted["revision"]
        return persisted

    def get(self, case_id: str, *, include_bundle: bool = False) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(CaseRunRow, case_id)
            if row is None:
                return None
            result = _parse(row.state_json, {})
            result["revision"] = row.revision
            if include_bundle:
                result["_sourceBundle"] = _parse(row.source_bundle_json, None)
            return result

    def list(
        self, *, limit: int = 30, case_pack_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self.sessions() as session:
            statement = select(CaseRunRow)
            if case_pack_id:
                statement = statement.where(CaseRunRow.case_pack_id == case_pack_id)
            rows = session.scalars(
                statement.order_by(CaseRunRow.created_at.desc()).limit(limit)
            ).all()
            result = []
            for row in rows:
                state = _parse(row.state_json, {})
                state["revision"] = row.revision
                result.append(state)
            return result
