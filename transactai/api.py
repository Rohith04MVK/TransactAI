from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn

from .smart_categorizer import SmartCategorizer
from .schemas import (
    Transaction, TransactionBatch, CategorizeResponse,
    CorrectionRequest, StatsResponse, HealthResponse
)

app = FastAPI(
    title="Smart Transaction Categorizer API",
    description="AI-powered transaction categorization with learning capabilities",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global categorizer instance (loaded once on startup)
categorizer: SmartCategorizer = None

# --- Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    """Load the categorizer on startup"""
    global categorizer
    print("🚀 Loading SmartCategorizer...")
    categorizer = SmartCategorizer(data_dir="./api_categorizer_data")
    print(f"✓ Categorizer loaded with {len(categorizer.categories)} categories")

@app.on_event("shutdown")
async def shutdown_event():
    """Save state on shutdown"""
    global categorizer
    if categorizer:
        categorizer._save_state()
    print("💾 State saved. Shutting down.")

# --- API Endpoints ---
@app.get("/", tags=["General"])
async def root():
    return {
        "message": "Smart Transaction Categorizer API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    return {
        "status": "healthy" if categorizer else "not_ready",
        "model_loaded": categorizer is not None,
        "categories_count": len(categorizer.categories) if categorizer else 0
    }

@app.post("/categorize", response_model=CategorizeResponse, tags=["Categorization"])
async def categorize_transaction(transaction: Transaction):
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    try:
        result = categorizer.process(transaction.transaction)
        return CategorizeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.post("/categorize/batch", response_model=List[CategorizeResponse], tags=["Categorization"])
async def categorize_batch(batch: TransactionBatch):
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    try:
        results = categorizer.batch_process(batch.transactions)
        return [CategorizeResponse(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(e)}")

@app.post("/correct", tags=["Learning"])
async def correct_category(correction: CorrectionRequest, background_tasks: BackgroundTasks):
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    try:
        categorizer.correct(correction.transaction, correction.correct_category)

        return {
            "message": "Correction applied successfully",
            "transaction": correction.transaction,
            "category": correction.correct_category,
            "status": "learned"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Correction error: {str(e)}")

@app.get("/categories", tags=["Categories"])
async def list_categories():
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    return {
        "categories": categorizer.categories,
        "count": len(categorizer.categories)
    }

@app.get("/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_stats():
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    return StatsResponse(
        total_categories=len(categorizer.categories),
        cached_transactions=len(categorizer.cache),
        manual_corrections=len(categorizer.corrections),
        categories_list=categorizer.categories,
        data_directory=str(categorizer.data_dir.absolute())
    )

@app.get("/cache", tags=["Statistics"])
async def get_cache():
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    return {
        "cache": categorizer.cache,
        "count": len(categorizer.cache)
    }

@app.post("/reset", tags=["Management"])
async def reset_system():
    if not categorizer:
        raise HTTPException(status_code=503, detail="Categorizer not initialized")

    try:
        categorizer.reset_data()
        return {
            "message": "System reset successfully",
            "categories": categorizer.categories,
            "status": "fresh_start"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset error: {str(e)}")

# Expose run helper for the old main
def run(UVICORN_APP_MODULE: str = "transactai.api:app", host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    uvicorn.run(
        UVICORN_APP_MODULE,
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
