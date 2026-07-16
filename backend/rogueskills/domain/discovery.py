import math
import re
import unicodedata
from collections.abc import Callable, Iterable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from rogueskills.contracts.materials import NormalizedMaterial

from .catalogs import DOMAIN_SYNONYMS, LOCAL_DISCOVERY_INDEX, SOURCE_CONNECTORS
from .shared import clamp, hash_string, round_number

FILTER_PATTERN = re.compile(r'\b(source|type|license|tag):(?:"([^"]+)"|(\S+))', re.IGNORECASE)
HIGH_RISK_PATTERNS = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I), "包含提示注入式指令"),
    (re.compile(r"忽略(?:以上|之前|前面).{0,8}(?:指令|要求|规则)", re.I), "包含提示注入式指令"),
    (re.compile(r"\brm\s+-rf\s+[/~*]", re.I), "包含破坏性删除命令"),
    (re.compile(r"(?:curl|wget)[^\n|]{0,180}\|\s*(?:sh|bash)", re.I), "包含远程下载并执行命令"),
    (
        re.compile(
            r"""\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*["'][^"']{8,}""", re.I
        ),
        "疑似包含明文 Secret",
    ),
]
MEDIUM_RISK_PATTERNS = [
    (re.compile(r"\bsudo\b", re.I), "包含提权命令"),
    (re.compile(r"\beval\s*\(", re.I), "包含动态代码执行"),
    (re.compile(r"disable.{0,20}(?:security|sandbox|guard)", re.I), "建议关闭安全控制"),
    (re.compile(r"关闭.{0,12}(?:安全|沙箱|权限检查)", re.I), "建议关闭安全控制"),
]


def _unique(items: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _normalize_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized).split()
    )


def tokenize(value: object) -> list[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    tokens = list(dict.fromkeys(normalized.split()))
    cjk_groups = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]{2,}", normalized)
    for group in cjk_groups:
        for index in range(len(group) - 1):
            token = group[index : index + 2]
            if token not in tokens:
                tokens.append(token)
    return tokens


def parse_search_query(query: str) -> dict[str, Any]:
    filters: dict[str, list[str]] = {"source": [], "type": [], "license": [], "tag": []}
    for match in FILTER_PATTERN.finditer(query):
        filters[match.group(1).lower()].append((match.group(2) or match.group(3)).lower())
    text = " ".join(FILTER_PATTERN.sub(" ", query).split())
    return {"text": text, "filters": filters}


def expand_query_terms(query: str) -> list[str]:
    base = tokenize(query)
    expanded = list(base)
    for term in base:
        for synonym in DOMAIN_SYNONYMS.get(term, []):
            for item in tokenize(synonym):
                if item not in expanded:
                    expanded.append(item)
    return expanded


def scan_content(content: str, *, license_value: str = "unknown") -> dict[str, Any]:
    reasons = [reason for pattern, reason in HIGH_RISK_PATTERNS if pattern.search(content)]
    level = "high" if reasons else "low"
    if not reasons:
        reasons = [reason for pattern, reason in MEDIUM_RISK_PATTERNS if pattern.search(content)]
        if reasons:
            level = "medium"
    if not license_value or license_value in ("unknown", "NOASSERTION"):
        reasons.append("许可证未知，不能直接发布")
        if level == "low":
            level = "medium"
    return {
        "level": level,
        "reasons": _unique(reasons),
        "executableContent": bool(
            re.search(r"```(?:bash|sh|shell|powershell|python|javascript|js)\b", content, re.I)
        ),
    }


