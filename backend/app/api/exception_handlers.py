from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DocumentTooLargeError,
    EmptyDocumentError,
    KnowledgeBaseAlreadyExistsError,
    KnowledgeBaseNotFoundError,
    UnsupportedDocumentTypeError,
    RetrievalServiceError,
    ChatServiceError,
)


async def knowledge_base_not_found_handler(
    request: Request,
    exc: KnowledgeBaseNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc),
            "code": "knowledge_base_not_found",
        },
    )


async def knowledge_base_already_exists_handler(
    request: Request,
    exc: KnowledgeBaseAlreadyExistsError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc),
            "code": "knowledge_base_already_exists",
        },
    )

async def document_not_found_handler(
    request: Request,
    exc: DocumentNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc),
            "code": "document_not_found",
        },
    )


async def document_already_exists_handler(
    request: Request,
    exc: DocumentAlreadyExistsError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc),
            "code": "document_already_exists",
        },
    )


async def unsupported_document_type_handler(
    request: Request,
    exc: UnsupportedDocumentTypeError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={
            "detail": str(exc),
            "code": "unsupported_document_type",
        },
    )


async def document_too_large_handler(
    request: Request,
    exc: DocumentTooLargeError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        content={
            "detail": str(exc),
            "code": "document_too_large",
        },
    )


async def empty_document_handler(
    request: Request,
    exc: EmptyDocumentError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "code": "empty_document",
        },
    )


async def document_processing_handler(
    request: Request,
    exc: DocumentProcessingError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc),
            "code": "document_processing_failed",
        },
    )


async def retrieval_service_handler(
    request: Request,
    exc: RetrievalServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": str(exc),
            "code": "retrieval_service_unavailable",
        },
    )


async def chat_service_handler(
    request: Request,
    exc: ChatServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": str(exc),
            "code": "chat_service_unavailable",
        },
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(
        KnowledgeBaseNotFoundError,
        knowledge_base_not_found_handler,
    )
    application.add_exception_handler(
        KnowledgeBaseAlreadyExistsError,
        knowledge_base_already_exists_handler,
    )
    application.add_exception_handler(
        DocumentNotFoundError,
        document_not_found_handler,
    )
    application.add_exception_handler(
        DocumentAlreadyExistsError,
        document_already_exists_handler,
    )
    application.add_exception_handler(
        UnsupportedDocumentTypeError,
        unsupported_document_type_handler,
    )
    application.add_exception_handler(
        DocumentTooLargeError,
        document_too_large_handler,
    )
    application.add_exception_handler(
        EmptyDocumentError,
        empty_document_handler,
    )
    application.add_exception_handler(
        DocumentProcessingError,
        document_processing_handler,
    )
    application.add_exception_handler(
        RetrievalServiceError,
        retrieval_service_handler,
    )
    application.add_exception_handler(
        ChatServiceError,
        chat_service_handler,
    )
