from dataclasses import dataclass
from typing import Protocol

from rogueskills.contracts.materials import NormalizedMaterial


class MaterialNormalizerError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class MaterialNormalizerInfo:
    mode: str
    provider: str
    model: str | None
    configured: bool


class MaterialNormalizer(Protocol):
    @property
    def info(self) -> MaterialNormalizerInfo: ...

    async def normalize(
        self,
        *,
        title: str | None,
        content: str,
        kind: str,
    ) -> NormalizedMaterial: ...


class UnavailableMaterialNormalizer:
    @property
    def info(self) -> MaterialNormalizerInfo:
        return MaterialNormalizerInfo(
            mode="llm",
            provider="openai-compatible",
            model=None,
            configured=False,
        )

    async def normalize(
        self,
        *,
        title: str | None,
        content: str,
        kind: str,
    ) -> NormalizedMaterial:
        del title, content, kind
        raise MaterialNormalizerError(
            "LLM_NORMALIZER_NOT_CONFIGURED",
            "SOP 语义转换需要配置 ROGUESKILLS_LLM_BASE_URL 和 ROGUESKILLS_LLM_MODEL。",
        )
