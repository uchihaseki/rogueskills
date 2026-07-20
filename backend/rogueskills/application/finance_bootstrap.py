from __future__ import annotations

from typing import Any

from rogueskills.adapters.discovery_gateway import DiscoveryGateway
from rogueskills.domain.catalogs import FINANCE_BOOTSTRAP
from rogueskills.domain.discovery import content_fingerprint, deduplicate_candidates
from rogueskills.domain.finance import (
    deep_filter_finance_candidate,
    finance_sops,
    select_finance_candidates,
)
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError
from .services import MaterialService, SkillService


class FinanceBootstrapService:
    def __init__(
        self,
        *,
        gateway: DiscoveryGateway,
        materials: MaterialService,
        skills: SkillService,
        repository: SkillRepository,
    ) -> None:
        self.gateway = gateway
        self.materials = materials
        self.skills = skills
        self.repository = repository

    def _existing_skill(self, *, source_url: str, fingerprint: str) -> dict[str, Any] | None:
        return next(
            (
                skill
                for skill in self.repository.list_skills()
                if skill.get("sourceUrl") == source_url or skill.get("fingerprint") == fingerprint
            ),
            None,
        )

    def _admit_existing(
        self, skill: dict[str, Any], *, auto_promote: bool
    ) -> dict[str, Any]:
        if skill["status"] == "initial" or not auto_promote:
            return {
                "skillId": skill["id"],
                "skillVersionId": skill["currentVersionId"],
                "status": skill["status"],
                "action": "reused",
                "evaluation": skill.get("evaluations", [None])[0]
                if skill.get("evaluations")
                else None,
            }
        evaluation, result = self.skills.benchmark(skill["id"])
        current = skill
        if result["passed"]:
            current = self.skills.promote(
                skill["id"], evaluation["id"], skill["currentVersionId"]
            )
        return {
            "skillId": current["id"],
            "skillVersionId": current["currentVersionId"],
            "status": current["status"],
            "action": "promoted" if current["status"] == "initial" else "benchmarked",
            "evaluation": evaluation,
        }

    async def _normalize_store_and_admit(
        self,
        *,
        title: str,
        content: str,
        source: dict[str, Any],
        license_value: str,
        kind: str,
        source_id: str,
        auto_promote: bool,
        discovery: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fingerprint = content_fingerprint(content)
        source_url = str(source.get("url") or f"finance-material://{fingerprint}")
        existing = self._existing_skill(source_url=source_url, fingerprint=fingerprint)
        if existing:
            return self._admit_existing(existing, auto_promote=auto_promote)

        genome, normalization = await self.materials.convert(
            title=title,
            content=content,
            source=source,
            license_value=license_value,
            kind=kind,
        )
        genome["metadata"]["category"] = "finance"
        genome["metadata"]["tags"] = list(
            dict.fromkeys([*genome["metadata"].get("tags", []), "finance", "stock-analysis"])
        )
        if discovery:
            genome["discovery"] = discovery
        stored = self.skills.create_quarantine(
            genome,
            source_id=source_id,
            snapshot_content=content,
        )
        evaluation, result = self.skills.benchmark(stored["id"])
        current = stored
        if auto_promote and result["passed"]:
            current = self.skills.promote(
                stored["id"], evaluation["id"], stored["currentVersionId"]
            )
        return {
            "skillId": current["id"],
            "skillVersionId": current["currentVersionId"],
            "name": current["name"],
            "status": current["status"],
            "action": "promoted" if current["status"] == "initial" else "stored",
            "evaluation": evaluation,
            "normalization": normalization,
        }

    async def run(
        self,
        *,
        max_community_skills: int = 2,
        sop_ids: list[str] | None = None,
        auto_promote: bool = True,
    ) -> dict[str, Any]:
        normalizer = self.materials.normalizer.info
        if not normalizer.configured:
            raise ApplicationError(
                "LLM_NORMALIZER_NOT_CONFIGURED",
                "金融 Skill 初始化需要配置 LLM Normalizer。",
                status_code=503,
            )

        candidates: list[dict[str, Any]] = []
        provider_status: list[dict[str, Any]] = []
        for query in FINANCE_BOOTSTRAP["queries"]:
            result = await self.gateway.federated_search(
                query,
                source_ids=["github"],
                limit_per_source=12,
            )
            candidates.extend(result["results"])
            provider_status.extend({**item, "query": query} for item in result["status"])

        unique_candidates = deduplicate_candidates(candidates)
        metadata_pool, rejected = select_finance_candidates(
            unique_candidates,
            pool_size=max(6, max_community_skills * 3),
        )
        community: list[dict[str, Any]] = []
        hydrated_count = 0
        for candidate in metadata_pool:
            if len(community) >= max_community_skills:
                break
            hydrated = await self.gateway.hydrate_candidate(candidate)
            hydrated_count += 1
            decision = deep_filter_finance_candidate(hydrated)
            if not decision["eligible"]:
                rejected.append(
                    {
                        "stage": "content",
                        "candidateId": candidate.get("id"),
                        "name": candidate.get("name"),
                        "reasons": decision["reasons"],
                    }
                )
                continue
            try:
                admitted = await self._normalize_store_and_admit(
                    title=hydrated["name"],
                    content=hydrated["content"],
                    source={
                        "platform": hydrated.get("platform", "GitHub"),
                        "url": hydrated.get("url"),
                        "author": hydrated.get("author", "Unknown"),
                        "revision": hydrated.get("snapshot", {}).get("revision"),
                        "artifactPaths": hydrated.get("snapshot", {}).get(
                            "artifactPaths", []
                        ),
                        "capturedAt": hydrated.get("snapshot", {}).get("fetchedAt"),
                    },
                    license_value=hydrated["license"],
                    kind="finance-community-skill",
                    source_id="finance-community",
                    auto_promote=auto_promote,
                    discovery={
                        "candidateId": hydrated.get("id"),
                        "sourceId": hydrated.get("sourceId"),
                        "ranking": hydrated.get("ranking"),
                        "financeRanking": hydrated.get("financeRanking"),
                        "snapshot": hydrated.get("snapshot"),
                    },
                )
                community.append(
                    {
                        "candidate": {
                            "id": hydrated.get("id"),
                            "name": hydrated.get("name"),
                            "url": hydrated.get("url"),
                            "license": hydrated.get("license"),
                            "stars": hydrated.get("signals", {}).get("stars", 0),
                            "financeRanking": hydrated.get("financeRanking"),
                        },
                        **admitted,
                    }
                )
            except ApplicationError as error:
                rejected.append(
                    {
                        "stage": "normalization_or_admission",
                        "candidateId": candidate.get("id"),
                        "name": candidate.get("name"),
                        "reasons": [f"{error.code}: {error.message}"],
                    }
                )

        sop_results: list[dict[str, Any]] = []
        for sop in finance_sops(sop_ids):
            try:
                admitted = await self._normalize_store_and_admit(
                    title=sop["title"],
                    content=sop["content"],
                    source={
                        "platform": "RogueSkills Finance SOP",
                        "url": f"finance-sop://{sop['id']}",
                        "author": "RogueSkills",
                        "revision": "v1",
                        "artifactPaths": [f"finance/{sop['id']}.md"],
                    },
                    license_value=sop["license"],
                    kind="finance-sop",
                    source_id="finance-sop",
                    auto_promote=auto_promote,
                )
                sop_results.append({"sopId": sop["id"], "title": sop["title"], **admitted})
            except ApplicationError as error:
                sop_results.append(
                    {
                        "sopId": sop["id"],
                        "title": sop["title"],
                        "status": "failed",
                        "error": {"code": error.code, "message": error.message},
                    }
                )

        initial_ids = [
            item["skillId"]
            for item in [*community, *sop_results]
            if item.get("status") == "initial"
        ]
        return {
            "scenario": FINANCE_BOOTSTRAP["scenario"],
            "model": {
                "mode": normalizer.mode,
                "provider": normalizer.provider,
                "model": normalizer.model,
                "configured": normalizer.configured,
            },
            "queries": FINANCE_BOOTSTRAP["queries"],
            "providerStatus": provider_status,
            "summary": {
                "discovered": len(unique_candidates),
                "metadataSelected": len(metadata_pool),
                "hydrated": hydrated_count,
                "communityStored": len(community),
                "sopsProcessed": len(sop_results),
                "initialSkills": len(initial_ids),
                "rejected": len(rejected),
            },
            "community": community,
            "sops": sop_results,
            "rejected": rejected,
            "initialSkillIds": initial_ids,
        }
