from app.constants.enums import FlagSeverity, FlagType
from app.harness.executors.create_records import execute_create_records
from app.harness.executors.extract_generic import validate_and_normalise
from app.harness.executors.extract_wbpro import parse_wbpro
from app.harness.models import HarnessType
from app.harness.schemas import GenericExtraction, ParsedClaim, RawExtraction, RawPage
from app.repos import claim_repo, document_repo, harness_repo
from tests.integration.characterisation_fixtures import seed_project, seed_user

ROW = ["1.1", "Excavation", "12,3O0.00", "50.00", "100.00", "0.00", "100.00", "0.00"]
SEVEN_COLUMN_ROW = ["1.2", "Short row", "100.00", "50.00", "50.00", "0.00", "50.00"]


async def run_pipeline(db_session, parsed: ParsedClaim):
    user = await seed_user(db_session)
    project = await seed_project(db_session, user)
    doc = await document_repo.create_document(db_session, project.id, "c.pdf", "application/pdf", b"%PDF-1.4 x")
    session = await harness_repo.create_session(
        db=db_session, user_id=user.id, project_id=project.id, harness_type=HarnessType.CLAIM_PARSE, document_id=doc.id
    )
    parsed_json = parsed.model_dump_json(exclude_none=True)
    await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", parsed_json)
    await harness_repo.write_workspace_file(db_session, session.id, "wbs_matches.json", "[]")
    await harness_repo.write_workspace_file(db_session, session.id, "vps_matches.json", "[]")
    await db_session.flush()

    result = await execute_create_records(
        db=db_session, session_id=session.id, user_id=user.id, project_id=project.id, config={}, llm=None
    )

    claim = await claim_repo.get_by_id(db_session, result.claim_id)
    return claim, await harness_repo.list_flags_by_claim(db_session, result.claim_id)


async def run_wbpro_pipeline(db_session, rows):
    raw = RawExtraction(pages=[RawPage(page_num=1, text="Claim No. 1\nCONTRACT WORKS", tables=[rows])])
    _, flags = await run_pipeline(db_session, parse_wbpro(raw))
    return flags


def generic_claim(*, item_type: str = "contract_work", metadata: dict[str, str] | None = None) -> ParsedClaim:
    return validate_and_normalise(
        GenericExtraction.model_validate(
            {
                "metadata": metadata if metadata is not None else {"claim_number": "4"},
                "line_items": [{"ref_code": "A1", "item_type": item_type, "contract_value": "10.00"}],
            }
        )
    )


async def test_malformed_wbpro_cell_yields_format_warning_flag_on_claim(db_session):
    flags = await run_wbpro_pipeline(db_session, [ROW])
    assert [(f.flag_type, f.severity, f.line_item_ref) for f in flags] == [
        (FlagType.format_warning, FlagSeverity.warning, "1.1")
    ]
    assert "12,3O0.00" in flags[0].description


async def test_dropped_wbpro_row_yields_format_warning_flag_on_claim(db_session):
    flags = await run_wbpro_pipeline(db_session, [ROW, SEVEN_COLUMN_ROW])
    dropped = [f for f in flags if f.description.startswith("Table row dropped")]
    assert [(f.flag_type, f.severity, f.line_item_ref) for f in dropped] == [
        (FlagType.format_warning, FlagSeverity.warning, "1.2")
    ]
    assert dropped[0].description == "Table row dropped: 7 columns (expected 8 or 9) on page 1, row 1"


async def test_unknown_generic_item_type_yields_format_warning_flag_on_claim(db_session):
    _, flags = await run_pipeline(db_session, generic_claim(item_type="labour"))
    assert [(f.flag_type, f.severity, f.line_item_ref, f.description) for f in flags] == [
        (FlagType.format_warning, FlagSeverity.warning, "A1", "item_type 'labour' unknown; recorded as contract_work")
    ]


async def test_unparseable_date_and_missing_claim_number_yield_format_warning_flags(db_session):
    claim, flags = await run_pipeline(db_session, generic_claim(metadata={"period_to": "32/01/25"}))
    assert claim.claim_number == 0
    assert claim.period_to is None
    assert sorted((f.flag_type, f.severity, f.description) for f in flags) == [
        (FlagType.format_warning, FlagSeverity.warning, "claim_number '' missing or unparseable; recorded as 0"),
        (FlagType.format_warning, FlagSeverity.warning, "period_to: unparseable date '32/01/25'; recorded as blank"),
    ]
