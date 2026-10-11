"""Domain and HTTP-facing error types."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An error that maps directly to an HTTP response."""

    def __init__(
        self, status: int, code: str, message: str, details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    @classmethod
    def not_found(cls, what: str = "Resource") -> ApiError:
        return cls(404, "NOT_FOUND", f"{what} not found")

    @classmethod
    def unauthorized(cls) -> ApiError:
        return cls(401, "UNAUTHORIZED", "Missing or invalid credentials")

    @classmethod
    def conflict(cls, message: str) -> ApiError:
        return cls(409, "CONFLICT", message)

    @classmethod
    def unprocessable(cls, code: str, message: str) -> ApiError:
        return cls(422, code, message)


class StateConflictError(Exception):
    """Raised by a store when an optimistic-concurrency or state precondition fails."""


class PickupNotFoundError(Exception):
    """Raised by a store when the pickup does not exist."""
