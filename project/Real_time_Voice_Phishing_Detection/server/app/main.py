import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.session import router as session_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

app = FastAPI(title="Vaia Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
