from typing import Any


class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.details = details or []


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class Unprocessable(DomainError):
    status_code = 422
    code = "validation_error"


class ServiceUnavailable(DomainError):
    status_code = 503
    code = "database_unavailable"
