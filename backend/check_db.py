"""
check_db.py
-----------
Quick connectivity and schema check.

    python check_db.py
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://tanyabora8869_db_user:py8WLf3ejE86rXSq@cluster0.uflgnz8.mongodb.net/?appName=Cluster0"
)
DB_NAME = os.getenv("DB_NAME", "deadzone01")

try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print(f"\nMongoDB Atlas  : CONNECTED")
except Exception as e:
    print(f"\nMongoDB Atlas  : FAILED — {e}")
    exit(1)

db = client[DB_NAME]
print(f"Database       : {DB_NAME}")
print(f"\nCollections:")
for col in sorted(db.list_collection_names()):
    count = db[col].count_documents({})
    print(f"  {col:<30} {count:>4} documents")

print("\nAll OK.\n")
