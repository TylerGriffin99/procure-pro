# Jev Matcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Jev (TypeSafe System One decision model, via OpenRouter) as a selectable, per-item matcher for the CLAIM_PARSE WBS (Phase 4) and VPS (Phase 5) phases, behind a strategy interface, with the existing LLM path as a first-class fallback.

**Architecture:** Introduce a `DecisionMatcher` strategy with two implementations — `JevMatcher` (fan-out, one Jev Choice per line item) and `LlmMatcher` (the current single pydantic-ai call). Phases 4 & 5 become `LLM_BATCH_AGENTS`, dispatched through a new `engine._run_decision_match` that writes the identical workspace JSON (`wbs_matches.json` / `vps_matches.json`), so `create_records.py` is untouched. Jev is opt-in per phase; selection resolves `phase_def.matcher → settings.matcher_default → "llm"`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, pydantic + pydantic-ai-slim 2.53.0, httpx, pytest / pytest-asyncio.

**Spec:** `docs/specs/introduce-jev-matcher.md`

## Global Constraints

- Python 3.12 (`StrEnum` in use). pydantic-ai-slim `>=2.0,<3` (locked 2.53.0). No new runtime deps except `httpx` (verify it is already present before adding).
- Jev transport is OpenRouter's decisions API: `POST https://openrouter.ai/api/alpha/decisions`, `Authorization: Bearer <settings.open_router_api_key>`. **Reuse `open_router_api_key`** — no `TYPESAFE_API_KEY` / `JEV_KEY`.
- Pin the model id `typesafe/jev-1.13` in config; do not default to the `~jev-latest` alias.
- A Choice carries ≤255 options; request (state + questions) must fit a 32k context.
- **No silent failures.** Every fallback or degraded path logs at WARNING/ERROR with the cause and is counted in the phase summary. A run that matched nothing must be impossible to produce silently. (A `silent-failure-hunter` pass on the branch diff is part of done.)
- The workspace-file contract is unchanged: matchers write a bare JSON `list[WbsMatch]` / `list[VpsMatch]`. `create_records.py` is not modified.
- Matcher is opt-in: default `settings.matcher_default = "llm"`; `matcher="llm"` reproduces today's behavior exactly.

## Review Focus

- **Empty in-scope item set** (claim with zero contract-work, or zero variation/PS items): the phase must write `[]` and complete, never crash or skip the write. → test in Task 7 (WBS) and Task 9 (VPS).
- **Jev returns a `choice` string not in the sent criteria** (protocol drift): treat as "none"/residue, log it, never write an unresolvable `wbs_code`. → test in Task 7.
- **Duplicate WBS `code` across categories** used as a criteria key: code→id resolution must not silently pick the wrong subcategory; detect the collision and key by id. → test in Task 7.
- **Null / zero / malformed `contract_value`** (e.g. `"(500.00)"`, `None`): state serialization must stay valid JSON and the item must still be matched, not dropped. → test in Task 7.
- **All items fall back** because Jev is fully down: the phase completes on the LLM path and the summary reports `fell_back=N/N`; output is never a silent empty list. → test in Task 10.

---

### Task 1: `DecisionMatcher` interface + `MatchOutcome` + factory

**Files:**
- Create: `backend/app/harness/matchers/__init__.py`
- Create: `backend/app/harness/matchers/base.py`
- Test: `backend/tests/unit/test_matcher_base.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `MatchOutcome` dataclass; `DecisionMatcher` protocol with `name: str` and `async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome`; `get_matcher(name: str) -> DecisionMatcher`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_matcher_base.py
import pytest
from app.harness.matchers.base import MatchOutcome, get_matcher


def test_match_outcome_defaults():
    out = MatchOutcome(output=[], output_json="[]")
    assert out.input_tokens == 0
    assert out.output_tokens == 0
    assert out.cost_usd is None


def test_get_matcher_unknown_raises():
    with pytest.raises(ValueError, match="Unknown matcher"):
        get_matcher("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_matcher_base.py -v`
Expected: FAIL — `ModuleNotFoundError: app.harness.matchers.base`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/harness/matchers/__init__.py
```

```python
# backend/app/harness/matchers/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class MatchOutcome:
    """Result of a matcher run: the typed list + its serialized form + usage."""

    output: list[Any]          # list[WbsMatch] or list[VpsMatch]
    output_json: str           # bare JSON array matching the phase output_schema
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


@runtime_checkable
class DecisionMatcher(Protocol):
    name: str

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        ...


