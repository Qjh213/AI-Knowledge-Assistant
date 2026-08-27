from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
)
from app.services.document import DocumentService


router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/documents",
    tags=["Documents"],
)

SessionDependency = Annotated[Session, Depends(get_db)]
UploadedDocument = Annotated[
    UploadFile,
    File(description="TXT, Markdown, PDF, or DOCX document"),
]

document_service = DocumentService()


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: UUID,
    session: SessionDependency,
    file: UploadedDocument,
) -> DocumentResponse:
    document = await document_service.upload(
        session,
        knowledge_base_id,
        file,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=DocumentListResponse,
)
def list_documents(
    knowledge_base_id: UUID,
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentListResponse:
    items, total = document_service.list(
        session,
        knowledge_base_id,
        offset=offset,
        limit=limit,
    )

    return DocumentListResponse(
        items=[
            DocumentResponse.model_validate(item)
            for item in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
) -> DocumentResponse:
    document = document_service.get(
        session,
        knowledge_base_id,
        document_id,
    )
    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
) -> Response:
    document_service.delete(
        session,
        knowledge_base_id,
        document_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)