"""CLAIM_PARSE harness definition — 7-phase claim parsing pipeline."""

from pathlib import Path

from app.harness.context_loaders import (
    load_format_playbook,
    load_variations_context,
    load_wbs_context,
)
from app.harness.executors.create_records import execute_create_records
from app.harness.executors.detect_format import execute_detect_format
from app.harness.executors.extract_line_items import execute_extract_line_items
from app.harness.executors.raw_extraction import execute_raw_extraction
from app.harness.executors.validate_claim import execute_validate_claim
from app.harness.models import (
    HarnessDefinition,
    HarnessPrerequisites,
    HarnessType,
    PhaseDefinition,
    PhaseType,
)
from app.harness.registry import harness_registry
from app.harness.schemas import VpsMatch, WbsMatch

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


claim_parse_definition = HarnessDefinition(
    harness_type=HarnessType.CLAIM_PARSE,
    display_name="Claim Parse & Assessment",
    description="Parse contractor claim PDF, validate, categorise, and create assessment",
    prerequisites=HarnessPrerequisites(
        intro_text="Upload a contractor claim PDF to parse and assess",
        required_document_count=1,
    ),
    phases=[
        # Phase 0: Raw Extraction
        PhaseDefinition(
            name="Raw Extraction",
            description="Extract raw text and tables from PDF",
            phase_type=PhaseType.PROGRAMMATIC,
            workspace_output="raw_extraction.json",
            executor=execute_raw_extraction,
        ),
        # Phase 1: Format Detection
        PhaseDefinition(
            name="Detect Format",
            description="Identify document format from text markers",
            phase_type=PhaseType.PROGRAMMATIC,
            workspace_output="format_detection.json",
            executor=execute_detect_format,
        ),
        # Phase 2: Extract Line Items (format-routed)
        PhaseDefinition(
            name="Extract Line Items",
            description="Extract structured line items — deterministic for WBPRO, LLM for others",
            phase_type=PhaseType.PROGRAMMATIC,
            workspace_output="parsed_claim.json",
            executor=execute_extract_line_items,
        ),
        # Phase 3: Validate Contractor Math
        PhaseDefinition(
            name="Validate Claim",
            description="Run deterministic validation checks on extracted data",
            phase_type=PhaseType.PROGRAMMATIC,
            workspace_output="validation_summary.json",
            executor=execute_validate_claim,
        ),
        # Phase 4: WBS Categorisation (with WBS context + format playbook)
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
        # Phase 5: Variation & PS Matching
        PhaseDefinition(
            name="Variation Matching",
            description=(
                "Match variations and provisional sums to existing records "
                "(Jev decision model, LLM fallback)"
            ),
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            matcher="jev",
            workspace_output="vps_matches.json",
            workspace_inputs=["parsed_claim.json"],
            system_prompt_template=_load_prompt("match_variations.md"),
            context_loaders=[load_variations_context],
            output_schema=list[VpsMatch],
        ),
        # Phase 6: Create Domain Records
        PhaseDefinition(
            name="Create Records",
            description="Create Claim, Assessment, and all line item records",
            phase_type=PhaseType.PROGRAMMATIC,
            workspace_output="creation_summary.json",
            executor=execute_create_records,
        ),
    ],
)

harness_registry.register(claim_parse_definition)
