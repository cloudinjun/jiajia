from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .soul import _load_yaml


@dataclass(frozen=True)
class DecorationDefinition:
    id: str
    anchor: str = "upper_right"
    dx: float = 0.0
    dy: float = 0.0
    color: str = "#666666"
    lifetime: str = "identity"
    role: str = "identity_prop"
    shape_type: str = "status_dot"
    pulse: bool = False


@dataclass(frozen=True)
class DecorationManifest:
    decorations: dict[str, DecorationDefinition] = field(default_factory=dict)

    def get(self, decoration_id: str) -> DecorationDefinition | None:
        return self.decorations.get(_key(decoration_id))


def load_decoration_manifest(path: Path) -> DecorationManifest:
    data = _load_yaml(path) if path.exists() else {}
    raw_items = _dict(data.get("decorations"))
    decorations = {
        _key(name): _parse_definition(_key(name), raw)
        for name, raw in raw_items.items()
        if isinstance(raw, dict)
    }
    return DecorationManifest(decorations)


def _parse_definition(name: str, raw: dict[str, Any]) -> DecorationDefinition:
    return DecorationDefinition(
        id=name,
        anchor=_key(raw.get("anchor")) or "upper_right",
        dx=_float(raw.get("dx")),
        dy=_float(raw.get("dy")),
        color=str(raw.get("color") or "#666666"),
        lifetime=_key(raw.get("lifetime")) or "identity",
        role=_key(raw.get("role")) or "identity_prop",
        shape_type=_key(raw.get("shape_type")) or "status_dot",
        pulse=bool(raw.get("pulse", False)),
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
