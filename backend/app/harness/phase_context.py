"""Shared phase-context building for harness phases and matchers."""

from __future__ import annotations

from collections.abc import Callable
from string import Template
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestError
from app.repos import harness_repo


async def load_workspace[T](db: AsyncSession, session_id: Any, path: str, parse: Callable[[str], T]) -> T:
    """An earlier phase always writes ``path``, so a missing, empty or schema-invalid file is fatal."""
    raw = await harness_repo.read_workspace_file(db, session_id, path)
    if not raw:
        raise BadRequestError(f"Workspace file {path} missing")
    try:
        return parse(raw)
    except ValidationError as e:
        raise BadRequestError(f"Workspace file {path} is invalid") from e


async def build_phase_context(*, db: Any, session_id: Any, project_id: Any, phase_def: Any) -> dict[str, str]:
    """Load workspace inputs and context-loader output into a template context."""
    context: dict[str, str] = {}
    for path in phase_def.workspace_inputs:
        content = await harness_repo.read_workspace_file(db, session_id, path)
        if not content:
            raise BadRequestError(f"Workspace file {path} missing for phase {phase_def.name}")
        var_name = path.replace(".json", "").replace("-", "_").replace("/", "_")
        context[f"workspace_{var_name}"] = content

    for loader in phase_def.context_loaders:
        extra = await loader(db, project_id, session_id)
        context.update(extra)
    return context


def render_system_prompt(phase_def: Any, context: dict[str, str]) -> str:
    return Template(phase_def.system_prompt_template).safe_substitute(**context)
