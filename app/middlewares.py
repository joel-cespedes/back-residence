from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import time
import logging

def setup_middlewares(app: FastAPI):
    # CORS completamente liberado para desarrollo
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Permite cualquier origen
        allow_credentials=True,
        allow_methods=["*"],  # Permite cualquier método HTTP
        allow_headers=["*"],   # Permite cualquier header
    )

    logger = logging.getLogger("uvicorn.error")

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.time()
        resp = await call_next(request)
        dur = (time.time() - start) * 1000
        logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, resp.status_code, dur)
        return resp

