"""
mongo_client.py
---------------
Provides two MongoDB clients:
  - async_db  : Motor (used inside async FastAPI route handlers)
  - sync_db   : pymongo (used inside ML model functions called by M1 / M2)

Both point to the same Atlas cluster and DB_NAME from .env
"""

import os
from dotenv import load_dotenv
import motor.motor_asyncio
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://tanyabora8869_db_user:py8WLf3ejE86rXSq@cluster0.uflgnz8.mongodb.net/?appName=Cluster0"
)
DB_NAME = os.getenv("DB_NAME", "deadzone01")

# ── Async client (Motor) ── used in all async FastAPI route handlers ──────────
_async_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
async_db = _async_client[DB_NAME]

# ── Sync client (pymongo) ── used in M1 / M2 ML functions ────────────────────
_sync_client = MongoClient(MONGO_URL)
sync_db = _sync_client[DB_NAME]


def get_async_db():
    """Return the Motor async database. Use inside FastAPI route handlers."""
    return async_db


def get_sync_db():
    """Return the pymongo sync database. Use inside ML model functions."""
    return sync_db