def _calculate_convertibility(candidate: dict[str, Any]) -> float:
    content = f"{candidate.get('name', '')}\n{candidate.get('summary', '')}\n{candidate.get('content', '')}"
    score = 18
    patterns = [
        (r"(?:workflow|steps?|procedure|流程|步骤|操作)", 24),
        (r"(?:goal|objective|目的|目标)", 14),
        (r"(?:input|输入|前置条件|prerequisite)", 10),
        (r"(?:output|结果|输出|deliverable)", 10),
        (r"(?:constraint|must|never|安全|约束|必须|不得|禁止)", 14),
        (r"(?:test|acceptance|example|验收|示例)", 10),
    ]
    for pattern, gain in patterns:
        if re.search(pattern, content, re.I):
            score += gain
    return clamp(score, 0, 100)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _calculate_freshness(updated_at: str | None, now: datetime) -> int:
    if not updated_at:
        return 35
    age_days = max(0, (now - _parse_datetime(updated_at)).total_seconds() / 86_400)
    if age_days <= 30:
        return 100
    if age_days <= 180:
        return 82
    if age_days <= 365:
        return 66
    if age_days <= 730:
        return 48
    return 30


def _calculate_relevance(candidate: dict[str, Any], query_text: str) -> float:
    terms = expand_query_terms(query_text)
    if not terms:
        return 60
    fields = [
        (_normalize_text(candidate.get("name", "")), 5),
        (_normalize_text(" ".join(candidate.get("tags", []))), 4),
        (_normalize_text(candidate.get("summary", "")), 2.5),
        (_normalize_text(candidate.get("content", "")), 1),
    ]
    matched_weight = 0.0
    for term in terms:
        normalized_term = _normalize_text(term)
        matched_weight += max(
            (weight for field, weight in fields if normalized_term in field), default=0
        )
    exact_bonus = (
        18
        if _normalize_text(query_text)
        in _normalize_text(f"{candidate.get('name', '')} {candidate.get('summary', '')}")
        else 0
    )
    return clamp(round_number(matched_weight / max(1, len(terms) * 5) * 92 + exact_bonus), 0, 100)


def _calculate_quality(candidate: dict[str, Any]) -> float:
    signals = candidate.get("signals", {})
    completeness = signals.get("completeness", _calculate_convertibility(candidate))
    stars = signals.get("stars", 0)
    community = clamp(math.log10(stars + 1) * 22, 0, 100)
    content_length = len(candidate.get("content", ""))
    documentation = 90 if content_length > 800 else 70 if content_length > 200 else 45
    return round_number(completeness * 0.55 + community * 0.2 + documentation * 0.25)


def _calculate_trust(candidate: dict[str, Any]) -> float:
    signals = candidate.get("signals", {})
    trust = 92 if signals.get("official") else 78 if candidate.get("sourceId") == "builtin" else 55
    if candidate.get("license") not in (None, "unknown", "NOASSERTION"):
        trust += 6
    if str(candidate.get("url", "")).startswith("https://"):
        trust += 2
    return clamp(trust, 0, 100)


def matches_filters(candidate: dict[str, Any], filters: dict[str, list[str]]) -> bool:
    if filters["source"] and str(candidate.get("sourceId", "")).lower() not in filters["source"]:
        return False
    if filters["type"] and str(candidate.get("kind", "")).lower() not in filters["type"]:
        return False
    if filters["license"] and str(candidate.get("license", "")).lower() not in filters["license"]:
        return False
    candidate_tags = [str(tag).lower() for tag in candidate.get("tags", [])]
    return not filters["tag"] or all(tag in candidate_tags for tag in filters["tag"])


