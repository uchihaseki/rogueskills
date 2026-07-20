"""Verify the configured OpenAI-compatible Qwen endpoint with a finance SOP."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from rogueskills.adapters.llm_material_normalizer import (  # noqa: E402
    OpenAICompatibleMaterialNormalizer,
)
from rogueskills.settings import Settings  # noqa: E402


FINANCE_SOP = """# 股票财报快速复盘 SOP

目标：基于公开资料复盘上市公司最新财报，区分事实、假设和推断。

步骤：
1. 确认股票代码、交易所、财报期间、币种和分析基准日。
2. 从公司公告和监管披露核验收入、利润率、现金流和负债变化。
3. 识别一次性项目、会计口径变化和管理层指引变化。
4. 使用基准、乐观和悲观情景检查估值假设。
5. 输出证据、结论、风险、数据缺口和下一次跟踪事项。

约束：
- 不得编造财务数字、来源或市场一致预期。
- 每个时效性事实必须保留来源和日期。
- 不得把结果表述为保证收益或个性化投资建议。
"""


async def main() -> int:
    settings = Settings(_env_file=PROJECT_ROOT / ".env")
    if not settings.llm_base_url or not settings.llm_model:
        print("FAIL configuration: ROGUESKILLS_LLM_BASE_URL/ROGUESKILLS_LLM_MODEL missing")
        return 2

    print(f"CONFIG base_url={settings.llm_base_url}")
    print(f"CONFIG model={settings.llm_model}")
    print(f"CONFIG api_key={'configured' if settings.llm_api_key else 'not-required'}")

    headers: dict[str, str] = {"Accept": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(f"{settings.llm_base_url.rstrip('/')}/models", headers=headers)
            response.raise_for_status()
            model_ids = [
                str(item.get("id"))
                for item in response.json().get("data", [])
                if isinstance(item, dict) and item.get("id")
            ]
        except (httpx.HTTPError, ValueError, TypeError) as error:
            print(f"FAIL models: {type(error).__name__}: {error}")
            return 3

        print(f"MODELS count={len(model_ids)} ids={model_ids}")
        if settings.llm_model not in model_ids:
            print(f"FAIL model-not-found: {settings.llm_model}")
            return 4

        normalizer = OpenAICompatibleMaterialNormalizer(
            client,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        try:
            normalized = await normalizer.normalize(
                title="股票财报快速复盘 SOP",
                content=FINANCE_SOP,
                kind="finance-sop",
            )
        except Exception as error:  # The script reports the adapter's typed failure verbatim.
            print(f"FAIL normalization: {type(error).__name__}: {error}")
            return 5

    print("NORMALIZATION status=passed")
    print(f"NORMALIZATION title={normalized.title}")
    print(f"NORMALIZATION steps={len(normalized.steps)} constraints={len(normalized.constraints)}")
    print(f"NORMALIZATION tools={normalized.tools} tags={normalized.tags}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
