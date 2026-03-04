from core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router import availabilities, departments, schedules, workers

app = FastAPI(
    title="Church Worker Scheduler API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(workers.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(availabilities.router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