def rank_candidate(
    candidate: dict[str, Any],
    query: str,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    parsed = parse_search_query(query)
    risk = scan_content(
        candidate.get("content") or candidate.get("summary") or "",
        license_value=candidate.get("license", "unknown"),
    )
    relevance = _calculate_relevance(candidate, parsed["text"])
    quality = _calculate_quality(candidate)
    trust = _calculate_trust(candidate)
    convertibility = _calculate_convertibility(candidate)
    now = (clock or (lambda: datetime.now(UTC)))()
    freshness = _calculate_freshness(candidate.get("updatedAt"), now)
    risk_penalty = 38 if risk["level"] == "high" else 14 if risk["level"] == "medium" else 0
    total = clamp(
        round_number(
            relevance * 0.35
            + quality * 0.2
            + trust * 0.2
            + convertibility * 0.15
            + freshness * 0.1
            - risk_penalty
        ),
        0,
        100,
    )
    return {
        **deepcopy(candidate),
        "risk": risk,
        "ranking": {
            "relevance": relevance,
            "quality": quality,
            "trust": trust,
            "convertibility": convertibility,
            "freshness": freshness,
            "riskPenalty": risk_penalty,
            "total": total,
        },
    }


def _canonical_key(candidate: dict[str, Any]) -> str:
    if candidate.get("url"):
        return _normalize_text(str(candidate["url"]).rstrip("/"))
    return f"{_normalize_text(candidate.get('name', ''))}|{_normalize_text(candidate.get('author', ''))}"


def deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = _canonical_key(candidate)
        existing = groups.get(key)
        if not existing or candidate.get("ranking", {}).get("total", 0) > existing.get(
            "ranking", {}
        ).get("total", 0):
            groups[key] = candidate
    return list(groups.values())


def search_local_index(
    query: str,
    *,
    clock: Callable[[], datetime] | None = None,
) -> list[dict[str, Any]]:
    parsed = parse_search_query(query)
    results = [rank_candidate(candidate, query, clock=clock) for candidate in LOCAL_DISCOVERY_INDEX]
    results = [candidate for candidate in results if matches_filters(candidate, parsed["filters"])]
    results = [
        candidate
        for candidate in results
        if not parsed["text"] or candidate["ranking"]["relevance"] >= 12
    ]
    return sorted(results, key=lambda candidate: candidate["ranking"]["total"], reverse=True)


def content_fingerprint(content: object) -> str:
    return f"{hash_string(content):08x}"


def _section_kind(heading: str) -> str:
    mappings = [
        (r"(?:workflow|steps?|procedure|process|操作|步骤|流程|checklist|清单)", "steps"),
        (r"(?:constraint|safety|rules?|注意|约束|安全|禁止|要求)", "constraints"),
        (r"(?:input|prerequisite|输入|前置)", "inputs"),
        (r"(?:output|deliverable|输出|交付|结果)", "outputs"),
        (r"(?:goal|objective|purpose|目标|目的)", "goal"),
        (r"(?:example|示例)", "examples"),
    ]
    return next((kind for pattern, kind in mappings if re.search(pattern, heading, re.I)), "other")


def _clean_list_item(line: str) -> str:
    return re.sub(r"^\s*(?:[-*+] |\d+[.)]\s*)", "", line).strip()


def _extract_tools(content: str) -> list[str]:
    known = [
        "Browser",
        "Search",
        "OCR",
        "API",
        "SQL",
        "GitHub",
        "Slack",
        "Jira",
        "Python",
        "Playwright",
        "Excel",
    ]
    return [tool for tool in known if re.search(rf"\b{re.escape(tool)}\b", content, re.I)]


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).lower()
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return ascii_slug if len(ascii_slug) >= 3 else f"skill-{content_fingerprint(value)}"