def get_matcher(name: str) -> DecisionMatcher:
    """Resolve a matcher by name. Imports are local to avoid import cycles."""
    if name == "llm":
        from app.harness.matchers.llm import LlmMatcher
        return LlmMatcher()
    if name == "jev":
        from app.harness.matchers.jev import JevMatcher
        return JevMatcher()
    raise ValueError(f"Unknown matcher: {name!r}. Use 'llm' or 'jev'.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_matcher_base.py::test_match_outcome_defaults -v`
Expected: PASS. (`test_get_matcher_unknown_raises` also passes; the `llm`/`jev` branches import lazily and are added in Tasks 3 and 7.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/ backend/tests/unit/test_matcher_base.py
git commit -m "feat(harness): add DecisionMatcher interface and MatchOutcome"
```

---

### Task 2: Extract shared phase-context builder

Pure refactor: lift the context-building block out of `engine._run_llm_single` so both the LLM_SINGLE path and `LlmMatcher` share one implementation (DRY). Behavior unchanged.

**Files:**
- Create: `backend/app/harness/phase_context.py`
- Modify: `backend/app/harness/engine.py:187-201`
- Test: `backend/tests/unit/test_phase_context.py`

**Interfaces:**
- Consumes: `harness_repo.read_workspace_file`, `phase_def.workspace_inputs`, `phase_def.context_loaders`.
- Produces: `async def build_phase_context(db, session_id, project_id, phase_def) -> dict[str, str]`; `def render_system_prompt(phase_def, context) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_phase_context.py
import pytest
from app.harness.phase_context import build_phase_context, render_system_prompt


class _FakePhase:
    workspace_inputs = ["parsed_claim.json"]
    context_loaders = []
    system_prompt_template = "Items: $workspace_parsed_claim / $extra"


@pytest.mark.asyncio
async def test_build_phase_context_reads_workspace(monkeypatch):
    async def fake_read(db, sid, path):
        return '{"line_items": []}'
    monkeypatch.setattr("app.harness.phase_context.harness_repo.read_workspace_file", fake_read)
    phase = _FakePhase()

    async def loader(db, project_id, session_id):
        return {"extra": "X"}
    phase.context_loaders = [loader]

    ctx = await build_phase_context(db=None, session_id="s", project_id="p", phase_def=phase)
    assert ctx["workspace_parsed_claim"] == '{"line_items": []}'
    assert ctx["extra"] == "X"
    assert render_system_prompt(phase, ctx) == 'Items: {"line_items": []} / X'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_phase_context.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/harness/phase_context.py
from __future__ import annotations

from string import Template

from app.harness import repo as harness_repo  # match the import path used in engine.py


async def build_phase_context(*, db, session_id, project_id, phase_def) -> dict[str, str]:
    context: dict[str, str] = {}
    for path in phase_def.workspace_inputs:
        content = await harness_repo.read_workspace_file(db, session_id, path)
        var_name = path.replace(".json", "").replace("-", "_").replace("/", "_")
        context[f"workspace_{var_name}"] = content or "FILE NOT FOUND"
    for loader in phase_def.context_loaders:
        extra = await loader(db, project_id, session_id)
        context.update(extra)
    return context


def render_system_prompt(phase_def, context: dict[str, str]) -> str:
    return Template(phase_def.system_prompt_template).safe_substitute(**context)
```

> NOTE: confirm the exact import alias for the harness repo as used at the top of
> `engine.py` (it references `harness_repo`). Mirror that import here so monkeypatch
> targets line up.

Then replace `engine.py:187-201` so `_run_llm_single` calls the helper:

```python
# in engine._run_llm_single, replacing the inline context block
from app.harness.phase_context import build_phase_context, render_system_prompt
context = await build_phase_context(
    db=self.db, session_id=self.session_id, project_id=self.project_id, phase_def=phase_def,
)
system_prompt = render_system_prompt(phase_def, context)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_phase_context.py tests/integration/test_harness_llm_single.py -v`
Expected: PASS (new unit test green; the existing LLM_SINGLE integration test still green — refactor preserved behavior).

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/phase_context.py backend/app/harness/engine.py backend/tests/unit/test_phase_context.py
git commit -m "refactor(harness): extract build_phase_context/render_system_prompt from engine"
```

---

### Task 3: `LlmMatcher` wrapping the existing structured call

**Files:**
- Create: `backend/app/harness/matchers/llm.py`
- Test: `backend/tests/unit/test_llm_matcher.py`

**Interfaces:**
- Consumes: `build_phase_context`, `render_system_prompt` (Task 2); `agent_runner.build_model`, `agent_runner.run_structured`; `MatchOutcome` (Task 1).
- Produces: `class LlmMatcher` with `name = "llm"` and the `DecisionMatcher.match` signature; `async def run_llm_matches(*, phase_def, db, project_id, session_id) -> MatchOutcome` (reused by `JevMatcher` for residue/fallback).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_llm_matcher.py
import pytest
from pydantic_ai.models.test import TestModel
from app.harness.matchers.llm import LlmMatcher
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    workspace_inputs = []
    context_loaders = []
    system_prompt_template = "match"
    model = None
    output_schema = list[WbsMatch]


@pytest.mark.asyncio
async def test_llm_matcher_returns_match_outcome(monkeypatch):
    # Force run_structured to use a pydantic-ai TestModel (no network).
    from app.harness import agent_runner
    sample = [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]

    async def fake_run_structured(*, output_type, system_prompt, user_prompt, model=None, phase_name=None):
        from app.harness.agent_runner import StructuredResult
        from pydantic import TypeAdapter
        return StructuredResult(
            output=sample,
            output_json=TypeAdapter(output_type).dump_json(sample).decode(),
            input_tokens=10, output_tokens=5,
        )
    monkeypatch.setattr("app.harness.matchers.llm.run_structured", fake_run_structured)

    out = await LlmMatcher().match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert out.output == sample
    assert out.input_tokens == 10
    assert out.output_json.startswith("[")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_llm_matcher.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/harness/matchers/llm.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_llm_matcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/llm.py backend/tests/unit/test_llm_matcher.py
git commit -m "feat(harness): add LlmMatcher wrapping run_structured"
```

---

### Task 4: Config + `matcher` field + engine `LLM_BATCH_AGENTS` dispatch

**Files:**
- Modify: `backend/app/config.py:16-24`
- Modify: `backend/app/harness/models.py:24-44`
- Modify: `backend/app/harness/engine.py:120-127` (dispatch) and add `_run_decision_match`
- Test: `backend/tests/integration/test_harness_batch_agents.py`

**Interfaces:**
- Consumes: `get_matcher` (Task 1), `MatchOutcome`.
- Produces: `PhaseDefinition.matcher: Literal["llm","jev"] | None`; settings `matcher_default`, `jev_model`, `jev_max_concurrency`, `jev_confidence_floor`, `jev_decisions_url`; `engine._run_decision_match` that writes the workspace file and emits `UsageEvent` + `HarnessPhaseResultEvent`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_harness_batch_agents.py
import pytest
from app.harness.models import PhaseType


@pytest.mark.asyncio
async def test_batch_agents_phase_writes_workspace_via_llm_matcher(harness_engine_factory, monkeypatch):
    """A LLM_BATCH_AGENTS phase with matcher='llm' writes wbs_matches.json like today."""
    from app.harness.schemas import WbsMatch
    from app.harness.matchers.base import MatchOutcome
    from pydantic import TypeAdapter

    sample = [WbsMatch(item_index=0, wbs_code="DM-01", confidence=0.9)]

    async def fake_match(self, *, phase_def, db, project_id, session_id):
        return MatchOutcome(output=sample,
                            output_json=TypeAdapter(list[WbsMatch]).dump_json(sample).decode())
    monkeypatch.setattr("app.harness.matchers.llm.LlmMatcher.match", fake_match)

    engine, written = harness_engine_factory(phase_type=PhaseType.LLM_BATCH_AGENTS, matcher="llm")
    await engine.run_single_phase_for_test()  # helper drives one phase; see fixture
    assert written["wbs_matches.json"].startswith("[")
    assert '"wbs_code":"DM-01"' in written["wbs_matches.json"].replace(" ", "")
```

> NOTE: `harness_engine_factory` is a new fixture in `backend/tests/integration/conftest.py`
> that builds a `HarnessEngine` with a single in-memory phase and captures workspace writes
> into the `written` dict. Mirror the setup already used by
> `tests/integration/test_harness_llm_single.py`; reuse its fakes for `harness_repo`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/test_harness_batch_agents.py -v`
Expected: FAIL — `_run_decision_match` not dispatched / `matcher` field missing.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/config.py`, add to `Settings` (after the API keys):

```python
    # Matcher selection + Jev (via OpenRouter decisions API)
    matcher_default: str = "llm"
    jev_model: str = "typesafe/jev-1.13"
    jev_decisions_url: str = "https://openrouter.ai/api/alpha/decisions"
    jev_max_concurrency: int = 8
    jev_confidence_floor: float = 0.6
```

In `backend/app/harness/models.py`, add to `PhaseDefinition` (near `model`):

```python
    matcher: Literal["llm", "jev"] | None = None
```

In `backend/app/harness/engine.py`, extend the dispatcher:

```python
        elif phase_def.phase_type == PhaseType.LLM_BATCH_AGENTS:
            async for event in self._run_decision_match(phase_index, phase_def, session_config):
                yield event
```

And add the method (mirrors `_run_llm_single`’s event/write/commit shape):

```python
    async def _run_decision_match(self, phase_index, phase_def, session_config):
        from app.config import settings
        from app.harness.matchers.base import get_matcher

        if phase_def.output_schema is None:
            raise ValueError(
                f"LLM_BATCH_AGENTS phase '{phase_def.name}' has no output_schema."
            )

        name = phase_def.matcher or settings.matcher_default or "llm"
        # Unconfigured Jev -> run the whole phase on the LLM path (logged, not silent).
        if name == "jev" and not settings.open_router_api_key:
            logger.warning(
                "Phase '%s' requested matcher=jev but open_router_api_key is unset; "
                "falling back to matcher=llm for the whole phase.", phase_def.name,
            )
            name = "llm"

        matcher = get_matcher(name)
        outcome = await matcher.match(
            phase_def=phase_def, db=self.db, project_id=self.project_id, session_id=self.session_id,
        )

        yield UsageEvent(prompt_tokens=outcome.input_tokens, completion_tokens=outcome.output_tokens)

        await harness_repo.write_workspace_file(
            self.db, self.session_id, phase_def.workspace_output, outcome.output_json,
            internal=phase_def.internal,
        )
        await harness_repo.update_phase(
            self.db, self.session_id, str(phase_index),
            {"status": "completed", "summary": f"Produced {phase_def.workspace_output} (matcher={name})"},
            phase_index + 1,
        )
        await self.db.commit()
        yield HarnessPhaseResultEvent(
            phase_index=phase_index, phase_name=phase_def.name, status=PhaseStatus.COMPLETED,
            detail=f"matcher={name}",
        )
```

> Ensure `logger` exists at module scope in `engine.py` (`logger = logging.getLogger(__name__)`); add it if absent.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integration/test_harness_batch_agents.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/harness/models.py backend/app/harness/engine.py backend/tests/integration/test_harness_batch_agents.py backend/tests/integration/conftest.py
git commit -m "feat(harness): LLM_BATCH_AGENTS dispatch + matcher selection + jev settings"
```

---

### Task 5: Structured context providers for WBS subcategories and VPS records

`JevMatcher` needs typed records (not prompt strings). Add providers that read the repos the existing context loaders use.

**Files:**
- Create: `backend/app/harness/matchers/data.py`
- Test: `backend/tests/unit/test_matcher_data.py`

**Interfaces:**
- Consumes: `wbs_code_repo.get_by_project` (and the queries inside `context_loaders.load_variations_context`).
- Produces: `@dataclass Subcat(id,str; code,str; description,str; parent_code,str; contract_sum,float|None)`; `@dataclass VpsRecord(id,str; description,str; value,float|None; item_type: Literal["variation","provisional_sum"])`; `async def wbs_subcategories(db, project_id) -> list[Subcat]`; `async def vps_records(db, project_id) -> list[VpsRecord]`.

> Before writing, Read `backend/app/harness/context_loaders.py` (`load_wbs_context`,
> `load_variations_context`) and `backend/app/repos/wbs_code_repo.py` to mirror the exact
> queries and field names. `wbs_subcategories` returns only rows with `level == "subcategory"`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_matcher_data.py
import pytest
from app.harness.matchers.data import wbs_subcategories, Subcat


@pytest.mark.asyncio
async def test_wbs_subcategories_filters_and_shapes(monkeypatch):
    class _Row:
        def __init__(self, id, code, level, desc, parent_code, cs):
            self.id, self.code, self.level, self.description = id, code, level, desc
            self.parent_code, self.contract_sum = parent_code, cs

    rows = [
        _Row("u1", "DM", "category", "Demolition", None, None),
        _Row("u2", "DM-01", "subcategory", "Soft strip", "DM", 12345.0),
    ]

    async def fake_get(db, project_id):
        return rows
    monkeypatch.setattr("app.harness.matchers.data.wbs_code_repo.get_by_project", fake_get)

    subs = await wbs_subcategories(db=None, project_id="p")
    assert subs == [Subcat(id="u2", code="DM-01", description="Soft strip",
                           parent_code="DM", contract_sum=12345.0)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_matcher_data.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/harness/matchers/data.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.repos import wbs_code_repo


@dataclass(eq=True)
class Subcat:
    id: str
    code: str
    description: str
    parent_code: str
    contract_sum: float | None


@dataclass(eq=True)
class VpsRecord:
    id: str
    description: str
    value: float | None
    item_type: Literal["variation", "provisional_sum"]


async def wbs_subcategories(*, db, project_id) -> list[Subcat]:
    rows = await wbs_code_repo.get_by_project(db, project_id)
    out: list[Subcat] = []
    for r in rows:
        if str(getattr(r, "level", "")) != "subcategory":
            continue
        cs = getattr(r, "contract_sum", None)
        out.append(Subcat(
            id=str(r.id), code=r.code, description=r.description or "",
            parent_code=getattr(r, "parent_code", "") or "",
            contract_sum=float(cs) if cs is not None else None,
        ))
    return out


async def vps_records(*, db, project_id) -> list[VpsRecord]:
    # Mirror the queries in context_loaders.load_variations_context.
    # Returns existing variations + provisional sums as typed records.
    ...  # implement against the same repos load_variations_context uses
```

> The `vps_records` body is filled against the real variation / provisional-sum repos —
> Read `context_loaders.load_variations_context` first and reuse its data access. Its unit
> test is added in Task 9 alongside VPS matching.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_matcher_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/data.py backend/tests/unit/test_matcher_data.py
git commit -m "feat(harness): typed WBS subcategory provider for matchers"
```

---

### Task 6: Jev decisions client + fake for tests

**Files:**
- Create: `backend/app/harness/matchers/jev_client.py`
- Modify: `backend/pyproject.toml` (ensure `httpx` dependency)
- Test: `backend/tests/unit/test_jev_client.py`

**Interfaces:**
- Consumes: `httpx`, `settings`.
- Produces: `async def call_decisions(*, state, questions, model, url, api_key, timeout=30.0) -> dict` returning the parsed JSON (`{"answers": {...}, "usage": {...}}`); raises `httpx.HTTPStatusError` on non-2xx.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_jev_client.py
import httpx
import pytest
from app.harness.matchers.jev_client import call_decisions


@pytest.mark.asyncio
async def test_call_decisions_posts_and_parses(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"answers": {"item_0": {"choice": "DM-01", "confidence": 0.9,
                                                                 "probabilities": {"DM-01": 0.9}}},
                                         "usage": {"input_tokens": 100, "output_tokens": 0, "cost": 0.0001}})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr("app.harness.matchers.jev_client._transport", transport)

    data = await call_decisions(
        state={"description": "demo"}, questions={"item_0": {"type": "choice", "instructions": "?",
                                                             "criteria": {"DM-01": "x"}}},
        model="typesafe/jev-1.13", url="https://openrouter.ai/api/alpha/decisions", api_key="k",
    )
    assert data["answers"]["item_0"]["choice"] == "DM-01"
    assert captured["auth"] == "Bearer k"
    assert captured["body"]["model"] == "typesafe/jev-1.13"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_jev_client.py -v`
Expected: FAIL — module missing. (If `httpx` is absent: `uv add httpx` first and commit the lockfile change in this task.)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/harness/matchers/jev_client.py
from __future__ import annotations

from typing import Any

import httpx

# Overridable in tests via monkeypatch (httpx.MockTransport).
_transport: httpx.BaseTransport | None = None


async def call_decisions(*, state, questions, model, url, api_key, timeout: float = 30.0) -> dict[str, Any]:
    """POST one decisions request. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=timeout, transport=_transport) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "state": state, "questions": questions},
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_jev_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/jev_client.py backend/pyproject.toml backend/uv.lock backend/tests/unit/test_jev_client.py
git commit -m "feat(harness): OpenRouter Jev decisions client"
```

---

### Task 7: `JevMatcher` — WBS happy path (criteria, fan-out, assembly)

WBS only, no residue/floor/resilience yet. Builds one Choice per contract-work item, fans out concurrently, assembles `list[WbsMatch]`.

**Files:**
- Create: `backend/app/harness/matchers/jev.py`
- Test: `backend/tests/unit/test_jev_matcher_wbs.py`

**Interfaces:**
- Consumes: `call_decisions` (Task 6, injectable as `decide_fn`), `wbs_subcategories` (Task 5), `harness_repo.read_workspace_file`, `WbsMatch`, `MatchOutcome`, `settings`.
- Produces: `class JevMatcher` with `name="jev"`, `__init__(self, decide_fn=None)`, and `match(...)`. Helpers: `build_wbs_criteria(subcats) -> tuple[dict[str,str], dict[str,str]]` (criteria, code→id map), `NONE_OPTION = "__none__"`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_jev_matcher_wbs.py
import json
import pytest
from app.harness.matchers.jev import JevMatcher, NONE_OPTION
from app.harness.matchers.data import Subcat
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    output_schema = list[WbsMatch]


SUBCATS = [
    Subcat(id="u1", code="DM-01", description="Soft strip", parent_code="DM", contract_sum=12345.0),
    Subcat(id="u2", code="PL-03", description="Preliminaries", parent_code="PL", contract_sum=4000.0),
]
PARSED = {"line_items": [
    {"item_index": 0, "description": "Demolition", "contract_value": "12,345.00", "item_type": "contract_work"},
    {"item_index": 1, "description": "overhead", "contract_value": None, "item_type": "contract_work"},
    {"item_index": 2, "description": "a variation", "contract_value": "900", "item_type": "variation"},
]}


def _matcher(monkeypatch, answers):
    async def fake_read(db, sid, path):
        return json.dumps(PARSED)
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file", fake_read)

    async def fake_subs(*, db, project_id):
        return SUBCATS
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories", fake_subs)

    async def fake_decide(*, state, questions, model, url, api_key, timeout=30.0):
        qid = next(iter(questions))            # one question per call
        return {"answers": {qid: answers[qid]}, "usage": {"input_tokens": 5, "output_tokens": 0, "cost": 0.0}}
    return JevMatcher(decide_fn=fake_decide)


@pytest.mark.asyncio
async def test_wbs_happy_path_maps_choice_to_code_and_id(monkeypatch):
    answers = {
        "item_0": {"choice": "DM-01", "confidence": 0.95, "probabilities": {"DM-01": 0.95}},
        "item_1": {"choice": "PL-03", "confidence": 0.8, "probabilities": {"PL-03": 0.8}},
    }
    out = await _matcher(monkeypatch, answers).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    by_index = {m.item_index: m for m in out.output}
    assert set(by_index) == {0, 1}                       # only contract_work items (index 2 excluded)
    assert by_index[0].wbs_code == "DM-01" and by_index[0].wbs_code_id == "u1"
    assert by_index[0].confidence == 0.95 and by_index[0].is_new is False
    assert by_index[1].wbs_code_id == "u2"               # null contract_value still matched


@pytest.mark.asyncio
async def test_wbs_empty_item_set_writes_empty_list(monkeypatch):
    m = _matcher(monkeypatch, {})
    async def only_variation(db, sid, path):
        return json.dumps({"line_items": [PARSED["line_items"][2]]})
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file", only_variation)
    out = await m.match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    assert out.output == [] and out.output_json == "[]"


@pytest.mark.asyncio
async def test_wbs_unknown_choice_becomes_residue_none(monkeypatch):
    # Jev returns a code not in criteria -> treated as none (is_new, no bogus wbs_code_id).
    answers = {"item_0": {"choice": "ZZ-99", "confidence": 0.5, "probabilities": {}},
               "item_1": {"choice": NONE_OPTION, "confidence": 0.5, "probabilities": {}}}
    out = await _matcher(monkeypatch, answers).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    for m in out.output:
        assert m.wbs_code_id is None and m.is_new is True   # residue placeholder until Task 8 mints real codes
```

> Collision guard test: add `test_wbs_duplicate_code_keys_by_id` — two subcats sharing `code="DM-01"`
> with different ids; assert `build_wbs_criteria` keys the colliding options by id and resolution
> returns the correct id, not the first-seen one.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_wbs.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/harness/matchers/jev.py
from __future__ import annotations

import asyncio
import json

from pydantic import TypeAdapter

from app.config import settings
from app.harness import repo as harness_repo
from app.harness.matchers.base import MatchOutcome
from app.harness.matchers.data import Subcat, wbs_subcategories
from app.harness.matchers.jev_client import call_decisions
from app.harness.schemas import WbsMatch

NONE_OPTION = "__none__"
_WBS_INSTRUCTIONS = (
    "Which WBS subcategory does this line item belong to? Prefer an exact or near "
    "(within ~1%) contract-sum match over description similarity. Choose "
    f"'{NONE_OPTION}' only if no subcategory fits."
)


def build_wbs_criteria(subcats: list[Subcat]) -> tuple[dict[str, str], dict[str, str]]:
    """Return (criteria, option_key -> subcat_id). Keys by code, or by id on code collision."""
    counts: dict[str, int] = {}
    for s in subcats:
        counts[s.code] = counts.get(s.code, 0) + 1
    criteria: dict[str, str] = {}
    key_to_id: dict[str, str] = {}
    for s in subcats:
        key = s.code if counts[s.code] == 1 else f"{s.code}#{s.id}"
        sum_txt = f" — contract sum ${s.contract_sum:,.2f}" if s.contract_sum is not None else ""
        criteria[key] = f"{s.description}{sum_txt}".strip(" —")
        key_to_id[key] = s.id
    criteria[NONE_OPTION] = "None of the above subcategories fit this line item"
    return criteria, key_to_id


class JevMatcher:
    name = "jev"

    def __init__(self, decide_fn=None):
        self._decide = decide_fn or call_decisions

    async def _read_items(self, db, session_id) -> list[dict]:
        raw = await harness_repo.read_workspace_file(db, session_id, "parsed_claim.json")
        return json.loads(raw or "{}").get("line_items", [])

    async def _choose(self, qid, state, criteria):
        data = await self._decide(
            state=state,
            questions={qid: {"type": "choice", "instructions": _WBS_INSTRUCTIONS, "criteria": criteria}},
            model=settings.jev_model, url=settings.jev_decisions_url, api_key=settings.open_router_api_key,
        )
        ans = data["answers"][qid]
        usage = data.get("usage", {})
        return ans, usage

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        items = [i for i in await self._read_items(db, session_id) if i.get("item_type") == "contract_work"]
        subcats = await wbs_subcategories(db=db, project_id=project_id)
        criteria, key_to_id = build_wbs_criteria(subcats)
        code_for_key = {k: (k.split("#")[0]) for k in key_to_id}

        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, WbsMatch] = {}
        in_tok = 0

        async def run(item):
            nonlocal in_tok
            idx = item["item_index"]
            qid = f"item_{idx}"
            state = {"description": item.get("description", ""),
                     "contract_value": item.get("contract_value"),
                     "item_type": item.get("item_type")}
            async with sem:
                ans, usage = await self._choose(qid, state, criteria)
            in_tok += int(usage.get("input_tokens", 0))
            choice = ans.get("choice")
            conf = float(ans.get("confidence", 0.0))
            if choice == NONE_OPTION or choice not in key_to_id:
                # Residue: no existing code chosen. Placeholder; Task 8 mints the real code.
                results[idx] = WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=conf)
            else:
                results[idx] = WbsMatch(item_index=idx, wbs_code=code_for_key[choice],
                                        wbs_code_id=key_to_id[choice], is_new=False, confidence=conf)

        await asyncio.gather(*(run(i) for i in items))
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(
            output=output,
            output_json=TypeAdapter(list[WbsMatch]).dump_json(output).decode(),
            input_tokens=in_tok, output_tokens=0,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_wbs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/jev.py backend/tests/unit/test_jev_matcher_wbs.py
git commit -m "feat(harness): JevMatcher WBS fan-out happy path"
```

---

### Task 8: `__none__` residue minting + low-confidence routing (WBS)

Items where Jev chose `__none__`/unknown, **or** where `confidence < settings.jev_confidence_floor`, are collected and resolved by one `run_llm_matches` call; the LLM result replaces the placeholder for those indices only.

**Files:**
- Modify: `backend/app/harness/matchers/jev.py`
- Test: `backend/tests/unit/test_jev_matcher_residue.py`

**Interfaces:**
- Consumes: `run_llm_matches` (Task 3).
- Produces: `JevMatcher._resolve_residue(residue_indices, phase_def, db, project_id, session_id) -> dict[int, WbsMatch]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_jev_matcher_residue.py
import json
import pytest
from app.harness.matchers.jev import JevMatcher, NONE_OPTION
from app.harness.matchers.data import Subcat
from app.harness.matchers.base import MatchOutcome
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    output_schema = list[WbsMatch]


@pytest.mark.asyncio
async def test_none_and_lowconf_items_routed_to_llm(monkeypatch):
    parsed = {"line_items": [
        {"item_index": 0, "description": "x", "contract_value": "1", "item_type": "contract_work"},
        {"item_index": 1, "description": "y", "contract_value": "2", "item_type": "contract_work"},
    ]}
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file",
                        lambda db, sid, path: _async(json.dumps(parsed)))
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories",
                        lambda **k: _async([Subcat("u1", "DM-01", "d", "DM", 1.0)]))

    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        # item_0 -> none; item_1 -> low confidence
        ans = {"item_0": {"choice": NONE_OPTION, "confidence": 0.9, "probabilities": {}},
               "item_1": {"choice": "DM-01", "confidence": 0.2, "probabilities": {"DM-01": 0.2}}}[qid]
        return {"answers": {qid: ans}, "usage": {}}

    llm_result = [WbsMatch(item_index=0, wbs_code="NEW-01", wbs_description="minted", parent_code="DM",
                           is_new=True, confidence=0.7),
                  WbsMatch(item_index=1, wbs_code="DM-01", wbs_code_id="u1", confidence=0.85)]

    async def fake_llm(*, phase_def, db, project_id, session_id):
        from pydantic import TypeAdapter
        return MatchOutcome(output=llm_result,
                            output_json=TypeAdapter(list[WbsMatch]).dump_json(llm_result).decode())
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", fake_llm)

    import app.config
    monkeypatch.setattr(app.config.settings, "jev_confidence_floor", 0.6, raising=False)

    out = await JevMatcher(decide_fn=fake_decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    by_index = {m.item_index: m for m in out.output}
    assert by_index[0].wbs_code == "NEW-01" and by_index[0].is_new is True   # minted
    assert by_index[1].wbs_code_id == "u1" and by_index[1].confidence == 0.85  # LLM second opinion used


def _async(v):
    async def _a(*a, **k):
        return v
    return _a()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_residue.py -v`
Expected: FAIL — residue not resolved; placeholders returned.

- [ ] **Step 3: Write minimal implementation**

In `jev.py`, import `run_llm_matches` and add residue handling. After the `gather`, before building `output`:

```python
from app.harness.matchers.llm import run_llm_matches  # top of file
```

```python
        # Residue = Jev picked none/unknown OR confidence below the floor.
        floor = settings.jev_confidence_floor
        residue = {idx for idx, m in results.items()
                   if m.is_new or m.wbs_code_id is None or m.confidence < floor}
        if residue:
            logger.info("JevMatcher routing %d/%d WBS item(s) to LLM (none/low-confidence): %s",
                        len(residue), len(results), sorted(residue))
            resolved = await self._resolve_residue(residue, phase_def, db, project_id, session_id)
            results.update(resolved)
```

```python
    async def _resolve_residue(self, residue, phase_def, db, project_id, session_id):
        outcome = await run_llm_matches(
            phase_def=phase_def, db=db, project_id=project_id, session_id=session_id,
        )
        return {m.item_index: m for m in outcome.output if m.item_index in residue}
```

Add `import logging` + `logger = logging.getLogger(__name__)` at the top of `jev.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_residue.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/jev.py backend/tests/unit/test_jev_matcher_residue.py
git commit -m "feat(harness): WBS residue minting + low-confidence LLM routing"
```

---

### Task 9: `JevMatcher` — VPS support

Variation / provisional-sum matching: Choice over existing records keyed by id, `__none__` → `matched_id=None`. Also fills `vps_records` from Task 5.

**Files:**
- Modify: `backend/app/harness/matchers/jev.py`, `backend/app/harness/matchers/data.py` (`vps_records` body)
- Test: `backend/tests/unit/test_jev_matcher_vps.py`

**Interfaces:**
- Consumes: `vps_records` (Task 5), `VpsMatch`.
- Produces: `JevMatcher` branches on `phase_def.output_schema` (`list[WbsMatch]` vs `list[VpsMatch]`); `build_vps_criteria(records) -> tuple[dict,dict]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_jev_matcher_vps.py
import json
import pytest
from app.harness.matchers.jev import JevMatcher, NONE_OPTION
from app.harness.matchers.data import VpsRecord
from app.harness.schemas import VpsMatch


class _Phase:
    name = "Variation Matching"
    output_schema = list[VpsMatch]


@pytest.mark.asyncio
async def test_vps_maps_and_none_is_null(monkeypatch):
    parsed = {"line_items": [
        {"item_index": 0, "description": "VO 1", "contract_value": "900", "item_type": "variation"},
        {"item_index": 1, "description": "PS lift", "contract_value": "5000", "item_type": "provisional_sum"},
        {"item_index": 2, "description": "work", "contract_value": "1", "item_type": "contract_work"},
    ]}
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file",
                        lambda db, sid, path: _async(json.dumps(parsed)))
    monkeypatch.setattr("app.harness.matchers.jev.vps_records",
                        lambda **k: _async([VpsRecord("v1", "Variation one", 900.0, "variation")]))

    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        ans = {"item_0": {"choice": "v1", "confidence": 0.9, "probabilities": {"v1": 0.9}},
               "item_1": {"choice": NONE_OPTION, "confidence": 0.5, "probabilities": {}}}[qid]
        return {"answers": {qid: ans}, "usage": {}}

    out = await JevMatcher(decide_fn=fake_decide).match(phase_def=_Phase(), db=None, project_id="p", session_id="s")
    by_index = {m.item_index: m for m in out.output}
    assert set(by_index) == {0, 1}                       # contract_work excluded
    assert by_index[0].matched_id == "v1" and by_index[0].item_type == "variation"
    assert by_index[1].matched_id is None and by_index[1].item_type == "provisional_sum"


def _async(v):
    async def _a(*a, **k):
        return v
    return _a()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_vps.py -v`
Expected: FAIL — `JevMatcher` only handles WBS; `vps_records` unimplemented.

- [ ] **Step 3: Write minimal implementation**

Implement `vps_records` in `data.py` (mirror `load_variations_context`). In `jev.py`, split `match` by schema:

```python
from app.harness.schemas import VpsMatch
from app.harness.matchers.data import vps_records

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        if phase_def.output_schema == list[VpsMatch]:
            return await self._match_vps(phase_def, db, project_id, session_id)
        return await self._match_wbs(phase_def, db, project_id, session_id)  # Task 7/8 body
```

```python
    async def _match_vps(self, phase_def, db, project_id, session_id) -> MatchOutcome:
        kinds = {"variation", "provisional_sum"}
        items = [i for i in await self._read_items(db, session_id) if i.get("item_type") in kinds]
        records = await vps_records(db=db, project_id=project_id)
        criteria = {r.id: f"{r.description} — ${r.value:,.2f}" if r.value is not None else r.description
                    for r in records}
        criteria[NONE_OPTION] = "No existing record matches; create a new one"
        valid_ids = {r.id for r in records}
        sem = asyncio.Semaphore(settings.jev_max_concurrency)
        results: dict[int, VpsMatch] = {}
        in_tok = 0

        async def run(item):
            nonlocal in_tok
            idx = item["item_index"]
            qid = f"item_{idx}"
            state = {"description": item.get("description", ""),
                     "contract_value": item.get("contract_value"), "item_type": item.get("item_type")}
            async with sem:
                data = await self._decide(
                    state=state,
                    questions={qid: {"type": "choice", "instructions":
                        "Which existing record does this item match? Match on description, then value "
                        f"within ~20%. Choose '{NONE_OPTION}' to create a new record.", "criteria": criteria}},
                    model=settings.jev_model, url=settings.jev_decisions_url,
                    api_key=settings.open_router_api_key,
                )
            ans = data["answers"][qid]
            in_tok += int(data.get("usage", {}).get("input_tokens", 0))
            choice = ans.get("choice")
            matched = choice if choice in valid_ids else None
            results[idx] = VpsMatch(item_index=idx, item_type=item["item_type"],
                                    matched_id=matched, confidence=float(ans.get("confidence", 0.0)))

        await asyncio.gather(*(run(i) for i in items))
        output = [results[k] for k in sorted(results)]
        return MatchOutcome(output=output,
                            output_json=TypeAdapter(list[VpsMatch]).dump_json(output).decode(),
                            input_tokens=in_tok, output_tokens=0)
```

Rename the Task 7/8 `match` body to `_match_wbs` (same code).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_vps.py tests/unit/test_jev_matcher_wbs.py tests/unit/test_jev_matcher_residue.py tests/unit/test_matcher_data.py -v`
Expected: PASS (WBS still green after the `_match_wbs` rename).

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/jev.py backend/app/harness/matchers/data.py backend/tests/unit/test_jev_matcher_vps.py
git commit -m "feat(harness): JevMatcher VPS matching + vps_records provider"
```

---

### Task 10: Resilience — retry/backoff, per-item fallback, loud logging, 32k guard

**Files:**
- Modify: `backend/app/harness/matchers/jev.py`
- Test: `backend/tests/unit/test_jev_matcher_resilience.py`

**Interfaces:**
- Consumes: `httpx.HTTPStatusError`, `run_llm_matches`.
- Produces: `JevMatcher._decide_with_retry(...)`; failed items join the residue set (WBS) or default to `matched_id=None` with a logged warning (VPS); a request exceeding 32k raises `ValueError`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_jev_matcher_resilience.py
import json
import httpx
import pytest
from app.harness.matchers.jev import JevMatcher
from app.harness.matchers.data import Subcat
from app.harness.matchers.base import MatchOutcome
from app.harness.schemas import WbsMatch


class _Phase:
    name = "WBS Categorisation"
    output_schema = list[WbsMatch]


@pytest.mark.asyncio
async def test_persistent_jev_error_falls_back_to_llm_and_logs(monkeypatch, caplog):
    parsed = {"line_items": [{"item_index": 0, "description": "x", "contract_value": "1",
                              "item_type": "contract_work"}]}
    monkeypatch.setattr("app.harness.matchers.jev.harness_repo.read_workspace_file",
                        lambda db, sid, path: _async(json.dumps(parsed)))
    monkeypatch.setattr("app.harness.matchers.jev.wbs_subcategories",
                        lambda **k: _async([Subcat("u1", "DM-01", "d", "DM", 1.0)]))

    async def always_529(*, state, questions, **k):
        raise httpx.HTTPStatusError("overloaded", request=httpx.Request("POST", "http://x"),
                                    response=httpx.Response(529))
    fallback = [WbsMatch(item_index=0, wbs_code="DM-01", wbs_code_id="u1", confidence=0.8)]

    async def fake_llm(*, phase_def, db, project_id, session_id):
        from pydantic import TypeAdapter
        return MatchOutcome(output=fallback,
                            output_json=TypeAdapter(list[WbsMatch]).dump_json(fallback).decode())
    monkeypatch.setattr("app.harness.matchers.jev.run_llm_matches", fake_llm)

    with caplog.at_level("WARNING"):
        out = await JevMatcher(decide_fn=always_529).match(phase_def=_Phase(), db=None,
                                                           project_id="p", session_id="s")
    assert out.output[0].wbs_code_id == "u1"                       # item recovered via LLM
    assert any("fell back" in r.message.lower() or "529" in r.message for r in caplog.records)


def _async(v):
    async def _a(*a, **k):
        return v
    return _a()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_resilience.py -v`
Expected: FAIL — no retry/fallback; the `HTTPStatusError` propagates.

- [ ] **Step 3: Write minimal implementation**

Add a retry wrapper and route failed items into the residue set. In `jev.py`:

```python
import asyncio as _asyncio
import random

_RETRYABLE = {429, 529}

    async def _decide_with_retry(self, qid, state, criteria, instructions, max_attempts=4):
        delay = 0.5
        for attempt in range(1, max_attempts + 1):
            try:
                return await self._decide(
                    state=state,
                    questions={qid: {"type": "choice", "instructions": instructions, "criteria": criteria}},
                    model=settings.jev_model, url=settings.jev_decisions_url,
                    api_key=settings.open_router_api_key,
                )
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code == 401:
                    raise  # config error: fail loudly, do not fall back
                if code in _RETRYABLE and attempt < max_attempts:
                    await _asyncio.sleep(delay + random.uniform(0, delay))
                    delay *= 2
                    continue
                logger.warning("Jev decision %s failed after %d attempt(s): HTTP %s",
                               qid, attempt, code)
                raise
```

In `_match_wbs.run(...)`, wrap the call so a terminal failure marks the item as residue instead of raising:

```python
            try:
                async with sem:
                    data = await self._decide_with_retry(qid, state, criteria, _WBS_INSTRUCTIONS)
                ans = data["answers"][qid]
            except Exception as e:                      # terminal Jev failure for this item
                logger.warning("JevMatcher item %s fell back to LLM: %s", idx, e)
                results[idx] = WbsMatch(item_index=idx, wbs_code="", is_new=True, confidence=0.0)
                return
```

(The residue step in Task 8 then resolves these via `run_llm_matches`; a full outage ⇒ every
item is residue ⇒ the phase completes entirely on the LLM path. Add a one-line summary log
after residue resolution: `logger.warning("JevMatcher: %d/%d items fell back", len(residue), len(results))`
when `len(residue) == len(results)`.) Apply the same `try/except` + `_decide_with_retry` in
`_match_vps` (failed VPS item ⇒ `matched_id=None`, logged).

Add the 32k guard in `build_wbs_criteria` callers: before the first call, assert the serialized
`{"state":..., "questions":{qid: {...criteria}}}` length is < 32_000 tokens-proxy (use a chars/4
heuristic) and raise `ValueError(f"Jev request for '{phase_def.name}' exceeds 32k context")` if not.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_jev_matcher_resilience.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/matchers/jev.py backend/tests/unit/test_jev_matcher_resilience.py
git commit -m "feat(harness): Jev retry/backoff + per-item LLM fallback + 32k guard"
```

---

### Task 11: Wire phases 4 & 5 to Jev + integration test

**Files:**
- Modify: `backend/app/harness/definitions/claim_parse.py:73-93`
- Modify: `.env.example` (document `OPENROUTER_API_KEY` reuse; remove stray `JEV_KEY`)
- Test: `backend/tests/integration/test_harness_batch_agents.py` (extend)

**Interfaces:**
- Consumes: everything above.
- Produces: phases 4 & 5 with `phase_type=PhaseType.LLM_BATCH_AGENTS, matcher="jev"`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/integration/test_harness_batch_agents.py
@pytest.mark.asyncio
async def test_phase4_jev_end_to_end_with_fake_decisions(harness_engine_factory, monkeypatch):
    """Phase 4 as LLM_BATCH_AGENTS/jev produces a valid list[WbsMatch] via a fake decisions endpoint."""
    from app.harness.schemas import WbsMatch
    from pydantic import TypeAdapter

    async def fake_decide(*, state, questions, **k):
        qid = next(iter(questions))
        return {"answers": {qid: {"choice": "DM-01", "confidence": 0.95,
                                  "probabilities": {"DM-01": 0.95}}}, "usage": {"input_tokens": 3}}
    monkeypatch.setattr("app.harness.matchers.jev.JevMatcher._decide", lambda self, **k: fake_decide(**k), raising=False)
    # ... stub wbs_subcategories + parsed_claim.json workspace as in unit tests ...

    engine, written = harness_engine_factory(phase_type=PhaseType.LLM_BATCH_AGENTS, matcher="jev")
    await engine.run_single_phase_for_test()
    parsed = TypeAdapter(list[WbsMatch]).validate_json(written["wbs_matches.json"])
    assert all(isinstance(m, WbsMatch) for m in parsed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/test_harness_batch_agents.py -v`
Expected: FAIL until phases are wired and the fixture stubs are in place.

- [ ] **Step 3: Write minimal implementation**

In `claim_parse.py`, change phases 4 and 5:

```python
        # Phase 4
        PhaseDefinition(
            name="WBS Categorisation",
            description="Match line items to WBS subcategories (Jev decision model, LLM fallback)",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            matcher="jev",
            workspace_output="wbs_matches.json",
            workspace_inputs=["parsed_claim.json"],
            system_prompt_template=_load_prompt("categorise_wbs.md"),
            context_loaders=[load_wbs_context, load_format_playbook],
            output_schema=list[WbsMatch],
        ),
        # Phase 5
        PhaseDefinition(
            name="Variation Matching",
            description="Match variations/PS (Jev decision model, LLM fallback)",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            matcher="jev",
            workspace_output="vps_matches.json",
            workspace_inputs=["parsed_claim.json"],
            system_prompt_template=_load_prompt("match_variations.md"),
            context_loaders=[load_variations_context],
            output_schema=list[VpsMatch],
        ),
```

Update `.env.example`: keep `LLM_PROVIDER`/`LLM_MODEL` for the LLM fallback; add a comment that
Jev reuses `OPENROUTER_API_KEY`; delete the stray `JEV_KEY` line.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integration/test_harness_batch_agents.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/harness/definitions/claim_parse.py backend/.env.example backend/tests/integration/test_harness_batch_agents.py
git commit -m "feat(harness): run WBS & VPS phases through JevMatcher by default"
```

---

### Task 12: E2E fixtures under `matcher=jev`

**Files:**
- Modify: `backend/tests/e2e/test_e2e_full_pipeline.py` (or add `test_e2e_jev_pipeline.py`)
- Test: `backend/tests/e2e/fixtures/` (reuse Gilmours/Paparoa)

**Interfaces:**
- Consumes: the full pipeline + a fake decisions endpoint.
- Produces: an e2e run proving `matcher=jev` yields the same item counts / record creation as the LLM path.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/e2e/test_e2e_jev_pipeline.py
import pytest
from tests.e2e.fixtures.gilmours_claim1 import EXPECTED_CLAIM_ITEM_COUNT


@pytest.mark.asyncio
async def test_gilmours_claim1_under_jev(e2e_pipeline, fake_jev_decisions):
    """Full pipeline with matcher=jev produces the same claim item count as the LLM path."""
    result = await e2e_pipeline.run(fixture="gilmours_claim1", matcher="jev")
    assert result.claim_item_count == EXPECTED_CLAIM_ITEM_COUNT
    assert result.wbs_matches_count == result.contract_work_count   # one match per contract-work item
```

> `fake_jev_decisions` is an autouse-able fixture that patches `JevMatcher._decide` to return a
> deterministic Choice per item from the fixture's expected WBS mapping (no network). Build it
> beside the existing e2e fixtures; derive the expected `choice` from the fixture's embedded WBS.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/e2e/test_e2e_jev_pipeline.py -v`
Expected: FAIL until the fixture + pipeline `matcher` override exist.

- [ ] **Step 3: Write minimal implementation**

Add the `fake_jev_decisions` fixture and a `matcher` override hook to the e2e pipeline runner
(pass `matcher="jev"` onto the phase defs for the run). Keep the LLM-path e2e tests unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/e2e -v`
Expected: PASS (existing LLM e2e + the new Jev e2e).

- [ ] **Step 5: Commit + branch review**

```bash
git add backend/tests/e2e/
git commit -m "test(harness): e2e pipeline under matcher=jev (Gilmours/Paparoa)"
```

Then run the branch-finish review gate (user's standing rule): `silent-failure-hunter` on the
branch diff vs `main`, in parallel with `/code-review`. Resolve any CRITICAL silent-failure
findings (swallowed Jev errors, residue that masks a total outage as empty output) before
declaring the feature done.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:

| Spec item | Task(s) |
|-----------|---------|
| `DecisionMatcher` interface + `MatchOutcome` | 1 |
| `LlmMatcher` wrap (fallback == today) | 2, 3 |
| `matcher` field + settings + engine `LLM_BATCH_AGENTS` dispatch | 4 |
| Structured WBS/VPS data providers | 5 |
| Jev OpenRouter decisions client | 6 |
| Per-item fan-out, criteria w/ contract sums, `__none__` | 7, 9 |
| `__none__` → new-code minting (WBS) | 8 |
| Low-confidence floor routing | 8 |
| Confidence stored from Jev | 7, 9 |
| Resilience (retry/backoff/fallback/unconfigured/401/32k), no silent failures | 4 (unconfigured), 10 |
| Concurrency cap | 7, 9, 10 |
| Phases 4 & 5 wired; key reuse; `.env` cleanup | 11 |
| Unit + integration + e2e verification | all + 11, 12 |
| `silent-failure-hunter` on branch diff | 12 |

**2. Placeholder scan** — two deliberate "fill against the real repo" notes remain (`vps_records` body in Task 5, filled in Task 9; the e2e fake fixture in Task 12). Both name the exact file to read and the shape to produce; neither leaves a design decision open. No `TODO`/`handle edge cases`/`similar to Task N` placeholders.

**3. Type consistency** — `MatchOutcome`, `WbsMatch`, `VpsMatch`, `Subcat`, `VpsRecord`, `build_wbs_criteria`, `NONE_OPTION`, `run_llm_matches`, `_decide_with_retry`, `_resolve_residue`, `_match_wbs`/`_match_vps` are named identically wherever referenced across tasks. `JevMatcher.match` branches on `phase_def.output_schema == list[VpsMatch]`.

**4. Review Focus** — all five uncovered inputs are pinned to a task's tests: empty item set (7/9), out-of-criteria choice (7), duplicate-code collision (7), null/malformed `contract_value` (7), total outage → non-empty-or-logged (10).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-03-jev-matcher.md`. Please review the plan. Which execution approach would you prefer?

- **Subagent-driven** — A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** — I implement every task myself in this session, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end.

**For this plan I recommend Subagent-driven, because the 12 tasks form a tight interface chain (`JevMatcher` in Tasks 7–10 leans on exact names and shapes produced in Tasks 1–6) and a swallowed-error mistake in the fallback path is exactly the failure class the user's standing rule says must not ship — per-task review catches an interface or silent-failure drift before it compounds.** Does the plan capture what you want, and which approach should we use?
