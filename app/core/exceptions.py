from __future__ import annotations

from fastapi import HTTPException, status


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", status_code=404)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, status_code=409)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(AppException):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=403)


class ValidationError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, status_code=429)


class URLExpiredError(AppException):
    def __init__(self) -> None:
        super().__init__("This short link has expired", status_code=410)


class URLNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Short URL")


class ShortCodeCollisionError(AppException):
    def __init__(self) -> None:
        super().__init__("Failed to generate unique short code", status_code=500)
