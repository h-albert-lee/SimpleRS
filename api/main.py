from fastapi import FastAPI
from api.routers.recommendations import router as recommendations_router

app = FastAPI(
    title="Recommendation System",
    version="1.0.0"
)

app.include_router(recommendations_router, prefix="/recommendations")
