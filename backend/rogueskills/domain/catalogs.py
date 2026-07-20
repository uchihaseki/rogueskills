import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).with_name("data")


def _load(name: str) -> Any:
    with (DATA_DIR / name).open(encoding="utf-8") as source:
        return json.load(source)


EVOLUTION_CATALOG: dict[str, Any] = _load("evolution-catalog.json")
DISCOVERY_CATALOG: dict[str, Any] = _load("discovery-catalog.json")
PRESET_CONTRIBUTIONS: dict[str, Any] = _load("preset-contributions.json")
FINANCE_BOOTSTRAP: dict[str, Any] = _load("finance-bootstrap.json")
SEED_SKILLS: list[dict[str, Any]] = _load("seed-skills.json")

ARCHETYPES = EVOLUTION_CATALOG["ARCHETYPES"]
EVOLUTIONS = EVOLUTION_CATALOG["EVOLUTIONS"]
MONSTERS = EVOLUTION_CATALOG["MONSTERS"]
MUTATIONS = EVOLUTION_CATALOG["MUTATIONS"]
NODE_TYPES = EVOLUTION_CATALOG["NODE_TYPES"]
REGIONS = EVOLUTION_CATALOG["REGIONS"]
FINANCE_REGIONS = EVOLUTION_CATALOG["FINANCE_REGIONS"]
RUN_MODES = EVOLUTION_CATALOG["RUN_MODES"]
STAT_LABELS = EVOLUTION_CATALOG["STAT_LABELS"]

DOMAIN_SYNONYMS = DISCOVERY_CATALOG["DOMAIN_SYNONYMS"]
LOCAL_DISCOVERY_INDEX = DISCOVERY_CATALOG["LOCAL_DISCOVERY_INDEX"]
SOURCE_CONNECTORS = DISCOVERY_CATALOG["SOURCE_CONNECTORS"]
