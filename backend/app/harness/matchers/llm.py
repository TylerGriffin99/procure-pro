from __future__ import annotations

from app.clients.llm_client import LlmClient
from app.constants.enums import MatcherName
from app.harness.models import PhaseRun
from app.harness.phase_context import build_phase_context, render_system_prompt
from app.harness.schemas import MatchOutcome


async def match_with_llm(phase: PhaseRun, *, llm: LlmClient) -> MatchOutcome:
    phase_def = phase.phase_def
    context = await build_phase_context(
        db=phase.db, session_id=phase.session_id, project_id=phase.project_id, phase_def=phase_def
    )
    res = await llm.run_structured(
        output_type=phase_def.output_schema,
        system_prompt=render_system_prompt(phase_def, context),
        user_prompt=f"Process the input for phase: {phase_def.name}",
        model_name=phase_def.model,
        phase_name=phase_def.name,
    )
    return MatchOutcome(
        matcher=MatcherName.llm,
        output=res.output,
        output_json=res.output_json,
        input_tokens=res.input_tokens,
        output_tokens=res.output_tokens,
    )
