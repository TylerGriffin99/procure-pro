"""Shared phase-context building for harness phases and matchers."""
from __future__ import annotations

from string import Template
from typing import Any

from app.repos import harness_repo


async def build_phase_context(*, db: Any, session_id: Any, project_id: Any, phase_def: Any) -> dict[str, str]:
    """Load workspace inputs and context-loader output into a template context."""
    context: dict[str, str] = {}
    for path in phase_def.workspace_inputs:
        content = await harness_repo.read_workspace_file(db, session_id, path)
        var_name = path.replace(".json", "").replace("-", "_").replace("/", "_")
        context[f"workspace_{var_name}"] = content or "FILE NOT FOUND"

    for loader in phase_def.context_loaders:
        extra = await loader(db, project_id, session_id)
        context.update(extra)
    return context


def render_system_prompt(phase_def: Any, context: dict[str, str]) -> str:
    return Template(phase_def.system_prompt_template).safe_substitute(**context)
