from fastapi import FastAPI
from app.care_sessions.router import router as care_sessions_router
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.include_router(care_sessions_router)

@app.get("/health")
def health():
    return {"status": "ok"}

