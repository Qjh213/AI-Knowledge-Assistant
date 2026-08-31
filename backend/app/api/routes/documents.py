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

from app.services.document_processing import (
    DocumentProcessingService,
)
from app.services.mineru_processing import (
    MinerUDocumentProcessingService,
)
from app.database.models import DocumentParser
from app.services.background_processing import (
    BackgroundDocumentProcessor,
    background_document_processor,
)


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


def get_document_processing_service() -> DocumentProcessingService:
    return DocumentProcessingService()


ProcessingServiceDependency = Annotated[
    DocumentProcessingService,
    Depends(get_document_processing_service),
]


def get_mineru_processing_service(
) -> MinerUDocumentProcessingService:
    return MinerUDocumentProcessingService()


MinerUProcessingServiceDependency = Annotated[
    MinerUDocumentProcessingService,
    Depends(get_mineru_processing_service),
]


def get_background_document_processor() -> BackgroundDocumentProcessor:
    return background_document_processor


BackgroundProcessorDependency = Annotated[
    BackgroundDocumentProcessor,
    Depends(get_background_document_processor),
]


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


@router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
)
def process_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
    processing_service: ProcessingServiceDependency,
) -> DocumentResponse:
    document = processing_service.process(
        session,
        knowledge_base_id,
        document_id,
    )

    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/process/background",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue document processing in the background",
)
def queue_document_processing(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
    background_processor: BackgroundProcessorDependency,
    parser: DocumentParser = DocumentParser.LOCAL,
) -> DocumentResponse:
    document = background_processor.enqueue(
        session,
        knowledge_base_id,
        document_id,
        parser,
    )
    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/process/retry",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed document processing in the background",
)
def retry_document_processing(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
    background_processor: BackgroundProcessorDependency,
) -> DocumentResponse:
    document = background_processor.enqueue(
        session,
        knowledge_base_id,
        document_id,
        None,
        retry_only=True,
    )
    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/process/mineru",
    response_model=DocumentResponse,
    summary="Submit a document to MinerU",
)
def submit_document_to_mineru(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
    processing_service: MinerUProcessingServiceDependency,
) -> DocumentResponse:
    document = processing_service.submit(
        session,
        knowledge_base_id,
        document_id,
    )

    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/process/mineru/refresh",
    response_model=DocumentResponse,
    summary="Refresh and finalize a MinerU task",
)
def refresh_mineru_document_processing(
    knowledge_base_id: UUID,
    document_id: UUID,
    session: SessionDependency,
    processing_service: MinerUProcessingServiceDependency,
) -> DocumentResponse:
    document = processing_service.finalize(
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
