---
title: Introduce Jev (TypeSafe System One) as a matcher for WBS & VPS phases
status: ready
created: 2026-10-03
scope: backend/app/harness (CLAIM_PARSE phases 4 & 5)
author: grilled spec (procure)
---

# Introduce Jev as a decision-model matcher for WBS & VPS matching

## Context

The CLAIM_PARSE harness turns a contractor payment-claim PDF into domain records.
Two of its seven phases are LLM calls that do **classification / record-linkage**,
not generation:

- **Phase 4 — WBS Categorisation**: map each contract-work line item to an existing
  WBS subcategory (or propose a new one).
- **Phase 5 — Variation & PS Matching**: link each variation / provisional-sum line
  item to an existing record (or create new).

Both run today as a single pydantic-ai chat completion that returns a whole
`list[WbsMatch]` / `list[VpsMatch]` in one shot. That is slow, pays for output
tokens, and leans on prompt-rubric confidence. Jev (TypeSafe's "System One"
decision model) is built for exactly this shape: unstructured state in, one typed
calibrated decision out, 70–500 ms, pay-per-input-token with **output free**, and
it cannot hallucinate a value outside the provided option set. It is reachable
through **OpenRouter's decisions API**, which this codebase is already wired for.

This spec adds Jev as a selectable **matcher** behind a strategy interface, with
the current LLM path kept as a first-class fallback. It realizes the already-
scaffolded `LLM_BATCH_AGENTS` phase type.

**Why now:** matching is the slowest, priciest part of the pipeline, and the
pydantic-ai migration that makes a clean swap possible is already complete. Jev
over OpenRouter is a strict upgrade (cheaper, faster, hallucination-free core)
with a safe fallback, so there is no reason to keep paying LLM output-token cost
on a bounded classification task.

## Current State (verified 2026-10-03)

| Fact | Location |
|------|----------|
| 7-phase pipeline; phases 4 & 5 are `LLM_SINGLE` | `backend/app/harness/definitions/claim_parse.py:73-93` |
| `PhaseType` enum: `PROGRAMMATIC` + `LLM_SINGLE` implemented; `LLM_AGENT`, `LLM_BATCH_AGENTS`, `LLM_HUMAN_INPUT` scaffolded, unimplemented | `backend/app/harness/models.py:12-17` |
| `PhaseDefinition` already carries `model`, `tools`, `max_rounds`, `batch_items_file`, `batch_size` | `backend/app/harness/models.py:24-44` |
| Engine dispatch: only `PROGRAMMATIC` / `LLM_SINGLE`; anything else raises `ValueError` | `backend/app/harness/engine.py:120-127` |
| `_run_llm_single` builds context, renders prompt, calls `run_structured`, writes bare JSON | `backend/app/harness/engine.py:173-235` |
| pydantic-ai runner + OpenAI-compatible provider routing incl. `openrouter` (`base_url https://openrouter.ai/api/v1`, `settings.open_router_api_key`) | `backend/app/harness/agent_runner.py:29-57,70-100` |
| Output schemas `WbsMatch` / `VpsMatch`, `confidence` required & range-checked | `backend/app/harness/schemas.py:24-46` |
| Settings: `llm_provider`, `llm_model`, `open_router_api_key` (and anthropic/openai/deepseek keys) | `backend/app/config.py:16-24` |
| Downstream consumer of `wbs_matches.json` / `vps_matches.json` | `backend/app/harness/executors/create_records.py` |

**WBS cardinality (bounds the 255-choice cap):** 2-level hierarchy
(category → subcategory); ~30–40 subcategories per project, **max observed 51**
(`scripts/seed_paparoa.py`); ~32–44 line items per claim. All comfortably under
Jev's 255 options/Choice. Caveat: variation records accumulate across a project's
life (Gilmours claims 1→3: 3→6→15 variations), so the VPS choice set can climb —
guard, not a blocker.

**Not changing:** the workspace-file contract. Matchers still write
`wbs_matches.json` (a `list[WbsMatch]`) and `vps_matches.json` (a `list[VpsMatch]`);
`create_records.py` is untouched. `.env` default provider stays as-is; Jev is opt-in
per phase.

## Proposed Change

