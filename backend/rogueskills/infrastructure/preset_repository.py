import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from rogueskills.application.errors import ApplicationError

from .database import AgentPresetRow


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse(value: str) -> dict[str, Any]:
    return json.loads(value)


class AgentPresetRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def get(self, preset_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.get(AgentPresetRow, preset_id)
            return deepcopy(_parse(row.config_json)) if row else None

    def get_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            row = session.scalar(select(AgentPresetRow).where(AgentPresetRow.run_id == run_id))
            return deepcopy(_parse(row.config_json)) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self.sessions() as session:
            rows = session.scalars(
                select(AgentPresetRow).order_by(AgentPresetRow.created_at.desc())
            ).all()
            return [deepcopy(_parse(row.config_json)) for row in rows]

    def save(self, preset: dict[str, Any]) -> dict[str, Any]:
        try:
            with self.sessions.begin() as session:
                existing = session.scalar(
                    select(AgentPresetRow).where(
                        AgentPresetRow.run_id == preset["sourceRun"]["runId"]
                    )
                )
                if existing:
                    current = _parse(existing.config_json)
                    if current["digest"] == preset["digest"]:
                        return deepcopy(current)
                    raise ApplicationError(
                        "AGENT_PRESET_ALREADY_EXISTS",
                        "该 Run 已经生成 AgentPreset，不能覆盖不可变配置。",
                        status_code=409,
                        details={"presetId": existing.id},
                    )
                session.add(
                    AgentPresetRow(
                        id=preset["id"],
                        run_id=preset["sourceRun"]["runId"],
                        base_skill_id=preset["sourceRun"]["baseSkillId"],
                        base_skill_version_id=preset["sourceRun"]["baseSkillVersionId"],
                        project_name=preset["project"]["name"],
                        scenario=preset["project"]["scenario"],
                        status=preset["status"],
                        digest=preset["digest"],
                        config_json=_json(preset),
                        created_at=datetime.now(UTC),
                    )
                )
        except IntegrityError as error:
            current = self.get_by_run_id(preset["sourceRun"]["runId"])
            if current and current["project"] == preset["project"]:
                return current
            raise ApplicationError(
                "AGENT_PRESET_ALREADY_EXISTS",
                "该 Run 已经生成 AgentPreset，不能覆盖不可变配置。",
                status_code=409,
            ) from error
        return deepcopy(preset)
