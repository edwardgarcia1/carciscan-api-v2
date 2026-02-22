from fastapi import FastAPI
from app.core.config import settings
from app.routers.predict import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V2_STR}/openapi.json"
)

app.include_router(api_router, prefix=settings.API_V2_STR)

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Carciscan API. See /docs for the API documentation."}

