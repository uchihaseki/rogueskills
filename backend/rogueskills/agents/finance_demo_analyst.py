from __future__ import annotations

from typing import Any

from rogueskills.contracts.finance_case import FinanceNarrative

from .finance_analyst import FinanceAnalystInfo


class DemoFinanceAnalyst:
    """Deterministic analyst for the bundled, persisted finance replay.

    The demo case is intentionally offline: it reads only the replay dataset and
    produces a stable baseline/candidate contrast so a presenter can demonstrate
    runtime validation without requiring an LLM endpoint.
    """

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="deterministic-replay",
            provider="RogueSkills demo fixture",
            model="finance-demo-evidence-analyst",
            configured=True,
        )

    @staticmethod
    def _value(dataset: dict[str, Any], item_id: str) -> float:
        for item in [*dataset.get("facts", []), *dataset.get("derivedMetrics", [])]:
            if item.get("id") == item_id:
                return float(item.get("value") or 0)
        return 0.0

    @staticmethod
    def _hundred_millions(value: float) -> str:
        return f"{value / 100_000_000:.1f} 亿美元"

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> FinanceNarrative:
        del genome, feedback
        candidate = agent_config is not None
        company = str(dataset.get("company", {}).get("name") or case.get("ticker") or "公司")
        revenue = self._value(dataset, "fact-revenue-annual_current")
        net_income = self._value(dataset, "fact-net_income-annual_current")
        free_cash_flow = self._value(dataset, "metric-free-cash-flow")
        if candidate:
            evidence = [
                "fact-revenue-annual_current",
                "fact-net_income-annual_current",
                "metric-free-cash-flow",
            ]
            findings = [
                {
                    "id": "finding-revenue",
                    "kind": "fact",
                    "claim": f"{company} 最近一个完整财年收入约 {self._hundred_millions(revenue)}，该结论直接引用 SEC 年度事实。",
                    "evidenceIds": [evidence[0]],
                },
                {
                    "id": "finding-profit",
                    "kind": "fact",
                    "claim": f"同期净利润约 {self._hundred_millions(net_income)}，口径为申报中的年度净利润。",
                    "evidenceIds": [evidence[1]],
                },
                {
                    "id": "finding-cash-flow",
                    "kind": "inference",
                    "claim": f"由经营现金流减资本开支得到的自由现金流约 {self._hundred_millions(free_cash_flow)}。",
                    "evidenceIds": [evidence[2]],
                },
            ]
        else:
            # The baseline deliberately cites the provider-level source only. The
            # evaluator can therefore demonstrate the value of claim-level citation
            # binding while keeping every statement grounded in the same snapshot.
            evidence = ["sec-companyfacts"] * 3
            findings = [
                {
                    "id": "finding-revenue",
                    "kind": "fact",
                    "claim": f"{company} 的公开财务数据已加载，可用于收入趋势分析。",
                    "evidenceIds": [evidence[0]],
                },
                {
                    "id": "finding-profit",
                    "kind": "fact",
                    "claim": "公开申报包含利润与现金流字段，可继续进行期间对照。",
                    "evidenceIds": [evidence[1]],
                },
                {
                    "id": "finding-cash-flow",
                    "kind": "inference",
                    "claim": "估值与现金流信息已保留在同源数据集，可供后续核验。",
                    "evidenceIds": [evidence[2]],
                },
            ]
        return FinanceNarrative.model_validate(
            {
                "summary": (
                    f"基于已持久化 SEC 与市场快照的 {company} 公开财务分析。"
                    if candidate
                    else f"已从同一持久化快照加载 {company} 的公开财务信息。"
                ),
                "findings": findings,
                "risks": [
                    {
                        "id": "risk-data-timing",
                        "risk": "申报和市场价格的时间点不同，不能将两者误解为同一时点估值。",
                        "evidenceIds": ["sec-submissions", "market-price"],
                    },
                    {
                        "id": "risk-scenario",
                        "risk": "估值情景依赖倍数和现金流收益率假设，不代表预测或投资建议。",
                        "evidenceIds": ["metric-free-cash-flow"],
                    },
                ],
                "dataGaps": ["未请求在线数据；分析仅使用已持久化来源快照。"],
                "conclusionBoundary": "这是基于公开信息的研究演示，不构成个性化投资建议。",
            }
        )
