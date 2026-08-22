import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

load_dotenv(".env.local")

app = FastAPI(title="Energy Platform API", version="0.1.0")

allowed_origins = os.getenv("FASTAPI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "energy-platform-fastapi",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
