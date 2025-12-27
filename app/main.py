from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.care_sessions.router import router as care_sessions_router

app = FastAPI(
    title="Care Session Service",
    description="NFC-based care session management microservice",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(care_sessions_router)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "care-session-service"}
