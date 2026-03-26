from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="A scalable multi-channel notification service supporting Email, SMS and Push",
    version="1.0.0",
    debug=settings.DEBUG
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME
    }