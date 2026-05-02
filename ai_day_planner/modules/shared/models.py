"""
Shared API models and typed exception classes.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ApiResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    error: Optional[ApiError] = None

    @classmethod
    def ok(cls, data: T) -> "ApiResponse[T]":
        return cls(data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str, details: dict | None = None) -> "ApiResponse":
        return cls(data=None, error=ApiError(code=code, message=message, details=details))


# ---------------------------------------------------------------------------
# Typed application exceptions
# ---------------------------------------------------------------------------

class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""
    def __init__(self, resource: str, resource_id: str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} with id '{resource_id}' does not exist")


class ConflictError(Exception):
    """Raised when an operation conflicts with existing state."""
    def __init__(self, message: str, details: dict | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


class DomainValidationError(Exception):
    """Raised when domain-level validation fails (beyond Pydantic schema)."""
    def __init__(self, message: str, fields: list[dict] | None = None) -> None:
        self.fields = fields or []
        super().__init__(message)
