from __future__ import annotations

from app.harness.models import HarnessDefinition, HarnessType


class HarnessRegistry:
    def __init__(self) -> None:
        self._definitions: dict[HarnessType, HarnessDefinition] = {}

    def register(self, definition: HarnessDefinition) -> None:
        self._definitions[definition.harness_type] = definition

    def get(self, harness_type: HarnessType) -> HarnessDefinition | None:
        return self._definitions.get(harness_type)

    def list_types(self) -> list[HarnessDefinition]:
        return list(self._definitions.values())


harness_registry = HarnessRegistry()
