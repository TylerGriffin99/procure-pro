from __future__ import annotations

from app.clients.llm_client import LlmClient
from app.config import settings
from app.harness.phase_context import build_phase_context, render_system_prompt
from app.harness.schemas import MatchOutcome


async def run_llm_matches(*, phase_def, db, project_id, session_id, llm: LlmClient) -> MatchOutcome:
    context = await build_phase_context(db=db, session_id=session_id, project_id=project_id, phase_def=phase_def)
    system_prompt = render_system_prompt(phase_def, context)
    res = await llm.run_structured(
        output_type=phase_def.output_schema,
        system_prompt=system_prompt,
        user_prompt=f"Process the input for phase: {phase_def.name}",
        model_name=phase_def.model,
        phase_name=phase_def.name,
    )
    return MatchOutcome(
        output=res.output, output_json=res.output_json, input_tokens=res.input_tokens, output_tokens=res.output_tokens
    )


class LlmMatcher:
    def __init__(self, llm: LlmClient | None = None) -> None:
        self.llm = llm or LlmClient.from_settings(settings)

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        return await run_llm_matches(
            phase_def=phase_def, db=db, project_id=project_id, session_id=session_id, llm=self.llm
        )
