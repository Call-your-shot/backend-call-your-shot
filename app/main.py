import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_link import (
    analytics_router,
    energy_router,
    estimation_router,
    green_credits_router,
    ingestion_router,
    pricing_router,
    proposal_router,
    roi_router,
    user_router,
    workflow_router,
)

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

app.include_router(energy_router)
app.include_router(analytics_router)
app.include_router(ingestion_router)
app.include_router(estimation_router)
app.include_router(green_credits_router)
app.include_router(pricing_router)
app.include_router(roi_router)
app.include_router(workflow_router)
app.include_router(user_router)
app.include_router(proposal_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "energy-platform-fastapi",
        "docs": "/docs",
        "health": "/api/health",
        "create_user": "/create-user",
        "create_proposal": "/create-proposal",
        "analytics_dashboard": "/api/v1/analytics/dashboard",
        "ingestion_telemetry": "/api/v1/ingestion/telemetry",
        "estimate_annual_load": "/api/v1/analytics/estimate-annual-load",
        "pricing": "/api/v1/pricing/calculate",
        "price_adjustments": "/api/properties/{property_id}/price-adjustments",
        "lease_requests": "/api/properties/{property_id}/lease-requests",
        "leave_request": "/api/properties/{property_id}/lease-requests/leave",
        "new_house_application": "/api/properties/{property_id}/house-applications",
        "review_lease_request": "/api/properties/{property_id}/lease-requests/{request_id}/status",
        "tenant_plan": "/api/properties/{property_id}/my-plan",
        "landlord_properties": "/api/properties/{property_id}/my-properties",
        "notifications": "/api/properties/{property_id}/notifications",
        "contracts": "/api/properties/{property_id}/contracts/generate",
        "roi": "/api/v1/roi/analyse",
        "green_projects": "/api/v1/green-projects",
    }




if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8001")), reload=True)
