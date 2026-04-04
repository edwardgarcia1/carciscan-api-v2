from fastapi import FastAPI
from app.core.config import settings
from app.routers.predict import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V2_STR}/openapi.json"
)

app.include_router(api_router, prefix=settings.API_V2_STR)


@app.on_event("startup")
async def startup_event():
    """
    Pre-load the carcinogenicity model at startup to eliminate
    cold start penalty on first request.
    """
    from app.services.predictor import get_carcinogenicity_model_data
    model_data = get_carcinogenicity_model_data()
    if "error" in model_data:
        raise RuntimeError(f"Failed to load carcinogenicity model: {model_data['error']}")


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Carciscan API. See /docs for the API documentation."}

