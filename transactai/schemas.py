from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class Transaction(BaseModel):
    transaction: str = Field(..., description="Transaction description", example="STARBUCKS 4423")

class TransactionBatch(BaseModel):
    transactions: List[str] = Field(..., description="List of transaction descriptions")

class CategorizeResponse(BaseModel):
    transaction: str
    category: str
    confidence: float
    source: str
    action: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class CorrectionRequest(BaseModel):
    transaction: str = Field(..., example="AMAZON PRIME")
    correct_category: str = Field(..., example="Entertainment")

class StatsResponse(BaseModel):
    total_categories: int
    cached_transactions: int
    manual_corrections: int
    categories_list: List[str]
    data_directory: str

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    categories_count: int
