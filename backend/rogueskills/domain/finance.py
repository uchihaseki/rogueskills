from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from .catalogs import FINANCE_BOOTSTRAP
from .discovery import scan_content
from .shared import clamp, round_number

FINANCE_TERMS = {
    "stock",
    "stocks",
    "equity",
    "equities",
    "fundamental",
    "valuation",
    "earnings",
    "financial statement",
    "cash flow",
    "investment research",
    "portfolio",
    "股票",
    "上市公司",
    "基本面",
    "财报",
    "估值",
    "现金流",
}
WORKFLOW_TERMS = {"skill", "agent", "workflow", "procedure", "steps", "prompt", "流程", "步骤"}


def _text(candidate: dict[str, Any], *, include_content: bool) -> str:
    parts = [
        candidate.get("name", ""),
        candidate.get("summary", ""),
        " ".join(candidate.get("tags", [])),
    ]
    if include_content:
        parts.append(candidate.get("content", ""))
    return " ".join(str(item) for item in parts).lower()


def _term_hits(text: str) -> list[str]:
    return sorted(term for term in FINANCE_TERMS if term in text)


def rank_finance_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(candidate)
    ranking = candidate.get("ranking", {})
    signals = candidate.get("signals", {})
    stars = max(0, int(signals.get("stars", 0) or 0))
    hits = _term_hits(_text(candidate, include_content=False))
    finance_relevance = clamp(len(hits) * 18 + ranking.get("relevance", 0) * 0.55, 0, 100)
    community_signal = clamp(math.log10(stars + 1) * 28, 0, 100)
    score = round_number(
        finance_relevance * 0.32
        + ranking.get("total", 0) * 0.2
        + ranking.get("quality", 0) * 0.18
        + ranking.get("trust", 0) * 0.15
        + community_signal * 0.15,
        1,
    )
    reasons: list[str] = []
    policy = FINANCE_BOOTSTRAP["filter"]
    license_value = str(candidate.get("license", "unknown"))
    if license_value in {"", "unknown", "NOASSERTION", "None"}:
        reasons.append("许可证未知")
    if stars < policy["minStars"]:
        reasons.append(f"社区信号不足：stars {stars} < {policy['minStars']}")
    if ranking.get("total", 0) < policy["minRankingTotal"]:
        reasons.append("Discovery 综合分不足")
    if ranking.get("relevance", 0) < policy["minRelevance"] or not hits:
        reasons.append("股票分析相关度不足")
    if candidate.get("risk", {}).get("level") == "high":
        reasons.append("元数据静态风险过高")
    result["financeRanking"] = {
        "score": score,
        "financeRelevance": round_number(finance_relevance, 1),
        "communitySignal": round_number(community_signal, 1),
        "stars": stars,
        "matchedTerms": hits,
        "eligible": not reasons,
        "reasons": reasons,
    }
    return result


def select_finance_candidates(
    candidates: list[dict[str, Any]], *, pool_size: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked = [rank_finance_candidate(candidate) for candidate in candidates]
    selected = sorted(
        (item for item in ranked if item["financeRanking"]["eligible"]),
        key=lambda item: item["financeRanking"]["score"],
        reverse=True,
    )[:pool_size]
    rejected = [
        {
            "stage": "metadata",
            "candidateId": item.get("id"),
            "name": item.get("name"),
            "reasons": item["financeRanking"]["reasons"],
        }
        for item in ranked
        if not item["financeRanking"]["eligible"]
    ]
    return selected, rejected


def deep_filter_finance_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    content = str(candidate.get("content") or "")
    reasons: list[str] = []
    policy = FINANCE_BOOTSTRAP["filter"]
    snapshot = candidate.get("snapshot", {})
    if snapshot.get("status") != "captured":
        reasons.append("未能拉取内容快照")
    if len(content) < policy["minContentLength"]:
        reasons.append("可分析内容过短")
    hits = _term_hits(_text(candidate, include_content=True))
    if len(hits) < 2:
        reasons.append("内容没有形成足够的股票分析语义覆盖")
    workflow_hits = sorted(term for term in WORKFLOW_TERMS if term in content.lower())
    if not workflow_hits:
        reasons.append("内容缺少可转换的 Agent、Skill 或 Workflow 结构")
    risk = scan_content(content, license_value=candidate.get("license", "unknown"))
    if risk["level"] == "high":
        reasons.extend(risk["reasons"] or ["内容静态风险过高"])
    return {
        "eligible": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "matchedTerms": hits,
        "workflowTerms": workflow_hits,
        "risk": risk,
    }


def finance_sops(sop_ids: list[str] | None = None) -> list[dict[str, Any]]:
    requested = set(sop_ids or FINANCE_BOOTSTRAP["defaultSopIds"])
    return [deepcopy(item) for item in FINANCE_BOOTSTRAP["sops"] if item["id"] in requested]
