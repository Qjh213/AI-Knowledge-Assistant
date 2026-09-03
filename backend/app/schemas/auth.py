from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r'^[a-z0-9][a-z0-9_.-]{2,31}$')]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


class LoginInput(StrictInput):
    username: Username
    password: str = Field(min_length=1, max_length=128)


class PasswordChange(StrictInput):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class UserCreate(StrictInput):
    username: Username
    temporary_password: Password


class AdminConfirmation(StrictInput):
    admin_password: str = Field(min_length=1, max_length=128)


class UserStatus(AdminConfirmation):
    is_active: bool


class PasswordReset(AdminConfirmation):
    temporary_password: Password


class UserLimits(StrictInput):
    storage_limit_mb: int = Field(ge=0, le=1_048_576)
    upload_limit_mb: int = Field(ge=1, le=100)
    processing_limit: int = Field(ge=1, le=16)
    daily_ai_limit: int = Field(ge=0, le=100_000)
