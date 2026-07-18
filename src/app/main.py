from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth
from app.db.database import init_db

load_dotenv()
# fmt: off  MC8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2YTBkYU5BPT06YThhOTlmYzI=


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="LangGraph Auth API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
# noqa  MS8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2YTBkYU5BPT06YThhOTlmYzI=

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8008,
        reload=True,
        lifespan="on",
    )
