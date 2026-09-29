from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from Hindsight.ai.deal_brief import DealBriefRateLimitError
from Hindsight.ai.deal_autopsy import DealAutopsyRateLimitError
from .database import close_database_client
from .routes import api_router
from .routes.hindsight_intelligence import SERVICE_ERRORS


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    close_database_client()


app = FastAPI(title="DealMind API", version="1.0.0", lifespan=lifespan)

_configured_origins = os.getenv("FRONTEND_ORIGINS")
_allowed_origins = (
    [origin.strip().rstrip("/") for origin in _configured_origins.split(",") if origin.strip()]
    if _configured_origins is not None
    else ["http://127.0.0.1:5500", "http://localhost:5500"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def service_error_handler(_: Request, exc: RuntimeError) -> JSONResponse:
    provider_error = exc
    while provider_error.__cause__ is not None:
        provider_error = provider_error.__cause__
    if (
        isinstance(exc, (DealBriefRateLimitError, DealAutopsyRateLimitError))
        or getattr(provider_error, "status_code", None) == 429
    ):
        response = getattr(provider_error, "response", None)
        retry_after = (
            exc.retry_after
            if isinstance(exc, (DealBriefRateLimitError, DealAutopsyRateLimitError))
            else getattr(response, "headers", {}).get("retry-after")
        )
        headers = {"Retry-After": retry_after} if retry_after else None
        content = {"detail": str(exc)}
        provider_message = getattr(exc, "provider_message", None)
        if provider_message:
            content["provider_message"] = provider_message
            content["retry_after"] = retry_after
        return JSONResponse(status_code=429, content=content, headers=headers)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


for service_error in SERVICE_ERRORS:
    app.add_exception_handler(service_error, service_error_handler)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "The DealMind service could not complete the request."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