Introduce a `DecisionMatcher` strategy. Phases 4 & 5 become `LLM_BATCH_AGENTS` and
run through a new dispatcher branch that picks a matcher and writes the identical
workspace JSON.

```
PhaseDefinition(matcher="jev" | "llm", phase_type=LLM_BATCH_AGENTS)
            │
engine._run_decision_match  ──pick──►  DecisionMatcher
            │                              ├── JevMatcher  (default)  ── OpenRouter /decisions
            │                              └── LlmMatcher  (fallback) ── existing run_structured
            ▼
   writes list[WbsMatch] / list[VpsMatch]  ──►  create_records.py  (unchanged)
```

Matcher selection resolves as: `phase_def.matcher` → `settings.matcher_default` →
`"llm"`. If `matcher == "jev"` but Jev is unconfigured or errors, fall back to
`LlmMatcher` (see Resilience).

### Implementation Details

#### 1. `DecisionMatcher` interface — `backend/app/harness/matchers/base.py` (new)

```python
class MatchOutcome(BaseModel):
    output: list[BaseModel]       # list[WbsMatch] or list[VpsMatch]
    output_json: str              # TypeAdapter(output_type).dump_json(...).decode()
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None # OpenRouter usage.cost when present

class DecisionMatcher(Protocol):
    name: str
    async def match(
        self, *, phase_def: PhaseDefinition, db, project_id, session_id,
    ) -> MatchOutcome: ...
```

The interface mirrors the shared decision-model contract (state + typed question →
choice + probabilities + confidence) so Clef / Fastino adapters can slot in later
(see Future Swaps). The matcher owns its own data access — it reads the parsed
claim from the workspace and WBS/variation records from the repos rather than
depending on prompt-string context loaders.

#### 2. `JevMatcher` — `backend/app/harness/matchers/jev.py` (new)

Per-item fan-out, one Jev **Choice** per in-scope line item:

- **In scope per phase:** WBS → `item_type == "contract_work"` items; VPS →
  `variation` / `provisional_sum` items (mirrors the current filtering in
  `create_records.py`).
- **State** (per call): the single line item — `description`, `contract_value`,
  `item_type`, and any ref/section context already on the item. Small, so each
  call is cheap.
- **Criteria** (WBS): every subcategory as `{code: description}` where each
  description embeds its `contract_sum` (e.g. `"Demolition works — contract sum
  $12,345.00"`), so Jev can use the strongest signal (sum match within ~1%)
  directly. Plus an explicit `"__none__": "None of the above subcategories fit
  this line item"` option. Criteria for VPS: existing variation/PS records as
  `{record_id: "desc — $value"}` + `"__none__"`.
- **Call:** `POST https://openrouter.ai/api/alpha/decisions`, `model:
  "typesafe/jev-1.13"` (configurable, alias `~typesafe/jev-latest`),
  `Authorization: Bearer <settings.open_router_api_key>`. One question id per item
  (`"item_{index}"`). Concurrency-capped at `settings.jev_max_concurrency`
  (default 8) via an `asyncio.Semaphore` + `asyncio.gather`; exponential backoff
  with jitter on 429 / 529 (bounded retries, e.g. 4).
- **Assemble:** map each answer back:
  - WBS: `choice == "__none__"` → collect into the "new code" residue (see §4);
    otherwise `wbs_code = choice`, resolve `wbs_code_id` from the code→id map,
    `confidence = answers[id].confidence`, `is_new = False`.
  - VPS: `choice == "__none__"` → `matched_id = None` (existing deterministic
    new-record path in `create_records.py` handles it); otherwise
    `matched_id = choice`, `confidence = answers[id].confidence`.
- **32k context guard:** criteria are sent per call; one item + ~51 options is tiny,
  but assert the serialized request is under the 32k window and fail loudly with a
  clear error if a pathological project ever exceeds it.

#### 3. `LlmMatcher` — `backend/app/harness/matchers/llm.py` (new, wraps existing path)

