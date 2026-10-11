from app.constants.enums import FlagSeverity, FlagType
from app.harness.executors.create_records import execute_create_records
from app.harness.executors.extract_wbpro import parse_wbpro
from app.harness.models import HarnessType
from app.harness.schemas import RawExtraction, RawPage
from app.repos import document_repo, harness_repo
from tests.integration.characterisation_fixtures import seed_project, seed_user

ROW = ["1.1", "Excavation", "12,3O0.00", "50.00", "100.00", "0.00", "100.00", "0.00"]
SEVEN_COLUMN_ROW = ["1.2", "Short row", "100.00", "50.00", "50.00", "0.00", "50.00"]


async def run_wbpro_pipeline(db_session, rows):
    user = await seed_user(db_session)
    project = await seed_project(db_session, user)
    doc = await document_repo.create_document(db_session, project.id, "c.pdf", "application/pdf", b"%PDF-1.4 x")
    session = await harness_repo.create_session(
        db=db_session, user_id=user.id, project_id=project.id, harness_type=HarnessType.CLAIM_PARSE, document_id=doc.id
    )
    raw = RawExtraction(pages=[RawPage(page_num=1, text="Claim No. 1\nCONTRACT WORKS", tables=[rows])])
    parsed_json = parse_wbpro(raw).model_dump_json(exclude_none=True)
    await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", parsed_json)
    await harness_repo.write_workspace_file(db_session, session.id, "wbs_matches.json", "[]")
    await harness_repo.write_workspace_file(db_session, session.id, "vps_matches.json", "[]")
    await db_session.flush()

    result = await execute_create_records(
        db=db_session, session_id=session.id, user_id=user.id, project_id=project.id, config={}, llm=None
    )

    return await harness_repo.list_flags_by_claim(db_session, result.claim_id)


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
