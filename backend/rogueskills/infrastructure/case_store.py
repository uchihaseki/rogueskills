from __future__ import annotations

from typing import Any

from .case_run_repository import CaseRunRepository
from .finance_case_repository import FinanceCaseRepository


class CompatibleCaseRunStore:
    """Write new runs generically while retaining read access to legacy Finance runs."""

    def __init__(
        self,
        primary: CaseRunRepository,
        legacy_finance: FinanceCaseRepository,
    ) -> None:
        self.primary = primary
        self.legacy_finance = legacy_finance

    def save(
        self,
        state: dict[str, Any],
        *,
        source_bundle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.primary.save(state, source_bundle=source_bundle)

    def get(self, case_id: str, *, include_bundle: bool = False) -> dict[str, Any] | None:
        return self.primary.get(case_id, include_bundle=include_bundle) or self.legacy_finance.get(
            case_id, include_bundle=include_bundle
        )

    def list(
        self, *, limit: int = 30, case_pack_id: str | None = None
    ) -> list[dict[str, Any]]:
        current = self.primary.list(limit=limit, case_pack_id=case_pack_id)
        if case_pack_id not in {None, "finance-stock-analysis"}:
            return current
        legacy = self.legacy_finance.list(limit=limit)
        seen = {item["id"] for item in current}
        return (current + [item for item in legacy if item.get("id") not in seen])[:limit]
