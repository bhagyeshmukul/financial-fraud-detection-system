from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.fraud_routes import router as fraud_router

app = FastAPI(title="Financial Fraud Detection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fraud_router)


@app.get("/")
def health():
    return {"status": "ok", "service": "financial-fraud-detection-system"}