A thin adapter over the current behavior: builds context from `phase_def`'s
context loaders + workspace inputs exactly as `_run_llm_single` does today, calls
`run_structured(output_type=phase_def.output_schema, ...)`, returns a
`MatchOutcome`. This is the fallback and keeps today's path behaviorally identical.
Refactor the context-building block out of `engine._run_llm_single` into a shared
helper so both the LLM_SINGLE path and `LlmMatcher` call it (no copy-paste).

#### 4. "None fits" → new-code minting (WBS only)

Jev returns a chosen existing option; it cannot invent a code. For the WBS residue
where Jev picked `"__none__"`, make **one** `LlmMatcher`-style call over just those
items to propose new subcategories (`wbs_code`, `wbs_description`, `parent_code`,
`is_new=True`), using the existing `categorise_wbs.md` prompt constrained to the
residue. Cost is bounded to the handful of genuine misses. VPS needs no residue
call — `matched_id=None` already means "create new record."

#### 5. Confidence & low-confidence routing

- Store Jev's calibrated `confidence` directly into `WbsMatch.confidence` /
  `VpsMatch.confidence` (both already `ge=0.0,le=1.0`). No schema change needed.
- Add `settings.jev_confidence_floor` (default `0.6`). WBS items whose Jev
  confidence is below the floor are routed to the `LlmMatcher` for a second opinion
  (reusing the §4 residue call path); the result that is used is recorded. VPS
  sub-floor items are left to the deterministic new-record path and flagged in the
  phase summary. The floor is config, not magic — surfaced in logs so a human can
  tune it from real runs.

#### 6. Engine wiring — `backend/app/harness/engine.py`

- Add a dispatch branch: `elif phase_def.phase_type == PhaseType.LLM_BATCH_AGENTS:
  _run_decision_match(...)`.
- `_run_decision_match` resolves the matcher (`phase_def.matcher` →
  `settings.matcher_default`), instantiates it, `await matcher.match(...)`, writes
  `response.output_json` to `phase_def.workspace_output`, emits `UsageEvent`
  (extend to carry `cost_usd` if present), updates phase status. Same SSE/event
  surface as `_run_llm_single`.

#### 7. Config & phase defs

- `backend/app/harness/models.py`: add `matcher: Literal["llm", "jev"] | None = None`
  to `PhaseDefinition`; add `jev_model: str = "typesafe/jev-1.13"` reference where phase
  overrides are set (or read from settings).
- `backend/app/config.py`: add `matcher_default: str = "llm"`,
  `jev_model: str = "typesafe/jev-1.13"`, `jev_max_concurrency: int = 8`,
  `jev_confidence_floor: float = 0.6`, `jev_decisions_url: str =
  "https://openrouter.ai/api/alpha/decisions"`. **Reuse `open_router_api_key`** —
  no `TYPESAFE_API_KEY` / `JEV_KEY` (the earlier `JEV_KEY` in `.env` is now
  unnecessary; remove it to avoid confusion).
- `backend/app/harness/definitions/claim_parse.py`: set phases 4 & 5
  `phase_type=PhaseType.LLM_BATCH_AGENTS, matcher="jev"`. Keep `output_schema`
  (`list[WbsMatch]` / `list[VpsMatch]`) and `context_loaders` (the `LlmMatcher`
  fallback still needs them).

### Jev / OpenRouter decisions API contract (reference)

Request:
```json
{
  "model": "typesafe/jev-1.13",
  "state": { "description": "...", "contract_value": "12,345.00", "item_type": "contract_work" },
  "questions": {
    "item_7": {
      "type": "choice",
      "instructions": "Which WBS subcategory does this line item belong to? Prefer an exact or near (within ~1%) contract-sum match over description similarity.",
      "criteria": {
        "DM-01": "Demolition works — contract sum $12,345.00",
        "PL-03": "Site preliminaries — contract sum $4,000.00",
        "__none__": "None of the above subcategories fit this line item"
      }
    }
  }
}
```
Response:
```json
{
  "model": "jev-1.13.0",
  "answers": {
    "item_7": { "type": "choice", "choice": "DM-01",
                "probabilities": {"DM-01": 0.97, "PL-03": 0.02, "__none__": 0.01},
                "confidence": 0.95 }
  },
  "usage": { "input_tokens": 312, "output_tokens": 0, "cost": 0.000013 }
}
```
Headers: `Authorization: Bearer <OpenRouter key>`, `Content-Type: application/json`.
Limits: up to 255 options/Choice; 32k context (state + questions). Output tokens
free; `usage.cost` returned in USD.

