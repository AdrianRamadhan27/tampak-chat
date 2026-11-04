from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "requestId": getattr(request.state, "request_id", None),
                "retryable": error.status in {429, 502, 503, 504},
            }
        },
    )
