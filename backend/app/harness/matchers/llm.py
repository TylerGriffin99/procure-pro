from __future__ import annotations

from app.harness.agent_runner import build_model, run_structured
from app.harness.matchers.base import MatchOutcome
from app.harness.phase_context import build_phase_context, render_system_prompt


async def run_llm_matches(*, phase_def, db, project_id, session_id) -> MatchOutcome:
    context = await build_phase_context(
        db=db, session_id=session_id, project_id=project_id, phase_def=phase_def,
    )
    system_prompt = render_system_prompt(phase_def, context)
    model = build_model(model_name=phase_def.model) if phase_def.model else None
    res = await run_structured(
        output_type=phase_def.output_schema,
        system_prompt=system_prompt,
        user_prompt=f"Process the input for phase: {phase_def.name}",
        model=model,
        phase_name=phase_def.name,
    )
    return MatchOutcome(
        output=res.output, output_json=res.output_json,
        input_tokens=res.input_tokens, output_tokens=res.output_tokens,
    )


class LlmMatcher:
    name = "llm"

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        return await run_llm_matches(
            phase_def=phase_def, db=db, project_id=project_id, session_id=session_id,
        )
