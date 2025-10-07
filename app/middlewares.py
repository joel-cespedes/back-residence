from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

def setup_middlewares(app: FastAPI):
    # GZIP Compression - comprime respuestas > 1KB
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS completamente liberado para desarrollo
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Permite cualquier origen
        allow_credentials=True,
        allow_methods=["*"],  # Permite cualquier método HTTP
        allow_headers=["*"],   # Permite cualquier header
    )

    logger = logging.getLogger("uvicorn.error")

    # Rate limiting simple en memoria
    login_attempts = defaultdict(list)

    @app.middleware("http")
    async def rate_limit_and_timing(request: Request, call_next):
        # Rate limiting solo para /auth/login
        if request.url.path == "/auth/login" and request.method == "POST":
            client_ip = request.client.host
            now = datetime.now()

            # Limpiar intentos viejos (> 1 minuto)
            login_attempts[client_ip] = [
                attempt for attempt in login_attempts[client_ip]
                if now - attempt < timedelta(minutes=1)
            ]

            # Verificar límite (5 por minuto)
            if len(login_attempts[client_ip]) >= 5:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many login attempts. Try again in 1 minute."}
                )

            # Registrar intento
            login_attempts[client_ip].append(now)

        # Timing middleware
        start = time.time()
        resp = await call_next(request)
        dur = (time.time() - start) * 1000
        logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, resp.status_code, dur)
        return resp

