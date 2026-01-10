from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Care Session Service")

# Import and include routers with error handling
try:
    from app.care_sessions.router import router as care_sessions_router
    app.include_router(care_sessions_router)
    logger.info("Care sessions router loaded successfully")
except Exception as e:
    logger.error(f"Failed to load care_sessions router: {e}")

try:
    from app.reports.router import router as reports_router
    app.include_router(reports_router)
    logger.info("Reports router loaded successfully")
except Exception as e:
    logger.error(f"Failed to load reports router: {e}")

try:
    from app.feedback.router import router as feedback_router
    app.include_router(feedback_router)
    logger.info("Feedback router loaded successfully")
except Exception as e:
    logger.error(f"Failed to load feedback router: {e}")

@app.get("/health")
def health():
    return {"status": "ok", "service": "care-session-service"}

