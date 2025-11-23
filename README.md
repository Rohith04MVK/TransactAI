# TransactAI

A smart transaction categorization API that uses AI to automatically classify financial transactions. The system learns from corrections and builds a knowledge base over time.

## Features

- **AI-Powered Categorization**: Uses sentence transformers and LLM (Qwen2.5-1.5B) to intelligently categorize transactions
- **Multi-Layer Intelligence**: Combines caching, keyword rules, vector similarity, and LLM reasoning
- **Learning System**: Improves accuracy through manual corrections and automatic deduplication
- **Persistent Storage**: Saves learned categories and corrections between sessions
- **REST API**: FastAPI-based endpoints for easy integration
- **Batch Processing**: Handle multiple transactions efficiently

## Installation

This project uses Python 3.12. Install dependencies with uv or pip:

```bash
pip install -e .
```

Additional dependencies needed:
```bash
pip install sentence-transformers transformers torch rich
```

## Quick Start

Start the API server:

```bash
python run.py
```

Or use uvicorn directly:

```bash
uvicorn transactai.api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

## API Endpoints

### Categorize Single Transaction
```bash
POST /categorize
{
  "transaction": "STARBUCKS 4423"
}
```

### Categorize Multiple Transactions
```bash
POST /categorize/batch
{
  "transactions": ["STARBUCKS 4423", "AMAZON PRIME", "SHELL GAS"]
}
```

### Correct a Categorization
```bash
POST /correct
{
  "transaction": "AMAZON PRIME",
  "correct_category": "Entertainment"
}
```

### Get System Stats
```bash
GET /stats
```

### List All Categories
```bash
GET /categories
```

## How It Works

1. **Cache Layer**: Checks for exact matches in previous transactions
2. **Keyword Rules**: Matches against predefined seed categories (Fast Food, Groceries, etc.)
3. **Vector Similarity**: Uses semantic embeddings to find similar categories
4. **LLM Reasoning**: Asks the language model to suggest appropriate categories
5. **Deduplication**: Prevents creating redundant categories by checking similarity

The system starts with 12 seed categories and expands as it encounters new transaction types.

## Data Storage

All learned data is stored in `./api_categorizer_data/`:
- `embeddings.pt`: Vector embeddings for categories
- `state.json`: Cache, corrections, and category seeds

## Configuration

Key parameters in [`transactai/smart_categorizer.py`](transactai/smart_categorizer.py):

- `SIMILARITY_THRESHOLD`: 0.55 (minimum confidence for vector matches)
- `DEDUPLICATION_THRESHOLD`: 0.70 (similarity threshold for merging categories)
- `EMBEDDING_MODEL`: 'all-MiniLM-L6-v2'
- `LLM_MODEL_ID`: "Qwen/Qwen2.5-1.5B-Instruct"

## Project Structure

```
transactai/
├── api.py                  # FastAPI application
├── schemas.py              # Pydantic models
├── smart_categorizer.py    # Core categorization logic
└── __init__.py
```

## Reset System

To clear all learned data and start fresh:

```bash
POST /reset
```

##