# TransactAI

A smart transaction categorization system that uses AI to automatically classify financial transactions. The system learns from corrections and builds a knowledge base over time, featuring both a REST API and an interactive web frontend.

## Features

- **AI-Powered Categorization**: Uses sentence transformers (all-MiniLM-L6-v2) and LLM (Qwen2.5-1.5B) to intelligently categorize transactions
- **Multi-Layer Intelligence**: Combines caching, keyword rules, vector similarity search, and LLM reasoning for optimal accuracy
- **Learning System**: Improves accuracy through manual corrections and automatic category deduplication
- **Persistent Storage**: Saves learned categories, corrections, and embeddings between sessions
- **REST API**: FastAPI-based endpoints for easy integration
- **Batch Processing**: Handle multiple transactions efficiently with progress tracking
- **Interactive Web UI**: Modern frontend for testing and reviewing categorizations
- **Low-Confidence Detection**: Automatically flags transactions that need human review

## Installation

This project uses Python 3.12 with `uv` for dependency management.

### Prerequisites

- Python 3.12+
- CUDA-capable GPU (optional, for faster inference)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Rohith04MVK/TransactAI
cd TransactAI
```

2. Install dependencies:
```bash
pip install -e .
```

3. Install additional AI dependencies:
```bash
pip install sentence-transformers transformers torch rich
```

## Quick Start

### Start the API Server

```bash
python run.py
```

Or using uvicorn directly:
```bash
uvicorn transactai.api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

### Access the Web Interface

Open [frontend/index.html](frontend/index.html) in your browser, or serve it with:

```bash
python -m http.server 8080 --directory frontend
```

Then navigate to `http://localhost:8080`

## API Endpoints

### Health Check
```bash
GET /health
```
Returns model status and category count.

### Categorize Single Transaction
```bash
POST /categorize
Content-Type: application/json

{
  "transaction": "STARBUCKS 4423"
}
```

**Response:**
```json
{
  "transaction": "STARBUCKS 4423",
  "category": "Food & Dining",
  "confidence": 0.92,
  "source": "Vector DB",
  "action": "Existing",
  "timestamp": "2024-01-15T10:30:00"
}
```

### Categorize Multiple Transactions (Batch)
```bash
POST /categorize/batch
Content-Type: application/json

{
  "transactions": ["STARBUCKS 4423", "AMAZON PRIME", "SHELL GAS STATION"]
}
```

### Submit a Correction (Train the Model)
```bash
POST /correct
Content-Type: application/json

{
  "transaction": "AMAZON PRIME",
  "correct_category": "Entertainment"
}
```

The system will learn from this correction and improve future predictions.

### Get System Statistics
```bash
GET /stats
```

Returns:
- Total categories
- Cached transactions count
- Manual corrections count
- Full category list
- Data directory path

### List All Categories
```bash
GET /categories
```

### View Transaction Cache
```bash
GET /cache
```

### Reset System
```bash
POST /reset
```
⚠️ **Warning**: This clears all learned data and resets to default seed categories.

## How It Works

The system uses a multi-layered approach for intelligent categorization:

### 1. **Cache Layer** (Instant)
Checks for exact matches in previously categorized transactions for instant results.

### 2. **Keyword Rules Layer** (Fast)
Matches against predefined seed categories using keyword patterns:
- Fast Food: `["mcdonalds", "kfc", "burger king", ...]`
- Groceries: `["walmart", "target", "whole foods", ...]`
- Utilities: `["electric", "water", "gas", "internet", ...]`
- And 9+ more categories

### 3. **Vector Similarity Search** (Semantic)
Uses sentence embeddings to find semantically similar categories:
- Confidence ≥ 0.55: Auto-categorize
- Confidence < 0.55: Escalate to LLM

### 4. **LLM Reasoning** (Intelligent)
For low-confidence cases, consults the Qwen2.5-1.5B language model with context-aware prompting.

### 5. **Deduplication** (Smart)
Prevents creating redundant categories by checking semantic similarity (threshold: 0.70). Maps similar suggestions to existing categories.

## Configuration

Key parameters in [`transactai/smart_categorizer.py`](transactai/smart_categorizer.py):

```python
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'          # Sentence transformer model
LLM_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"   # Language model
SIMILARITY_THRESHOLD = 0.55                    # Min confidence for auto-categorization
DEDUPLICATION_THRESHOLD = 0.70                 # Similarity threshold for merging categories
CONFIDENCE_FLOOR = 0.30                        # Below this, always consult LLM
```

