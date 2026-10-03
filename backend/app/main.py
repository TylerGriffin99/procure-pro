import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, projects, claims, assessments, harness, claim_flags

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Claim Review API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(claims.router)
app.include_router(assessments.router)
app.include_router(harness.router)
app.include_router(claim_flags.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
