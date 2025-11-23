"""
This file was refactored. Use `run.py` to start the FastAPI server, or run with:

    python -m transactai.api

Or use uvicorn directly:

    uvicorn transactai.api:app --reload --host 0.0.0.0 --port 8000
"""

from transactai.api import run

if __name__ == "__main__":
    run()