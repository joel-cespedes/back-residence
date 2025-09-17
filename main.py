import uvicorn
from fastapi import FastAPI, Depends
from app.middlewares import setup_middlewares
from app.deps import get_current_user
from app.routers import auth, residences, structure, residents, tags, devices, tasks, measurements, dashboard

app = FastAPI(title="Residences API", version="1.0.0")
setup_middlewares(app)

app.include_router(auth.router)
app.include_router(residences.router)
app.include_router(structure.router)
app.include_router(residents.router)
app.include_router(tags.router)
app.include_router(devices.router)
app.include_router(tasks.router)
app.include_router(measurements.router)
app.include_router(dashboard.router)


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}



if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=8001)


