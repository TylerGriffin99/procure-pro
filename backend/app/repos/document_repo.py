import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.values import PDF_MEDIA_TYPE
from app.models.document import Document


async def create_document(
    db: AsyncSession, project_id: uuid.UUID, filename: str, content_type: str, content: bytes
) -> Document:
    """Persist an uploaded PDF as a Document row."""
    doc = Document(
        project_id=project_id,
        filename=filename or "upload.pdf",
        content_type=content_type or PDF_MEDIA_TYPE,
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        file_data=content,
    )
    db.add(doc)
    await db.flush()
    return doc


async def get_document(db: AsyncSession, document_id: uuid.UUID) -> Document | None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


async def delete(db: AsyncSession, document_id: uuid.UUID) -> None:
    document = await get_document(db, document_id)
    if document is not None:
        await db.delete(document)
        await db.flush()
