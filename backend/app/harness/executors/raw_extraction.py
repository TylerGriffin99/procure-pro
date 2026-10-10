"""Phase 0: Extract raw text and tables from PDF using pdfplumber."""
import logging
import uuid
from io import BytesIO
from typing import Any

import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import document_repo

logger = logging.getLogger(__name__)


async def execute_raw_extraction(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    config: dict[str, Any],
) -> dict:
    """Extract raw text and tables from every page of a PDF."""
    document_id = config.get("document_id")
    if not document_id:
        raise ValueError("config['document_id'] is required for raw_extraction")
    document = await document_repo.get_document(db, uuid.UUID(str(document_id)))
    if document is None:
        raise FileNotFoundError(f"Document not found: {document_id}")

    pages_data: list[dict[str, Any]] = []
    metadata: dict[str, str] = {}

    with pdfplumber.open(BytesIO(document.file_data)) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("PDF has zero pages")

        for page in pdf.pages:
            text = page.extract_text() or ""
            tables = page.extract_tables() or []

            clean_tables = []
            for table in tables:
                clean_table = []
                for row in table:
                    clean_row = [str(cell) if cell is not None else "" for cell in row]
                    clean_table.append(clean_row)
                clean_tables.append(clean_table)

            pages_data.append({
                "page_num": page.page_number,
                "text": text,
                "tables": clean_tables,
            })

        first_text = pages_data[0]["text"] if pages_data else ""
        metadata = _extract_metadata(first_text)

    logger.info(
        "Raw extraction: %d pages, %d tables total",
        len(pages_data),
        sum(len(p["tables"]) for p in pages_data),
    )

    return {"metadata": metadata, "pages": pages_data}


def _extract_metadata(text: str) -> dict[str, str]:
    """Extract basic metadata from first page text via simple pattern matching."""
    import re
    metadata = {}

    patterns = {
        "claim_number": r"Claim\s*No\.?\s*[:\-]?\s*(\d+)",
        "period_from": r"Period\s*From\s*[:\-]?\s*([\d/]+)",
        "period_to": r"Period\s*To\s*[:\-]?\s*([\d/]+)",
        "payment_due": r"Payment\s*Due\s*[:\-]?\s*([\d/]+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1)

    return metadata
