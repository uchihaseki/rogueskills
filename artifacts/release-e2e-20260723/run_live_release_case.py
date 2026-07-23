"""Run Release Readiness through the production Case Pack against GitHub REST API."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "release-live.db"
REPOSITORY = os.getenv("ROGUESKILLS_RELEASE_REPOSITORY", "openai/openai-python")
REF = os.getenv("ROGUESKILLS_RELEASE_REF", "main")
BASE_BRANCH = os.getenv("ROGUESKILLS_RELEASE_BASE_BRANCH") or None


def write(name: str, value: object) -> None:
    (ROOT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def digest(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


try:
    settings = Settings(
        database_url=f"sqlite:///{DATABASE}",
        project_root=Path(__file__).resolve().parents[2],
    )
    app = create_app(settings)
    with TestClient(app) as api:
        preflight_response = api.get(
            "/api/case-runs/preflight?casePackId=release-readiness"
        )
        preflight = preflight_response.json()
        write("00-live-preflight.json", preflight)
        if preflight_response.status_code >= 400 or not preflight.get("ready"):
            raise RuntimeError(preflight)

        response = api.post(
            "/api/case-runs",
            json={
                "casePackId": "release-readiness",
                "casePackVersion": "1.0.0",
                "skillId": "release-readiness-base",
                "input": {
                    "repository": REPOSITORY,
                    "ref": REF,
                    "baseBranch": BASE_BRANCH,
                    "maxPullRequests": 20,
                },
                "mode": "live",
                "autoEvolve": False,
            },
        )
        payload = response.json()
        write("01-live-release-case.json", payload)
        if response.status_code >= 400:
            raise RuntimeError(payload)
        case = payload["caseRun"]
        stored = app.state.case_store.get(case["id"], include_bundle=True)
        source_bundle = (stored or {}).get("_sourceBundle")
        if not isinstance(source_bundle, dict):
            raise RuntimeError("Live Case did not persist a source bundle")
        pack = app.state.case_pack_registry.get("release-readiness")
        gateway_calls_after_live = getattr(pack.data_gateway, "calls", None)
        summary = {
            "caseId": case["id"],
            "casePackRef": f"{case['casePackId']}@{case['casePackVersion']}",
            "repository": case["repository"],
            "ref": case["ref"],
            "status": case["status"],
            "recommendation": (case.get("finalReport") or {}).get("recommendation"),
            "runtimeVerified": case["runtimeVerified"],
            "finalScore": (case.get("finalEvaluation") or {}).get("score"),
            "failedCaseIds": (case.get("finalEvaluation") or {}).get(
                "failedCaseIds"
            ),
            "baseSkillVersionId": case["baseSkillVersionId"],
            "evolvedSkillVersionId": case.get("evolvedSkillVersionId"),
            "sourceCount": len((case.get("finalReport") or {}).get("sources", [])),
            "factCount": len((case.get("finalReport") or {}).get("facts", [])),
            "checkRunCount": len(source_bundle.get("checkRuns", {}).get("check_runs", [])),
            "sourceBundleDigest": digest(source_bundle),
            "artifactId": (case.get("runtimeArtifact") or {}).get("id"),
            "artifactDigest": (case.get("runtimeArtifact") or {}).get("digest"),
            "liveGatewayCalls": gateway_calls_after_live,
        }
        write("02-live-release-summary.json", summary)
        if not case["runtimeVerified"]:
            raise RuntimeError(
                "Live report did not pass hard gates; inspect 01-live-release-case.json"
            )

        replay_response = api.post(
            f"/api/case-runs/{case['id']}/replay",
            json={"skillId": "release-readiness-base", "autoEvolve": False},
        )
        replay_payload = replay_response.json()
        write("03-verified-replay-case.json", replay_payload)
        if replay_response.status_code >= 400:
            raise RuntimeError(replay_payload)
        replay = replay_payload["caseRun"]
        gateway_calls_after_replay = getattr(pack.data_gateway, "calls", None)
        replay_summary = {
            "caseId": replay["id"],
            "mode": replay["mode"],
            "replayCaseId": replay["replayCaseId"],
            "runtimeVerified": replay["runtimeVerified"],
            "finalScore": (replay.get("finalEvaluation") or {}).get("score"),
            "recommendation": (replay.get("finalReport") or {}).get("recommendation"),
            "factsEqualToLive": (
                (replay.get("finalReport") or {}).get("facts")
                == (case.get("finalReport") or {}).get("facts")
            ),
            "sourcesEqualToLive": (
                (replay.get("finalReport") or {}).get("sources")
                == (case.get("finalReport") or {}).get("sources")
            ),
            "liveGatewayCallsBeforeReplay": gateway_calls_after_live,
            "liveGatewayCallsAfterReplay": gateway_calls_after_replay,
            "replayAvoidedLiveGateway": gateway_calls_after_live
            == gateway_calls_after_replay,
            "artifactDigest": (replay.get("runtimeArtifact") or {}).get("digest"),
        }
        write("04-verified-replay-summary.json", replay_summary)
        if not all(
            [
                replay["runtimeVerified"],
                replay_summary["factsEqualToLive"],
                replay_summary["sourcesEqualToLive"],
                replay_summary["replayAvoidedLiveGateway"],
            ]
        ):
            raise RuntimeError("Verified Replay did not preserve the Live evidence")
        print(json.dumps({"live": summary, "replay": replay_summary}, ensure_ascii=False))
except Exception as error:
    write("99-live-release-failure.json", {"type": type(error).__name__, "message": str(error)})
    raise