## Resilience (hard requirement — no silent failures)

The user has a standing rule against swallowed errors; every fallback here **logs
loudly at WARNING/ERROR with the cause**, never silently degrades.

| Situation | Behavior |
|-----------|----------|
| Transient Jev error (429/529/network) | Per-item exponential backoff + jitter, bounded retries |
| Jev error persists after retries, for an item | Log the item + error, fall back **that item** to `LlmMatcher`; mark it in the phase summary |
| Jev unconfigured (no `open_router_api_key`) and `matcher="jev"` | Log once, run the **whole phase** on `LlmMatcher` (identical to today); do not raise |
| 401 (bad key) | Raise loudly — this is a config error, not a transient one |
| Malformed/empty Jev response for an item | Log, fall back that item to `LlmMatcher` |
| Serialized request exceeds 32k | Raise with a clear message naming the phase and item count |

Fallbacks are observable: a run that silently matched nothing must be impossible —
if every item fell back, the logs say so and the phase summary reports
`matcher=jev, fell_back=N/N`.

## Acceptance Criteria

1. A new `DecisionMatcher` interface exists with `JevMatcher` and `LlmMatcher`
   implementations; phases 4 & 5 run through `_run_decision_match` with
   `matcher="jev"` default.
2. With `matcher="jev"`, Phase 4 produces a `wbs_matches.json` that validates as
   `list[WbsMatch]`, exactly one entry per `contract_work` line item, byte-for-byte
   schema-compatible with what `create_records.py` consumes today.
3. Phase 5 with `matcher="jev"` produces a `vps_matches.json` validating as
   `list[VpsMatch]`, one entry per variation/PS item; `matched_id=None` for
   `"__none__"` choices.
4. Each match's `confidence` is Jev's calibrated confidence (0.0–1.0).
5. Items where Jev returns `"__none__"` (WBS) are minted as new subcategories via a
   single residue `LlmMatcher` call with `is_new=True` and a non-empty
   `wbs_code`/`parent_code`.
6. WBS items with `confidence < settings.jev_confidence_floor` are routed to the
   `LlmMatcher` second-opinion path; the decision is logged.
7. With `open_router_api_key` unset and `matcher="jev"`, the phase completes on the
   `LlmMatcher` with a single WARNING log and no raise.
8. Per-item Jev failure after bounded retries falls back that item to `LlmMatcher`,
   logs the cause, and the phase summary reports the fallback count. No error is
   swallowed (verified by `silent-failure-hunter` on the branch diff).
9. Jev calls run concurrently, capped at `settings.jev_max_concurrency`, with
   backoff on 429/529.
10. `matcher="llm"` (or unset default) reproduces today's behavior exactly
    (regression-free).
11. All existing tests pass; new tests below pass.

## Testing Plan

| Layer | What | Count |
|-------|------|-------|
| Unit | `JevMatcher`: line-item → Choice request shape (criteria incl. `__none__`, sums embedded) | +3 |
| Unit | `JevMatcher`: response → `WbsMatch`/`VpsMatch` mapping incl. `__none__`→residue / `matched_id=None` | +3 |
| Unit | Confidence floor routing; code→id resolution; 255/32k guards | +3 |
| Unit | Resilience: 429 retry→success; persistent error→per-item LLM fallback (asserts WARNING logged); unconfigured→whole-phase LLM fallback; 401→raise | +4 |
| Unit | `matcher_default` / `phase_def.matcher` resolution precedence | +1 |
| Integration | `HarnessEngine` LLM_BATCH_AGENTS phase with a **fake decisions endpoint**, asserts `wbs_matches.json` validates as `list[WbsMatch]` (mirror `tests/integration/test_harness_llm_single.py`) | +2 |
| E2E | Re-run existing Gilmours & Paparoa fixtures with `matcher=jev` (fake Jev), assert same item counts / record creation as the LLM path | +2 |

Build a `FakeDecisionsClient` (returns canned `answers` with probabilities +
confidence) as the Jev analogue of pydantic-ai's `TestModel`; no network in tests.