## Data Storage

All learned data is persisted in `./api_categorizer_data/`:

- **`embeddings.pt`**: PyTorch tensor file containing:
  - Category embeddings (vectors)
  - Category names list
  
- **`state.json`**: Human-readable JSON containing:
  - Transaction cache (exact match lookup)
  - Manual corrections history
  - Category seed keywords
  - Last update timestamp

## Project Structure

```
TransactAI/
├── transactai/
│   ├── __init__.py              # Package initialization
│   ├── api.py                   # FastAPI application with endpoints
│   ├── schemas.py               # Pydantic models for request/response validation
│   └── smart_categorizer.py    # Core AI categorization logic
├── frontend/
│   ├── index.html               # Web UI
│   └── js/
│       └── app.js               # Frontend JavaScript logic
├── run.py                       # Simple server launcher
├── main.py                      # Alternative entry point (deprecated)
├── pyproject.toml               # Project dependencies
└── README.md                    # This file
```

## Seed Categories (Default)

The system starts with 12 intelligent seed categories:

1. **Fast Food** - Quick service restaurants
2. **Groceries** - Supermarkets and food stores
3. **Utilities** - Electric, water, gas, internet, phone bills
4. **Transportation** - Uber, fuel, parking, public transit
5. **Entertainment** - Streaming services, movies, concerts
6. **Online Shopping** - E-commerce platforms
7. **Food Delivery** - Meal delivery services
8. **Rent** - Housing payments
9. **Income** - Salary, wages, deposits
10. **Health** - Medical, pharmacy, fitness
11. **Travel** - Hotels, flights, bookings
12. **Subscription** - Recurring memberships

New categories are automatically created by the LLM when needed.

## Usage Examples

### Python API Client

```python
import requests

API_URL = "http://localhost:8000"

# Categorize a transaction
response = requests.post(f"{API_URL}/categorize", json={
    "transaction": "STARBUCKS COFFEE 5512"
})
result = response.json()
print(f"Category: {result['category']}, Confidence: {result['confidence']}")

# Batch processing
response = requests.post(f"{API_URL}/categorize/batch", json={
    "transactions": [
        "UBER TRIP 8X92",
        "WHOLEFDS MRK 442",
        "NETFLIX.COM"
    ]
})
results = response.json()
for r in results:
    print(f"{r['transaction']} → {r['category']} ({r['confidence']:.2%})")

# Submit correction
requests.post(f"{API_URL}/correct", json={
    "transaction": "PRIME VIDEO SUBSCRIPTION",
    "correct_category": "Entertainment"
})
```

### Frontend Usage

1. **Dashboard Tab**: View performance metrics and category distribution
2. **Classify Tab**: Upload CSV data (Date, Description, Amount format) and review categorizations
3. **Taxonomy Tab**: Manage category labels and add custom categories

## Performance & Resources

- **Model Size**: ~3GB (embeddings + LLM weights)
- **Inference Speed**: 
  - Cache hit: <1ms
  - Keyword match: <5ms
  - Vector search: ~10-50ms
  - LLM inference: ~500-2000ms (GPU) / ~2-5s (CPU)
- **Storage**: ~1-10MB for learned data (scales with usage)

## Development

### Running Tests
```bash
# Test single transaction
curl -X POST "http://localhost:8000/categorize" \
  -H "Content-Type: application/json" \
  -d '{"transaction": "AMAZON WEB SERVICES"}'

# Test batch
curl -X POST "http://localhost:8000/categorize/batch" \
  -H "Content-Type: application/json" \
  -d '{"transactions": ["UBER EATS", "SPOTIFY", "COSTCO"]}'
```

### Hot Reload Development
```bash
uvicorn transactai.api:app --reload --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Models Not Loading
- Ensure you have sufficient RAM/VRAM (minimum 8GB recommended)
- First run downloads models from HuggingFace (~3GB)
- Check internet connection for initial model download

### Low Accuracy
- Submit corrections via `/correct` endpoint to train the system
- Check [`transactai/smart_categorizer.py`](transactai/smart_categorizer.py) to add seed keywords for your use case
- Lower `SIMILARITY_THRESHOLD` for stricter matching

### CORS Issues (Frontend)
- API has CORS enabled for all origins (`allow_origins=["*"]`)
- For production, restrict to specific origins in [`transactai/api.py`](transactai/api.py)

## License

This project is licensed under the MIT license.