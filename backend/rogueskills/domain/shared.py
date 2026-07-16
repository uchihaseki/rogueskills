from collections.abc import Callable, Sequence
from math import floor

UINT32_MASK = 0xFFFFFFFF


def _imul(left: int, right: int) -> int:
    """Match JavaScript Math.imul and preserve the low unsigned 32 bits."""
    return (left * right) & UINT32_MASK


def hash_string(value: object) -> int:
    hash_value = 2_166_136_261
    encoded = str(value).encode("utf-16-le", errors="surrogatepass")
    for index in range(0, len(encoded), 2):
        code_unit = encoded[index] | (encoded[index + 1] << 8)
        hash_value ^= code_unit
        hash_value = _imul(hash_value, 16_777_619)
    return hash_value & UINT32_MASK


def create_rng(seed: object) -> Callable[[], float]:
    state = hash_string(seed) or 1

    def random() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & UINT32_MASK
        value = state
        value = _imul(value ^ (value >> 15), value | 1)
        value ^= (value + _imul(value ^ (value >> 7), value | 61)) & UINT32_MASK
        value &= UINT32_MASK
        return ((value ^ (value >> 14)) & UINT32_MASK) / 4_294_967_296

    return random


def pick[T](items: Sequence[T], random: Callable[[], float]) -> T:
    return items[floor(random() * len(items))]


def shuffle[T](items: Sequence[T], random: Callable[[], float]) -> list[T]:
    result = list(items)
    for index in range(len(result) - 1, 0, -1):
        target = floor(random() * (index + 1))
        result[index], result[target] = result[target], result[index]
    return result


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def round_number(value: float, precision: int = 0) -> int | float:
    factor = 10**precision
    rounded = floor(value * factor + 0.5) / factor
    return int(rounded) if precision == 0 else rounded