def _infer_capabilities(
    content: str, tools: list[str], completeness: float
) -> list[dict[str, Any]]:
    levels = {
        "quality": 38 + completeness * 0.32,
        "robustness": 34 + completeness * 0.18,
        "speed": 45,
        "efficiency": 45,
        "security": 28,
        "vision": 10,
        "structure": 34,
    }
    evidence: dict[str, list[str]] = {stat: [] for stat in levels}
    rules = [
        (
            r"(?:validate|verify|校验|验证|检查)",
            {"quality": 9, "robustness": 6},
            ("quality", "材料包含验证步骤"),
        ),
        (
            r"(?:retry|fallback|rollback|重试|回退|降级|异常)",
            {"robustness": 18},
            ("robustness", "材料包含失败恢复策略"),
        ),
        (
            r"(?:parallel|cache|batch|并行|缓存|批量)",
            {"speed": 14, "efficiency": 8},
            ("speed", "材料包含吞吐优化策略"),
        ),
        (
            r"(?:budget|token|cost|limit|预算|成本|限额)",
            {"efficiency": 16},
            ("efficiency", "材料声明资源或成本限制"),
        ),
        (
            r"(?:never|must not|permission|injection|secret|不得|禁止|权限|敏感|安全)",
            {"security": 24},
            ("security", "材料包含安全或权限约束"),
        ),
        (
            r"(?:schema|json|structured|checklist|字段|结构化|清单)",
            {"structure": 24},
            ("structure", "材料声明结构化输出或检查清单"),
        ),
    ]
    for pattern, effects, evidence_item in rules:
        if re.search(pattern, content, re.I):
            for stat, gain in effects.items():
                levels[stat] += gain
            evidence[evidence_item[0]].append(evidence_item[1])
    if (
        re.search(r"(?:ocr|screenshot|image|vision|截图|图片|视觉)", content, re.I)
        or "OCR" in tools
    ):
        levels["vision"] += 48
        evidence["vision"].append("材料包含视觉处理能力")
    labels = {
        "quality": "Task Quality",
        "robustness": "Robustness",
        "speed": "Execution Speed",
        "efficiency": "Cost Efficiency",
        "security": "Safety & Permission",
        "vision": "Visual Understanding",
        "structure": "Structured Output",
    }
    return [
        {
            "id": stat,
            "label": labels[stat],
            "level": round_number(clamp(level, 0, 100)),
            "tags": [stat],
            "evidence": evidence[stat],
        }
        for stat, level in levels.items()
    ]


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n?", content)
    if not match:
        return {}, content
    attributes: dict[str, str] = {}
    for line in match.group(1).splitlines():
        entry = re.match(r"^([a-zA-Z][\w-]*):\s*(.+)$", line)
        if entry:
            attributes[entry.group(1)] = re.sub(
                r"""^(["'])(.*)\1$""", r"\2", entry.group(2).strip()
            )
    return attributes, content[len(match.group(0)) :]


