"""Compatibility import for the canonical DealMind FastAPI application.

Start the service with ``uvicorn backend.main:app``. This module intentionally
does not create a second FastAPI application.
"""

from backend.main import app

__all__ = ["app"]
