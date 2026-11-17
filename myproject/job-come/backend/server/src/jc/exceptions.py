"""Application errors."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, *, code: str = "app_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AuthError(AppError):
    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message, code=code)


class ConflictError(AppError):
    def __init__(self, message: str, *, code: str = "conflict") -> None:
        super().__init__(message, code=code)


class NotFoundError(AppError):
    def __init__(self, message: str, *, code: str = "not_found") -> None:
        super().__init__(message, code=code)


class ForbiddenError(AppError):
    def __init__(self, message: str, *, code: str = "forbidden") -> None:
        super().__init__(message, code=code)


class GoneError(AppError):
    def __init__(self, message: str, *, code: str = "gone") -> None:
        super().__init__(message, code=code)


class TooManyRequestsError(AppError):
    def __init__(self, message: str, *, code: str = "rate_limited") -> None:
        super().__init__(message, code=code)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str, *, code: str = "unavailable") -> None:
        super().__init__(message, code=code)
