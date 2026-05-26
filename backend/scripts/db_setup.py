"""
db_setup.py — Run this once after deployment to initialize indexes
and verify the database is reachable.

Usage:
    python scripts/db_setup.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from models.models import init_indexes
from models.token_blocklist import TokenBlocklist


def main():
    uri    = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    dbname = os.getenv("MONGO_DB_NAME", "ai_meeting_analyzer")

    print(f"Connecting to MongoDB: {uri}/{dbname}")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("ping")
        print("✅ MongoDB connection OK")
    except Exception as e:
        print(f"❌ Cannot connect to MongoDB: {e}")
        sys.exit(1)

    db = client[dbname]

    # Standard indexes
    init_indexes(db)

    # Token blocklist TTL index
    TokenBlocklist.init_ttl_index(db)
    print("✅ Token blocklist TTL index ready")

    # Print collection stats
    for col in ["users", "meetings", "transcripts", "analyses", "token_blocklist"]:
        count = db[col].count_documents({})
        print(f"   {col}: {count} documents")

    print("\n✅ Database setup complete.")
    client.close()


if __name__ == "__main__":
    main()
