from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    application: str
    version: str
    environment: str
    timestamp: datetime


class ServiceStatus(BaseModel):
    status: str
    detail: str


class ReadinessResponse(BaseModel):
    status: str
    services: dict[str, ServiceStatus]
    timestamp: datetime