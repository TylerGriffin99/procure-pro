import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import error_handlers
from app.config import settings
from app.routers import assessments, auth, claim_flags, claims, harness, projects

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Claim Review API", version="0.1.0", lifespan=lifespan)
error_handlers.register(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix=settings.api_prefix)
for router in (auth.router, projects.router, claims.router, assessments.router, harness.router, claim_flags.router):
    api.include_router(router)
app.include_router(api)


@app.get("/health")
async def health():
    return {"status": "ok"}