## Rollback Plan

Pure opt-in and reversible: set phases 4 & 5 back to `phase_type=LLM_SINGLE`
(or `matcher="llm"`) and the pipeline runs exactly as before. No data migration,
no schema change, workspace-file contract unchanged. Revert the PR to remove the
`matchers/` package entirely.

## Effort Estimate

- `DecisionMatcher` interface + `LlmMatcher` wrap + engine refactor: ~3h
- `JevMatcher` (decisions client, criteria builder, fan-out, assembly): ~4h
- Residue new-code + confidence-floor routing: ~2h
- Resilience (retry/backoff/fallback/logging): ~2h
- Config + phase wiring: ~1h
- Tests (unit + integration + e2e fixtures): ~4h
- **Total ~16h** (CC-assisted: a fraction of that)

## Files Reference

| File | Change |
|------|--------|
| `backend/app/harness/matchers/base.py` | New: `DecisionMatcher` protocol, `MatchOutcome` |
| `backend/app/harness/matchers/jev.py` | New: `JevMatcher` + OpenRouter decisions client |
| `backend/app/harness/matchers/llm.py` | New: `LlmMatcher` wrapping `run_structured` |
| `backend/app/harness/engine.py:120-127` | Add `LLM_BATCH_AGENTS` dispatch branch |
| `backend/app/harness/engine.py:173-235` | Extract shared context-build helper; add `_run_decision_match` |
| `backend/app/harness/models.py:24-44` | Add `matcher` field to `PhaseDefinition` |
| `backend/app/config.py:16-24` | Add `matcher_default`, `jev_model`, `jev_max_concurrency`, `jev_confidence_floor`, `jev_decisions_url` |
| `backend/app/harness/definitions/claim_parse.py:73-93` | Phases 4 & 5 → `LLM_BATCH_AGENTS`, `matcher="jev"` |
| `.env.example` / `.env` | Document reuse of `OPENROUTER_API_KEY`; remove stray `JEV_KEY` |
| `backend/tests/unit/test_jev_matcher.py` | New unit tests |
| `backend/tests/integration/test_harness_batch_agents.py` | New integration test |
| `backend/tests/e2e/fixtures/` | Re-run under `matcher=jev` |

## Out of Scope

- Generic extraction (Phase 2 generic branch) — it is generative extraction, a poor
  decision-model fit.
- The legacy `backend/app/utils/categoriser.py` and `variation_matcher.py` — dead
  (test-only); not migrated or deleted here.
- Implementing `LLM_AGENT` / `LLM_HUMAN_INPUT` phase types.
- Native `typesafe-sdk` transport (we use OpenRouter). The interface leaves room
  for it later.
- Any change to `create_records.py` or the workspace-file contract.

## Future Swaps (documented, not built)

The `DecisionMatcher` interface is shaped to the common decision-model contract, so
these drop in as new `matchers/*.py` adapters without touching the engine:

- **Cloudflare Clef / Clef-flash** — open-source (Apache-2.0), on Workers AI;
  multimodal, 64k context, claims ~13× faster than Jev. Strong self-host/speed hedge.
- **Fastino TLMs** — zero-shot text classification; flat monthly subscription (no
  per-token). Worth it if claim volume spikes.
- **Laya / Von / NanoJev** — tiny (322M–600M) open decision models for cheap
  self-hosting.

## Risks / Watch

- **Accuracy vs. the demo premise:** Jev owns the contract-sum signal (no
  programmatic pre-pass, by decision). If exact-sum matching regresses vs. the LLM
  rubric, revisit adding a deterministic sum pre-pass that feeds only the residue to
  Jev.
- **Growing VPS choice set:** long projects accumulate variations; monitor against
  the 255 cap and 32k window, add paging/filtering if a project approaches it.
- **Confidence calibration drift:** Jev confidence ≠ the old prompt rubric; tune
  `jev_confidence_floor` from real runs before trusting the high-confidence core.
- **`alpha/decisions` endpoint:** it is an alpha surface; pin `typesafe/jev-1.13`
  rather than the `~jev-latest` alias in production to avoid silent behavior shifts.
