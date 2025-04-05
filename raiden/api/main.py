import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from raiden.core.config import settings
from raiden.api.dependencies import initialize_dependencies, shutdown_dependencies
from raiden.api.endpoints import sessions
from raiden.api.models import ErrorDetail

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Raiden Agent API",
    description="API for controlling the Raiden autonomous web automation agent.",
    version="0.1.0",
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up application...")
    await initialize_dependencies()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down application...")
    await shutdown_dependencies()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )

app.include_router(sessions.router)

@app.get("/", tags=["Status"])
async def read_root():
    return {"status": "Raiden API is operational."}
