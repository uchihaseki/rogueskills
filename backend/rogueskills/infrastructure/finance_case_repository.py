from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .database import FinanceCaseRunRow


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse(value: str | None, fallback: Any = None) -> dict[str, Any]:
    parsed = json.loads(value) if value is not None else fallback
    return parsed if isinstance(parsed, dict) else {}


class FinanceCaseRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def save(
        self,
        state: dict[str, Any],
        *,
        source_bundle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            row = session.get(FinanceCaseRunRow, state["id"])
            if row is None:
                row = FinanceCaseRunRow(
                    id=state["id"],
                    ticker=state["ticker"],
                    as_of_date=state["asOfDate"],
                    mode=state["mode"],
                    skill_id=state["skillId"],
                    base_skill_version_id=state["baseSkillVersionId"],
                    evolved_skill_version_id=state.get("evolvedSkillVersionId"),
                    status=state["status"],
                    phase=state["phase"],
                    state_json=_json(state),
                    source_bundle_json=_json(source_bundle) if source_bundle else None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.status = state["status"]
                row.phase = state["phase"]
                row.evolved_skill_version_id = state.get("evolvedSkillVersionId")
                row.state_json = _json(state)
                if source_bundle is not None:
                    row.source_bundle_json = _json(source_bundle)
                row.updated_at = now
            session.flush()
        return deepcopy(state)

    def get(self, case_id: str, *, include_bundle: bool = False) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(FinanceCaseRunRow, case_id)
            if row is None:
                return None
            result = _parse(row.state_json, {})
            if include_bundle:
                result["_sourceBundle"] = _parse(row.source_bundle_json, None)
            return result

    def list(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.sessions() as session:
            rows = session.scalars(
                select(FinanceCaseRunRow)
                .order_by(FinanceCaseRunRow.created_at.desc())
                .limit(limit)
            ).all()
            return [_parse(row.state_json, {}) for row in rows]