def convert_material_to_skill(
    *,
    title: str | None,
    content: str,
    source: dict[str, Any] | None = None,
    license_value: str = "unknown",
    kind: str = "sop",
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    source = source or {"platform": "Manual SOP", "url": None, "author": "Unknown"}
    attributes, body = _parse_frontmatter(content or "")
    effective_license = attributes.get("license") or license_value
    heading_match = re.search(r"^#\s+(.+)$", body, re.M)
    normalized_title = (
        (title or "").strip()
        or attributes.get("name")
        or (heading_match.group(1).strip() if heading_match else None)
        or "Untitled Skill"
    )
    lines = body.replace("\r\n", "\n").split("\n")
    sections: dict[str, list[str]] = {
        key: [] for key in ("steps", "constraints", "inputs", "outputs", "examples", "goal")
    }
    current_section = "other"
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            current_section = _section_kind(heading.group(1))
            continue
        numbered = bool(re.match(r"^\d+[.)]\s+", line))
        bullet = bool(re.match(r"^[-*+]\s+", line))
        item = _clean_list_item(line)
        if numbered or (bullet and current_section == "steps"):
            sections["steps"].append(item)
            continue
        if bullet and current_section in ("constraints", "inputs", "outputs", "examples"):
            sections[current_section].append(item)
            continue
        if current_section in sections and current_section != "steps":
            sections[current_section].append(item)
        if re.search(r"(?:必须|不得|禁止|切勿|\bmust\b|\bnever\b|\bshould not\b)", item, re.I):
            sections["constraints"].append(item)
    if not sections["steps"]:
        sections["steps"] = [
            _clean_list_item(line.strip()) for line in lines if re.match(r"^[-*+]\s+", line.strip())
        ][:12]
    first_paragraph = next(
        (
            line.strip()
            for line in lines
            if line.strip()
            and not line.strip().startswith("#")
            and not re.match(r"^[-*+\d]", line.strip())
        ),
        None,
    )
    description = (
        attributes.get("description")
        or " ".join(sections["goal"])
        or first_paragraph
        or f"由 {kind} 材料转换的候选 Skill"
    )[:360]
    risk = scan_content(content, license_value=effective_license)
    fingerprint = content_fingerprint(content)
    completeness = clamp(
        20
        + min(36, len(sections["steps"]) * 7)
        + min(16, len(sections["constraints"]) * 4)
        + (12 if sections["goal"] or first_paragraph else 0)
        + (8 if sections["inputs"] else 0)
        + (8 if sections["outputs"] else 0)
        + (6 if sections["examples"] else 0),
        0,
        100,
    )
    tools = _extract_tools(content)
    captured_at = source.get("capturedAt") or (
        clock or (lambda: datetime.now(UTC))
    )().isoformat().replace("+00:00", "Z")
    return {
        "schemaVersion": "1.0.0",
        "id": f"{_slugify(normalized_title)}-{fingerprint[:6]}",
        "name": normalized_title,
        "description": description,
        "status": "quarantine",
        "metadata": {
            "category": kind,
            "license": effective_license,
            "tags": _unique([*tokenize(normalized_title)[:6], "generated-from-material"]),
            "completeness": completeness,
        },
        "prompt": {
            "role": f"You are responsible for executing the {normalized_title} workflow.",
            "objective": description,
            "instruction": "Follow the workflow in order, respect every constraint, and return the declared output.",
        },
        "workflow": {
            "steps": [
                {"id": f"step-{index + 1}", "order": index + 1, "instruction": instruction}
                for index, instruction in enumerate(_unique(sections["steps"])[:20])
            ]
        },
        "inputs": _unique(sections["inputs"])[:12],
        "outputs": _unique(sections["outputs"])[:12],
        "constraints": _unique(sections["constraints"])[:20],
        "examples": _unique(sections["examples"])[:8],
        "tools": tools,
        "capabilities": _infer_capabilities(content, tools, completeness),
        "testCases": [
            {"id": "happy-path", "purpose": "验证标准输入下能完整执行所有步骤", "status": "draft"},
            {"id": "missing-input", "purpose": "验证输入缺失时不会臆造关键信息", "status": "draft"},
            {"id": "constraint-check", "purpose": "验证高风险情况下仍遵守约束", "status": "draft"},
        ],
        "evaluation": {
            "status": "not_run",
            "requiredGates": ["static-safety", "license-review", "benchmark", "human-review"],
        },
        "provenance": {
            "platform": source.get("platform", "Manual SOP"),
            "url": source.get("url"),
            "author": source.get("author", "Unknown"),
            "revision": source.get("revision"),
            "artifactPaths": source.get("artifactPaths", []),
            "fingerprint": fingerprint,
            "capturedAt": captured_at,
        },
        "risk": risk,
    }


def _capabilities_from_normalized(
    material: NormalizedMaterial,
    completeness: float,
) -> list[dict[str, Any]]:
    constraint_count = len(material.constraints)
    acceptance_count = len(material.acceptanceCriteria)
    tool_names = {tool.casefold() for tool in material.tools}
    visual = any(name in tool_names for name in {"ocr", "vision", "screenshot"})
    levels = {
        "quality": clamp(45 + completeness * 0.3 + min(12, acceptance_count * 3), 0, 100),
        "robustness": clamp(35 + min(24, constraint_count * 3), 0, 100),
        "speed": 45,
        "efficiency": 45,
        "security": clamp(28 + min(30, constraint_count * 6), 0, 100),
        "vision": 58 if visual else 10,
        "structure": clamp(
            34 + (20 if material.outputs else 0) + min(18, acceptance_count * 3),
            0,
            100,
        ),
    }
    labels = {
        "quality": "Task Quality",
        "robustness": "Robustness",
        "speed": "Execution Speed",
        "efficiency": "Cost Efficiency",
        "security": "Safety & Permission",
        "vision": "Visual Understanding",
        "structure": "Structured Output",
    }
    evidence = {
        "quality": material.acceptanceCriteria[:3],
        "robustness": material.constraints[:3],
        "speed": [],
        "efficiency": [],
        "security": material.constraints[:3],
        "vision": material.tools if visual else [],
        "structure": [*material.outputs[:2], *material.acceptanceCriteria[:1]],
    }
    return [
        {
            "id": stat,
            "label": labels[stat],
            "level": round_number(level),
            "tags": [stat],
            "evidence": evidence[stat],
        }
        for stat, level in levels.items()
    ]


def build_skill_genome_from_normalized(
    *,
    material: NormalizedMaterial,
    original_content: str,
    title: str | None,
    source: dict[str, Any] | None = None,
    license_value: str = "unknown",
    kind: str = "sop",
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Build a deterministic Genome after semantic normalization has completed."""
    source = source or {"platform": "Manual SOP", "url": None, "author": "Unknown"}
    normalized_title = (title or "").strip() or material.title
    completeness = clamp(
        20
        + min(36, len(material.steps) * 7)
        + min(16, len(material.constraints) * 4)
        + 12
        + (8 if material.inputs else 0)
        + (8 if material.outputs else 0)
        + (6 if material.examples else 0),
        0,
        100,
    )
    fingerprint = content_fingerprint(original_content)
    captured_at = source.get("capturedAt") or (
        clock or (lambda: datetime.now(UTC))
    )().isoformat().replace("+00:00", "Z")
    risk = scan_content(original_content, license_value=license_value)
    acceptance = material.acceptanceCriteria or [
        "标准输入下完整执行所有步骤并产生声明的输出",
        "输入缺失时不臆造关键信息",
        "高风险输入下仍遵守全部约束",
    ]
    return {
        "schemaVersion": "1.0.0",
        "id": f"{_slugify(normalized_title)}-{fingerprint[:6]}",
        "name": normalized_title,
        "description": material.description,
        "status": "quarantine",
        "metadata": {
            "category": kind,
            "license": license_value,
            "tags": _unique([*material.tags, "llm-normalized"]),
            "completeness": completeness,
        },
        "prompt": {
            "role": material.role,
            "objective": material.objective,
            "instruction": material.instruction,
        },
        "workflow": {
            "steps": [
                {
                    "id": f"step-{index + 1}",
                    "order": index + 1,
                    "instruction": instruction,
                }
                for index, instruction in enumerate(material.steps)
            ]
        },
        "inputs": material.inputs,
        "outputs": material.outputs,
        "constraints": material.constraints,
        "examples": material.examples,
        "tools": material.tools,
        "capabilities": _capabilities_from_normalized(material, completeness),
        "testCases": [
            {
                "id": f"acceptance-{index + 1}",
                "purpose": criterion,
                "status": "draft",
            }
            for index, criterion in enumerate(acceptance[:12])
        ],
        "evaluation": {
            "status": "not_run",
            "requiredGates": [
                "static-safety",
                "license-review",
                "benchmark",
                "human-review",
            ],
        },
        "provenance": {
            "platform": source.get("platform", "Manual SOP"),
            "url": source.get("url"),
            "author": source.get("author", "Unknown"),
            "revision": source.get("revision"),
            "artifactPaths": source.get("artifactPaths", []),
            "fingerprint": fingerprint,
            "capturedAt": captured_at,
            "normalizer": "llm",
        },
        "risk": risk,
    }


def candidate_to_skill_genome(
    candidate: dict[str, Any], *, clock: Callable[[], datetime] | None = None
) -> dict[str, Any]:
    content = candidate.get("content") or candidate.get("summary") or ""
    snapshot = candidate.get("snapshot") or {
        "status": "captured" if content else "metadata_only",
        "fingerprint": content_fingerprint(content),
        "artifactPaths": [],
    }
    has_skill_artifact = any(
        re.search(r"(^|/)skill\.md$", path, re.I) for path in snapshot.get("artifactPaths", [])
    )
    genome = convert_material_to_skill(
        title=None if has_skill_artifact else candidate.get("name"),
        content=content,
        kind=candidate.get("kind", "skill"),
        license_value=candidate.get("license", "unknown"),
        source={
            "platform": candidate.get("platform"),
            "url": candidate.get("url"),
            "author": candidate.get("author"),
            "revision": snapshot.get("revision"),
            "artifactPaths": snapshot.get("artifactPaths", []),
            "capturedAt": snapshot.get("fetchedAt"),
        },
        clock=clock,
    )
    genome["discovery"] = {
        "candidateId": candidate.get("id"),
        "sourceId": candidate.get("sourceId"),
        "ranking": candidate.get("ranking"),
        "snapshot": snapshot,
    }
    return genome


def connector_by_id(connector_id: str) -> dict[str, Any] | None:
    return next(
        (connector for connector in SOURCE_CONNECTORS if connector["id"] == connector_id), None
    )
