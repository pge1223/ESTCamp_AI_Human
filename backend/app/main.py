import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.api.v1.router import router as v1_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 전역 에러 핸들러 ───────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """요청 파라미터/바디 유효성 검사 실패 (422)"""
    logger.warning("Validation error: %s %s — %s", request.method, request.url, exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "요청 데이터가 올바르지 않습니다.",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """404, 400 등 의도된 HTTP 에러"""
    logger.warning("HTTP %d: %s %s — %s", exc.status_code, request.method, request.url, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError):
    """DB 쿼리/연결 오류"""
    logger.error("DB error: %s %s — %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "database_error",
            "message": "데이터베이스 오류가 발생했습니다.",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """그 외 모든 예상치 못한 에러"""
    logger.error("Unhandled exception: %s %s — %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "서버 내부 오류가 발생했습니다.",
        },
    )


# ─────────────────────────────────────────────────────────────

app.include_router(v1_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
