from fastapi import FastAPI

app = FastAPI(title="Care Session Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "care-session-service"}
