"""Phase 0: Extract raw text and tables from PDF using pdfplumber."""

import logging
import uuid
from io import BytesIO
from typing import Any

import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_client import LlmClient
from app.harness.extract_shared import extract_metadata
from app.harness.schemas import RawExtraction, RawPage
from app.repos import document_repo

logger = logging.getLogger(__name__)


async def execute_raw_extraction(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
    llm: LlmClient,
) -> RawExtraction:
    document_id = config.get("document_id")
    if not document_id:
        raise ValueError("config['document_id'] is required for raw_extraction")
    document = await document_repo.get_document(db, uuid.UUID(str(document_id)))
    if document is None:
        raise FileNotFoundError(f"Document not found: {document_id}")

    with pdfplumber.open(BytesIO(document.file_data)) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("PDF has zero pages")
        pages = [
            RawPage(
                page_num=page.page_number,
                text=page.extract_text() or "",
                tables=[
                    [[str(cell) if cell is not None else "" for cell in row] for row in table]
                    for table in page.extract_tables() or []
                ],
            )
            for page in pdf.pages
        ]

    result = RawExtraction(metadata=extract_metadata(pages[0].text), pages=pages)
    logger.info("Raw extraction: %d pages, %d tables total", len(pages), sum(len(p.tables) for p in pages))
    return result
