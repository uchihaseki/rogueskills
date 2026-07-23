from __future__ import annotations

import hashlib
import json
from typing import Any

from rogueskills.contracts.case_runtime import CaseEvaluation, CaseRuntimeArtifact


class DigestRuntimeArtifactBuilder:
    """Build a portable immutable artifact for Case Packs without a platform preset compiler."""

    def build(
        self, case_run: dict[str, Any], evaluation: CaseEvaluation
    ) -> dict[str, Any]:
        payload = {
            "caseRunId": case_run["id"],
            "casePackId": case_run["casePackId"],
            "casePackVersion": case_run["casePackVersion"],
            "skillVersionId": case_run.get("evolvedSkillVersionId")
            or case_run["baseSkillVersionId"],
            "evaluationId": evaluation.evaluationId,
            "score": evaluation.score,
            "runtimeVerified": evaluation.runtimeVerified,
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
        artifact = CaseRuntimeArtifact(
            id=f"artifact-{digest.removeprefix('sha256:')[:20]}",
            caseRunId=case_run["id"],
            casePackId=case_run["casePackId"],
            casePackVersion=case_run["casePackVersion"],
            skillVersionId=payload["skillVersionId"],
            evaluationId=evaluation.evaluationId,
            digest=digest,
        )
        return {"runtimeArtifact": artifact.model_dump(mode="json")}
