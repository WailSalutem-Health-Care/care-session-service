"""Care Session Service - FastAPI Application."""

from dotenv import load_dotenv
import os
import threading
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env file in development
if os.path.exists(".env"):
    load_dotenv()

# Configure structured logging with trace correlation
from app.observability.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


def _start_nfc_consumer():
    """Start NFC event consumer in background thread."""
    try:
        from app.messaging.consumer import NFCEventConsumer

        NFCEventConsumer().start_consuming()
    except Exception as e:
        logger.error(f"NFC consumer failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    # Initialize OpenTelemetry
    from app.observability.telemetry import init_telemetry, shutdown_telemetry, instrument_sqlalchemy

    telemetry_initialized = init_telemetry()
    if telemetry_initialized:
        logger.info("OpenTelemetry initialized successfully")

        # Instrument database
        try:
            from app.db.postgres import engine

            instrument_sqlalchemy(engine)
        except Exception as e:
            logger.warning(f"Failed to instrument database: {e}")
    else:
        logger.warning("OpenTelemetry initialization failed, continuing without telemetry")

    # Start NFC consumer in background thread
    thread = threading.Thread(target=_start_nfc_consumer, daemon=True)
    thread.start()

    yield

    # Shutdown telemetry on app shutdown
    if telemetry_initialized:
        logger.info("Shutting down OpenTelemetry")
        shutdown_telemetry()


app = FastAPI(title="Care Session Service", lifespan=lifespan)

# Add Telemetry Middleware (before CORS)
from app.observability.middleware import TelemetryMiddleware

app.add_middleware(TelemetryMiddleware, excluded_paths=["/health"])

# Instrument FastAPI
from app.observability.telemetry import instrument_fastapi

instrument_fastapi(app)

# CORS
allowed_origins_str = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://wailsalutem-web-ui.netlify.app,https://wailsalutem-suite.netlify.app/",
)
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
try:
    from app.care_sessions.router import router as care_sessions_router

    app.include_router(care_sessions_router)
except Exception as e:
    logger.error(f"Failed to load care_sessions router: {e}")

try:
    from app.reports.router import router as reports_router

    app.include_router(reports_router)
except Exception as e:
    logger.error(f"Failed to load reports router: {e}")

try:
    from app.feedback.router import router as feedback_router

    app.include_router(feedback_router)
except Exception as e:
    logger.error(f"Failed to load feedback router: {e}")


@app.get("/health")
async def health():
    """Health check with dependency status"""
    status = {"status": "healthy", "service": "care-session-service", "dependencies": {}}

    # Check database
    try:
        from app.db.postgres import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["dependencies"]["database"] = {"status": "healthy"}
    except Exception as e:
        status["status"] = "degraded"
        status["dependencies"]["database"] = {"status": "unhealthy", "error": str(e)}

    return status
