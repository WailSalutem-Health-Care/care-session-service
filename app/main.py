from fastapi import FastAPI
from app.care_sessions.router import router as care_sessions_router
from app.reports.router import router as reports_router
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.include_router(care_sessions_router)
app.include_router(reports_router)

@app.get("/health")
def health():
    return {"status": "ok"}

