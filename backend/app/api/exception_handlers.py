from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    KnowledgeBaseAlreadyExistsError,
    KnowledgeBaseNotFoundError,
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


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(
        KnowledgeBaseNotFoundError,
        knowledge_base_not_found_handler,
    )
    application.add_exception_handler(
        KnowledgeBaseAlreadyExistsError,
        knowledge_base_already_exists_handler,
    )