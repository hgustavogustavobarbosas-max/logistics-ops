class AppError(Exception):
    """Erro de aplicação com status HTTP e código estável para o cliente."""

    status_code = 500
    code = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers
        if code is not None:
            self.code = code


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InsufficientStockError(ConflictError):
    code = "insufficient_stock"


class InvalidStatusTransitionError(ConflictError):
    code = "invalid_status_transition"


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule_violation"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"
