"""
setup_db.py  —  DeadZero v3.0
Run once to initialise MongoDB Atlas collections and indexes.
Safe to re-run: drops bad docs, recreates indexes cleanly.

Usage:
    python3 setup_db.py
"""

import os
from pymongo import MongoClient, ASCENDING
from pymongo.errors import CollectionInvalid
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME   = os.getenv("DB_NAME", "deadzone01")

# ── connect ───────────────────────────────────────────────────────────────────
print(f"\nConnecting to MongoDB...")
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)

# verify connection
client.admin.command("ping")
print(f"✅ Connected")

db = client[DB_NAME]
print(f"   Database : {DB_NAME}\n")

# ── collections to ensure exist ───────────────────────────────────────────────
COLLECTIONS = [
    "sessions",
    "grids",
    "routers",
    "signal_results",
    "deadzones",
    "optimisation_results",
    "suggestions",
]

print("Ensuring collections exist...")
for name in COLLECTIONS:
    existing = db.list_collection_names()
    if name in existing:
        print(f"  Exists   : {name}")
    else:
        db.create_collection(name)
        print(f"  Created  : {name}")

# ── STEP 1: clean up null / bad documents BEFORE creating unique indexes ──────
print("\nCleaning up documents with null session_id (if any)...")

for coll_name in COLLECTIONS:
    result = db[coll_name].delete_many({"session_id": None})
    if result.deleted_count > 0:
        print(f"  🧹 Removed {result.deleted_count} null-session_id doc(s) from '{coll_name}'")
    else:
        print(f"  ✓  '{coll_name}' is clean")

# ── STEP 2: drop old conflicting indexes before recreating ────────────────────
print("\nDropping old indexes (safe — will recreate)...")

INDEX_NAMES_TO_DROP = [
    "session_id_unique",
    "session_id_1",
    "router_id_unique",
    "router_id_1",
]

for coll_name in COLLECTIONS:
    coll = db[coll_name]
    existing_indexes = [idx["name"] for idx in coll.list_indexes()]
    for idx_name in INDEX_NAMES_TO_DROP:
        if idx_name in existing_indexes:
            coll.drop_index(idx_name)
            print(f"  Dropped  : {coll_name}.{idx_name}")

# ── STEP 3: create indexes cleanly ───────────────────────────────────────────
print("\nCreating indexes...")

# sessions — unique session_id
db.sessions.create_index(
    [("session_id", ASCENDING)],
    unique=True,
    sparse=True,          # ← sparse=True skips documents where session_id is null
    name="session_id_unique"
)
print("  ✅ sessions.session_id_unique")

# grids — session_id lookup
db.grids.create_index(
    [("session_id", ASCENDING)],
    sparse=True,
    name="session_id_1"
)
print("  ✅ grids.session_id_1")

# routers — unique router_id + session lookup
db.routers.create_index(
    [("router_id", ASCENDING)],
    unique=True,
    sparse=True,
    name="router_id_unique"
)
db.routers.create_index(
    [("session_id", ASCENDING)],
    sparse=True,
    name="session_id_1"
)
print("  ✅ routers.router_id_unique + session_id_1")

# signal_results
db.signal_results.create_index(
    [("session_id", ASCENDING)],
    sparse=True,
    name="session_id_1"
)
print("  ✅ signal_results.session_id_1")

# deadzones
db.deadzones.create_index(
    [("session_id", ASCENDING)],
    sparse=True,
    name="session_id_1"
)
print("  ✅ deadzones.session_id_1")

# optimisation_results
db.optimisation_results.create_index(
    [("session_id", ASCENDING)],
    sparse=True,
    name="session_id_1"
)
print("  ✅ optimisation_results.session_id_1")

# suggestions
db.suggestions.create_index(
    [("session_id", ASCENDING)],
    sparse=True,
    name="session_id_1"
)
print("  ✅ suggestions.session_id_1")

# ── done ──────────────────────────────────────────────────────────────────────
print("\n✅ Database setup complete!")
print(f"   Collections : {db.list_collection_names()}")
print(f"   Ready to run: uvicorn app.main:app --reload --port 8000\n")

client.close()