from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import time
import logging

def setup_middlewares(app: FastAPI):
    origins = [o.strip() for o in settings.cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger = logging.getLogger("uvicorn.error")

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.time()
        resp = await call_next(request)
        dur = (time.time() - start) * 1000
        logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, resp.status_code, dur)
        return resp

